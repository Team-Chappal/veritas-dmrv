"""CORS is a security control once this is deployed, and a convenience before.

S7.4's Tier 2 -- a public URL with a hosted backend -- is what turns
``allow_origins=["*"]`` from "fine on a laptop" into "an unauthenticated public
API that anybody on the internet can script against, driving this deployment's
Cloudinary quota".

The mutating routes already carry JWT scopes. The READ routes deliberately do
not, because they are the demo surface a judge is meant to poke. So the read
surface is exactly the thing that must not be reachable from every site on the
internet, and this file pins that.

The default stays ``*`` so the S6 exit criterion keeps holding: the app must work
with no configuration at all, and CORS must not be the reason it cannot.
"""

from __future__ import annotations

import ast
import importlib
import os
import sys

import pytest
from fastapi.testclient import TestClient

REPO = __import__("pathlib").Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

ORIGIN_OK = "https://veritas-dmrv.vercel.app"
ORIGIN_LOCAL = "http://localhost:3000"
ORIGIN_EVIL = "https://evil.example"


@pytest.fixture
def app_with_cors(monkeypatch: pytest.MonkeyPatch):
    """Import the app with a given CORS_ALLOW_ORIGINS and hand back a client.

    The app is a module-level singleton, so it has to be re-imported for each
    setting. Reloading it is not free but it is correct, and doing it properly is
    what lets the three cases below be tested independently instead of one being
    whatever happened to load first.
    """
    import core.config
    import mock_server

    def build(value: str | None):
        if value is None:
            monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
        else:
            monkeypatch.setenv("CORS_ALLOW_ORIGINS", value)
        importlib.reload(core.config)
        return importlib.reload(mock_server).app

    yield build

    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    importlib.reload(core.config)
    importlib.reload(mock_server)


def _origin_for(app, origin: str) -> str | None:
    with TestClient(app) as c:
        r = c.get("/health", headers={"Origin": origin})
    return r.headers.get("access-control-allow-origin")


def _cors_middleware_kwargs() -> dict:
    """The keyword arguments of the real add_middleware(CORSMiddleware, ...) call.

    Read from the syntax tree, so neither a comment nor a string can be mistaken
    for the configuration that ships.
    """
    import ast

    tree = ast.parse((REPO / "backend" / "mock_server.py").read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "attr", None) or getattr(func, "id", None)
        if name != "add_middleware":
            continue
        if not node.args or "CORS" not in ast.dump(node.args[0]):
            continue
        return {kw.arg: kw.value for kw in node.keywords if kw.arg}
    return {}


def _is_literal_star_list(node: ast.AST) -> bool:
    """True if the expression is literally a list containing the string "*"."""
    if not isinstance(node, (ast.List, ast.Tuple)):
        return False
    return any(
        isinstance(e, ast.Constant) and e.value == "*" for e in node.elts
    )


class TestCorsPolicy:
    def test_default_is_wildcard_so_local_dev_needs_no_configuration(
        self, app_with_cors
    ) -> None:
        """The S6 exit criterion, pinned.

        `allow_origins=["*"]` on a laptop is a convenience. Remove it and the
        Next dev server on :3000 cannot talk to a mock backend on :8000, which
        would make the exit criterion -- works with the backend entirely absent,
        no configuration -- fail for a reason that has nothing to do with the
        product.
        """
        assert _origin_for(app_with_cors(None), ORIGIN_LOCAL) == "*"

    def test_a_listened_origin_is_allowed(self, app_with_cors) -> None:
        app = app_with_cors(f"{ORIGIN_OK},{ORIGIN_LOCAL}")
        assert _origin_for(app, ORIGIN_OK) == ORIGIN_OK
        assert _origin_for(app, ORIGIN_LOCAL) == ORIGIN_LOCAL

    def test_an_unlisted_origin_is_refused(self, app_with_cors) -> None:
        """The whole point of the change, and the one that would be missed.

        A permissive CORS policy is not a slow burn, it is a header that is
        either present or absent, so this is a single boolean and there is no
        middle ground in which it is quietly half-configured.
        """
        app = app_with_cors(ORIGIN_OK)
        assert _origin_for(app, ORIGIN_EVIL) is None, (
            f"{ORIGIN_EVIL} was allowed to call a deployed API. The read routes "
            "carry no auth by design, so CORS is the only control on them."
        )

    def test_none_denies_every_browser_origin(self, app_with_cors) -> None:
        """For a backend nothing is meant to call -- a worker, a cron endpoint.

        `allow_origins=["none"]` is the setting that makes that explicit, rather
        than leaving a wildcard on something that should be unreachable from a
        browser at all.
        """
        app = app_with_cors("none")
        assert _origin_for(app, ORIGIN_LOCAL) is None
        assert _origin_for(app, ORIGIN_OK) is None

    def test_whitespace_in_the_list_is_tolerated(self, app_with_cors) -> None:
        """A comma-separated env var is hand-written, so it will have spaces.

        `CORS_ALLOW_ORIGINS="a, b"` is the natural way to type it. Without
        stripping, the second origin is `" b"` and silently never matches, which
        produces a 403 that looks like a deployment problem.
        """
        app = app_with_cors(f"  {ORIGIN_OK} ,  {ORIGIN_LOCAL}  ")
        assert _origin_for(app, ORIGIN_LOCAL) == ORIGIN_LOCAL

    def test_credentials_stay_off(self) -> None:
        """`*` plus credentials is a wildcard that silently never applies.

        The browser refuses `Access-Control-Allow-Origin: *` on a credentialed
        request, so a config with both set does not mean "wide open", it means
        "broken, in a way that only shows up for cookie-bearing requests".

        Read from the AST rather than from `app.user_middleware`, which does not
        hold the middleware in the way this assumed -- the first version of this
        spec asserted the middleware "is not installed" on a build where it
        plainly was.
        """
        kwargs = _cors_middleware_kwargs()
        assert kwargs, "no add_middleware(CORSMiddleware, ...) call in the source"
        creds = kwargs["allow_credentials"]
        # ast.Constant, not a bare bool: the node compares False by identity and
        # an unwrapped Constant is what the parse actually produces.
        assert isinstance(creds, ast.Constant) and creds.value is False, (
            f"allow_credentials must be False alongside a wildcard origin, got "
            f"{ast.dump(creds)}"
        )


class TestCorsConfig:
    def test_the_setting_exists_and_is_read_from_the_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import core.config  # noqa: PLC0415

        monkeypatch.setenv("CORS_ALLOW_ORIGINS", f"{ORIGIN_OK},{ORIGIN_LOCAL}")
        importlib.reload(core.config)
        assert core.config.get_settings().cors_allow_origins == [
            ORIGIN_OK,
            ORIGIN_LOCAL,
        ]

    def test_a_wildcard_is_not_hardcoded_in_the_middleware(self) -> None:
        """The bug, pinned at the source.

        `allow_origins=["*"]` as a LITERAL is what made this policy
        unconfigurable, and it read as a deliberate convenience. A spec that only
        checked runtime behaviour would have passed while the literal sat there,
        one refactor away from being the deployed policy again.

        Parsed with `ast`, because a text search finds the literal in the
        COMMENT that explains removing it -- which is where the first version of
        this spec found it, in a file whose code was correct.
        """
        kwargs = _cors_middleware_kwargs()
        origins = kwargs.get("allow_origins")
        assert origins is not None, "the CORS call has no allow_origins"
        assert not _is_literal_star_list(origins), (
            "allow_origins is a hardcoded wildcard again; it must come from "
            "settings so a deployment can name its own origins"
        )

    def test_the_ast_helpers_can_see_a_hardcoded_wildcard(self) -> None:
        """Guards the guard, using the exact shape the real bug had.

        A parser that cannot recognise `["*"]` would report "not hardcoded" for
        a file that hardcodes it, and the check above would be a permanent pass.
        This is the same reasoning as the comment-stripper in
        test_deployment.py, where the stripper ate the URL it was searching for.
        """
        import ast as _ast

        hardcoded = _ast.parse("f(allow_origins=['*'])").body[0].value  # type: ignore[attr-defined]
        assert _is_literal_star_list(hardcoded.keywords[0].value), (
            "_is_literal_star_list does not recognise the pattern it exists to "
            "detect"
        )
        from_settings = _ast.parse("f(allow_origins=ALLOWED)").body[0].value  # type: ignore[attr-defined]
        assert not _is_literal_star_list(from_settings.keywords[0].value)
