"""Deployment contract: docker-compose.yml and the two Dockerfiles.

S7.3's exit criterion is "`docker compose up` reaches a working demo". The
container build cannot be exercised here, so these specs do not pretend to.

What they DO is pin the wiring that the image build depends on, and that part is
checkable without a daemon:

  * the API URL the frontend is built with is resolvable BY A BROWSER, not by
    Docker -- a compose service name is wrong here, and the failure is a blank
    page rather than an error, so nothing else would catch it;
  * the healthcheck paths name endpoints that actually exist in the app;
  * the servers bind 0.0.0.0, because the default 127.0.0.1 produces a container
    that looks healthy and refuses connections;
  * no credential is required, because a demo that needs secrets is a demo that
    does not come up on a clean clone;
  * ``backend/.env`` is excluded from the build context, so credentials cannot be
    baked into an image by accident.

Each of those is a mistake that is cheap to make and expensive to discover at
demo time. Where a check cannot be made, it says so rather than passing quietly.

NOTE ON THE BUILD ITSELF. These specs do NOT verify that either image builds,
that the pinned wheels resolve for the image's Python, or that compose comes up.
``make verify-docker`` does that on a machine with a daemon, and the PR that
introduced this file recorded that it had not been run.
"""

from __future__ import annotations

import json
import subprocess
import re
import sys
import urllib.parse
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
COMPOSE = REPO / "docker-compose.yml"
BACKEND_DOCKERFILE = REPO / "backend" / "Dockerfile"
FRONTEND_DOCKERFILE = REPO / "frontend" / "Dockerfile"
DOCKERIGNORE = REPO / ".dockerignore"


def _strip_ts_comments(src: str) -> str:
    """Remove // and /* */ comments so an assertion about CODE cannot be
    satisfied or broken by the prose around it.

    PROTECTS URLS FIRST, which the first version did not. A naive scanner sees
    "http://localhost:8000", takes the "//" for a line comment, and deletes the
    rest of the line -- so the search string was removed by the stripper, and
    reintroducing the very bug under test still passed. A guard that cannot see
    the defect is worse than no guard, because it reports coverage.

    Still lossy in one respect: it does not understand string literals, so a
    "//" inside a string is treated as a comment. For the only use -- asking
    whether a function still returns a default -- that is harmless.
    """
    sentinel = "\u0000URLSLASH\u0000"
    guarded = src.replace("://", f":{sentinel}")
    out, i, n = [], 0, len(guarded)
    while i < n:
        if guarded.startswith("//", i):
            j = guarded.find("\n", i)
            i = n if j == -1 else j
        elif guarded.startswith("/*", i):
            j = guarded.find("*/", i)
            i = n if j == -1 else j + 2
        else:
            out.append(guarded[i])
            i += 1
    return "".join(out).replace(sentinel, "//")


@pytest.fixture(scope="module")
def compose() -> dict:
    if not COMPOSE.exists():
        pytest.fail("docker-compose.yml is missing; S7.3 requires it")
    return yaml.safe_load(COMPOSE.read_text())


@pytest.fixture(scope="module")
def backend_dockerfile() -> str:
    return BACKEND_DOCKERFILE.read_text()


@pytest.fixture(scope="module")
def frontend_dockerfile() -> str:
    return FRONTEND_DOCKERFILE.read_text()


# --------------------------------------------------------------------------- #
# compose shape                                                               #
# --------------------------------------------------------------------------- #


def test_compose_declares_both_services(compose: dict) -> None:
    services = compose.get("services", {})
    assert "backend" in services, "the demo needs a backend service"
    assert "frontend" in services, "the demo needs a frontend service"


def test_both_services_publish_a_port(compose: dict) -> None:
    for name, svc in compose["services"].items():
        assert svc.get("ports"), f"{name} publishes no port, so the demo is unreachable"


def test_published_ports_do_not_collide(compose: dict) -> None:
    seen: dict[int, str] = {}
    for name, svc in compose["services"].items():
        for mapping in svc.get("ports", []):
            host = int(str(mapping).split(":")[0])
            assert host not in seen, f"{name} and {seen[host]} both bind host port {host}"
            seen[host] = name


# --------------------------------------------------------------------------- #
# The build-time API URL. The subtle one.                                   #
# --------------------------------------------------------------------------- #


def test_api_url_is_a_build_arg_not_a_runtime_env(compose: dict) -> None:
    """NEXT_PUBLIC_* is INLINED at build time by Next.js.

    Setting it as a runtime environment variable on the container produces an
    image that silently keeps whatever URL it was built with, and the symptom is
    a frontend pointing at nothing with no error anywhere.
    """
    frontend = compose["services"]["frontend"]
    args = frontend.get("build", {}).get("args", {})
    assert "NEXT_PUBLIC_API_URL" in args, (
        "NEXT_PUBLIC_API_URL must be a build arg. As a runtime env var it is "
        "inlined at build time and ignored at run time."
    )
    env = frontend.get("environment", {}) or {}
    assert "NEXT_PUBLIC_API_URL" not in env, (
        "NEXT_PUBLIC_API_URL in the runtime environment is a no-op and implies "
        "a belief that it works, which is worse than leaving it out"
    )


def _api_url_default(compose: dict) -> str:
    """The DEFAULT a compose value resolves to.

    A compose value is usually the interpolation ``${VAR:-fallback}``, so the
    literal in the file is not the URL anybody gets. Inspecting the raw string
    would assert against text that is never used, and in one version of this
    spec it reported "an absolute URL is required" about a string that did have
    one, ninety characters past the host.
    """
    raw = str(compose["services"]["frontend"]["build"]["args"]["NEXT_PUBLIC_API_URL"])
    m = re.search(r":-([^}]*)\}$", raw)
    return (m.group(1) if m else raw).strip()


def test_api_url_is_resolvable_by_a_browser(compose: dict) -> None:
    """A compose service name is NOT resolvable by a browser on the host.

    The value is consumed by a browser, not by Docker, so "backend" or
    "http://backend:8000" cannot work from a laptop. This is the mistake a
    compose file makes most easily, because it looks correct and the container
    network genuinely does resolve it.
    """
    url = _api_url_default(compose)
    assert "backend" not in url, (
        f"the browser cannot resolve a compose service name: {url!r}. Use the "
        "PUBLISHED host address, e.g. http://localhost:8000."
    )
    assert url.startswith("http://"), f"an absolute URL is required, got {url!r}"


def test_default_api_url_points_at_the_published_backend_port(compose: dict) -> None:
    backend_publish = str(compose["services"]["backend"]["ports"][0]).split(":")[0]
    url = _api_url_default(compose)
    assert f":{backend_publish}" in url, (
        f"the frontend is built against {url} but the backend publishes "
        f"{backend_publish}; the demo would start and show nothing"
    )


# --------------------------------------------------------------------------- #
# Credentials are optional                                                    #
# --------------------------------------------------------------------------- #


def test_no_service_embeds_a_literal_secret(compose: dict) -> None:
    """Values are passthroughs, never literals.

    Every credential must arrive as ``${VAR:-}`` so that an absent .env yields
    an empty value and fixture mode. A literal in the compose file would put a
    secret in version control, and a REQUIRED variable would make the S7 exit
    criterion unreachable for anyone but the author.
    """
    secretish = re.compile(r"(SECRET|API_KEY|API_SECRET|PASSWORD|TOKEN)", re.I)
    for name, svc in compose["services"].items():
        for key, value in (svc.get("environment") or {}).items():
            if not secretish.search(key):
                continue
            rendered = str(value)
            assert "${" in rendered and ":-" in rendered, (
                f"{name}.{key} must be a passthrough defaulting to empty, got "
                f"{rendered!r}. A literal puts a secret in git; a bare ${VAR} "
                "makes the demo unstartable without one."
            )


def test_required_interpolation_without_a_default_is_absent(compose: dict) -> None:
    """``${VAR}`` is a HARD requirement; ``${VAR:-}`` is not.

    Compose substitutes the former from the host environment and fails loudly if
    it is unset, which is the opposite of what a clean-clone demo needs.
    """
    for name, svc in compose["services"].items():
        for key, value in (svc.get("environment") or {}).items():
            rendered = str(value)
            for var, sep, default in re.findall(r"\$\{([A-Z_]+)(:-?)([^}]*)\}", rendered):
                assert sep == ":-", (
                    f"{name}.{key} uses ${{{var}}} with no default, so compose "
                    "fails when it is unset"
                )


def test_dotenv_is_excluded_from_the_build_context() -> None:
    """Credentials must not be bakeable into an image by accident.

    backend/.env is gitignored, and .dockerignore makes that structural rather
    than a convention someone has to remember.
    """
    if not DOCKERIGNORE.exists():
        pytest.fail(".dockerignore is missing; the build context is the repo root")
    lines = {
        line.strip()
        for line in DOCKERIGNORE.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    assert "backend/.env" in lines, "backend/.env would be sent to the build daemon"
    assert ".git" in lines, ".git in the build context is megabytes of nothing"
    assert "frontend/node_modules" in lines, "node_modules must not come from the host"


# --------------------------------------------------------------------------- #
# Dockerfiles                                                                 #
# --------------------------------------------------------------------------- #


def _healthcheck_commands(dockerfile: str) -> list[str]:
    """The CMD of every HEALTHCHECK, as a list of tokens.

    A Dockerfile HEALTHCHECK may be written in shell form (a string) or exec
    form (a JSON array). Both appear in real files, and a parser that only
    understands one reports "the Dockerfile has no port" about a Dockerfile
    that plainly does -- which is what happened here on the first run.
    """
    out: list[str] = []
    for block in re.findall(r"^HEALTHCHECK[^\n]*\n(?:[ \t]+.*\n)*", dockerfile, re.M):
        m = re.search(r"\bCMD\s+(.+)$", block, re.M)
        if not m:
            continue
        raw = m.group(1).strip()
        if raw.startswith("["):
            out.append(" ".join(json.loads(raw)))
        else:
            out.append(raw)
    return out


def _json_array(dockerfile: str, key: str) -> list[str]:
    """The JSON array form of an instruction, e.g. ``CMD ["a", "b"]``."""
    m = re.search(rf"^{key}\s+(\[.*\])", dockerfile, re.M)
    return json.loads(m.group(1)) if m else []


def test_servers_bind_all_interfaces(
    backend_dockerfile: str, frontend_dockerfile: str
) -> None:
    """0.0.0.0, not 127.0.0.1.

    The default loopback bind produces a container that starts, logs a healthy
    message, and refuses every connection from outside -- so the failure looks
    like a networking problem on the host rather than a misconfigured CMD.
    """
    backend_cmd = " ".join(_json_array(backend_dockerfile, "CMD"))
    frontend_cmd = " ".join(_json_array(frontend_dockerfile, "CMD"))
    assert "--host 0.0.0.0" in backend_cmd, (
        f"backend CMD does not bind all interfaces: {backend_cmd!r}"
    )
    assert "--hostname 0.0.0.0" in frontend_cmd, (
        f"frontend CMD does not bind all interfaces: {frontend_cmd!r}"
    )


def test_containers_run_unprivileged(
    backend_dockerfile: str, frontend_dockerfile: str
) -> None:
    for name, text in (("backend", backend_dockerfile), ("frontend", frontend_dockerfile)):
        assert re.search(r"^USER ", text, re.M), f"{name} runs as root"
        # USER after the final COPY, or the copied files are unreadable.
        assert text.rindex("USER ") > text.rindex("COPY "), (
            f"{name} switches user before its last COPY, so the files are root-owned"
        )


def test_backend_healthcheck_names_a_real_endpoint(backend_dockerfile: str) -> None:
    """The healthcheck path must exist in the app.

    A healthcheck against a path that is not routed never passes, and the
    deployment reports unhealthy for a reason that has nothing to do with the
    app -- so the endpoints are cross-checked against the real route table.
    """
    commands = _healthcheck_commands(backend_dockerfile)
    assert commands, "the backend Dockerfile has no HEALTHCHECK CMD"
    routes = _backend_routes()
    for command in commands:
        # Parse the path OUT of the URL. A regex over the raw text matches
        # "//127.0.0.1" out of "http://127.0.0.1:8000/health" and then reports
        # that as a missing route, which is how this spec failed first.
        for url in re.findall(r"https?://[^\s'\"|]+", command):
            path = urllib.parse.urlparse(url).path
            assert path, f"no path in {url!r}"
            assert path in routes, (
                f"the backend healthcheck requests {path!r}, which is not a "
                "route. A healthcheck against a missing path never passes."
            )


def _backend_routes() -> set[str]:
    sys.path.insert(0, str(REPO / "backend"))
    try:
        from mock_server import app  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover - import guard
        pytest.fail(f"could not import the app to cross-check routes: {exc}")
    finally:
        sys.path.pop(0)
    return {getattr(r, "path", "") for r in app.routes}


def test_health_endpoint_is_actually_served() -> None:
    """The route the healthcheck depends on, verified rather than assumed."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    sys.path.insert(0, str(REPO / "backend"))
    try:
        from mock_server import app  # noqa: PLC0415
    finally:
        sys.path.pop(0)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json().get("status") == "ONLINE"


def test_backend_healthcheck_agrees_with_the_port_the_container_serves(
    backend_dockerfile: str,
) -> None:
    """The healthcheck port and the CMD port must be the same number.

    They are written by hand in two places, and a mismatch is invisible until
    the container is unhealthy for a reason that has nothing to do with the app.
    """
    cmd_port = re.search(r"--port\"?,?\s+\"?(\d+)", " ".join(_json_array(backend_dockerfile, "CMD")))
    assert cmd_port, "no --port in the backend CMD"
    health_port = re.search(r":(\d+)/health", " ".join(_healthcheck_commands(backend_dockerfile)))
    assert health_port, "the healthcheck does not name a port"
    assert cmd_port.group(1) == health_port.group(1), (
        f"the CMD serves port {cmd_port.group(1)} but the healthcheck probes "
        f"{health_port.group(1)}"
    )
    assert "EXPOSE 8000" in backend_dockerfile


def test_python_version_matches_the_wheel_pins(backend_dockerfile: str) -> None:
    """The image must be the Python the pinned wheels were chosen for.

    backend/requirements.txt records that its pins target CPython 3.11/3.12 and
    that a few floors were relaxed for cp313 wheels. An image on a different
    minor version re-opens that whole question at build time, on a machine with
    no virtualenv to compare against.
    """
    reqs = (REPO / "backend" / "requirements.txt").read_text()
    assert "CPython 3.11/3.12" in reqs, "requirements.txt no longer records its target"
    m = re.search(r"FROM python:3\.(\d+)-slim", backend_dockerfile)
    assert m, "no pinned Python base image"
    assert m.group(1) in {"11", "12"}, (
        f"the image is on Python 3.{m.group(1)}, but the pins target 3.11/3.12"
    )


def test_frontend_uses_ci_frontend_install(frontend_dockerfile: str) -> None:
    """`npm ci`, not `npm install`.

    The lockfile is committed precisely so the image matches CI. `npm install`
    would let the image resolve different versions than the tests were run
    against, which is a difference nobody would notice until the demo broke.
    """
    assert "npm ci" in frontend_dockerfile, "the image does not use npm ci"
    assert "npm install" not in frontend_dockerfile
    assert "package-lock.json" in frontend_dockerfile, "the lockfile is not copied in"


def test_frontend_waits_for_a_healthy_backend(compose: dict) -> None:
    """depends_on must be on health, not merely on start.

    The frontend paints panels against the API on first render, so a startup
    race shows up as a fixture badge that appears and then clears -- which reads
    as a defect in the provenance labelling rather than as ordering.
    """
    dep = compose["services"]["frontend"]["depends_on"]["backend"]
    assert dep.get("condition") == "service_healthy", (
        "the frontend must wait for the backend to be HEALTHY, not merely started"
    )


# --------------------------------------------------------------------------- #
# Judge-facing deployment. See docs/DEMO.md.                                    #
# --------------------------------------------------------------------------- #


def test_vercel_config_is_where_vercel_actually_looks() -> None:
    """The config must be in the PROJECT ROOT, which is `frontend/`.

    It was committed at the REPO ROOT and Vercel silently ignored every line of
    it. Nothing errored: `vercel build` reported "Detected Next.js (Build
    Command: next build, Output Directory: Next.js default)" -- defaults, not the
    committed config -- and carried on.

    That is the failure shape worth guarding. A config file in the wrong
    directory is not a build failure, it is a build that quietly uses somebody
    else's idea of the build command, and the only evidence is a line in a log
    that reads like a normal detection message.

    `.vercel/project.json` is written by the CLI into whatever directory it was
    invoked from, so that is the authority on where the project root is.
    """
    import json

    p = REPO / "frontend" / "vercel.json"
    if not p.exists():
        pytest.fail(
            "frontend/vercel.json is missing. Note the DIRECTORY: the Vercel "
            "project root is frontend/, and a vercel.json at the repo root is "
            "ignored in silence."
        )
    assert not (REPO / "vercel.json").exists(), (
        "a vercel.json at the repo root is ignored by Vercel and will mislead "
        "the next reader into thinking the build is configured"
    )

    cfg = json.loads(p.read_text())
    # `npm ci`, not `npm install`: an unpinned install makes the deployed build
    # differ from the tested one, which is invisible until it breaks on stage.
    assert cfg.get("installCommand", "").startswith("npm ci"), (
        f"installCommand is {cfg.get('installCommand')!r}; an unpinned install "
        "makes the deployed build differ from the tested one"
    )
    assert cfg.get("framework") == "nextjs"


def test_no_api_url_is_baked_into_the_committed_build() -> None:
    """A judge-facing deploy must make no request, and the build is the proof.

    NEXT_PUBLIC_* is inlined at build time, so the deployed artefact is the only
    place this can be checked -- the source could be correct and the bundle still
    contain a URL, which is exactly the shape of bug the e2e suite cannot see.
    """
    static = REPO / "frontend" / ".next" / "static"
    if not static.exists():
        pytest.skip("no local .next build; run `make fe-build` first")
    hits = subprocess.run(
        ["grep", "-rl", "localhost:8000", str(static)],
        capture_output=True,
        text=True,
    )
    assert hits.returncode != 0, (
        "a local .next build contains localhost:8000, so a deployment made from "
        "it would point every panel at the judge's own machine"
    )


def test_demo_build_makes_no_network_requests() -> None:
    """Tier 1 is only honest if the page asks for nothing.

    The frontend runs with the backend entirely absent -- that is the S6 exit
    criterion -- but the first implementation still FETCHED, defaulting to
    http://localhost:8000 and degrading after connection-refused. Working by
    accident, and reporting "Backend unreachable" when the truth was that no
    backend had been asked for. The spec in frontend/e2e/demo-build.spec.ts
    asserts the absence of requests; this asserts the source no longer invents a
    default, so the two cannot drift.
    """
    src = (REPO / "frontend" / "lib" / "api.ts").read_text()
    # Strip comments first. api.ts DOCUMENTS this change, so the literal text
    # "?? \"http://localhost:8000\"" appears in the explanatory comment that
    # describes removing it -- and the first version of this spec failed on that
    # comment while the code was correct. A code assertion that can be satisfied
    # or broken by prose is not a code assertion.
    code = _strip_ts_comments(src)
    assert '?? "http://localhost:8000"' not in code, (
        "api.ts still invents a localhost default. A judge-facing build with no "
        "API configured must make no request at all, not fall back to one."
    )
    assert "isDemoBuild" in code, "the no-API state is not a first-class case"


def test_demo_images_are_publishable() -> None:
    """Tier 3 -- one command for a judge -- needs a publish workflow."""
    p = REPO / ".github" / "workflows" / "publish-demo.yml"
    if not p.exists():
        pytest.fail("publish-demo.yml is missing; Tier 3 of docs/DEMO.md cannot run")
    text = p.read_text()
    for required in ("ghcr.io", "backend/Dockerfile", "frontend/Dockerfile"):
        assert required in text, f"the publish workflow does not build {required}"
    # It must not publish on every branch push: that burns registry space and
    # makes `latest` meaningless.
    assert "tags:" in text, "the workflow triggers on nothing"


def test_demo_doc_states_what_each_tier_does_not_prove() -> None:
    """A demo guide that only lists what works is marketing, not documentation."""
    p = REPO / "docs" / "DEMO.md"
    if not p.exists():
        pytest.fail("docs/DEMO.md is missing")
    text = p.read_text()
    assert "does not prove" in text.lower()
    assert "unconfirmed" in text.lower(), (
        "the unconfirmed webhook signature is the one surface a judge can break, "
        "and the demo guide must say so"
    )
    for tier in ("Tier 1", "Tier 2", "Tier 3"):
        assert tier in text, f"{tier} is undocumented"


DEMO_URL = "https://veritas-dmrv.vercel.app"


def test_documented_demo_url_is_the_one_that_is_actually_public() -> None:
    """The README, the pitch and DEMO.md must all cite a URL that opens.

    A documented URL that has been renamed, aliased behind a login, or moved is
    worse than no URL: a judge who types it in front of a room and gets a login
    page is a thing that happened here already.

    This project shipped once with a SHORT url that answered 302 to a Vercel
    login, because the project had `ssoProtection: all_except_custom_domains`.
    The long url beside it was public, so checking the long one found nothing
    wrong. The only reason it was caught is that the alias was changed and then
    FETCHED.

    Network-gated, like the other live checks: it skips rather than failing when
    there is no connectivity, because a laptop on a train should not turn a
    documentation typo into a red build.
    """
    import urllib.error
    import urllib.request

    for doc in ("README.md", "docs/DEMO.md", "docs/14-HACKATHON-PITCH-DECK-AND-PRESENTATION.md"):
        text = (REPO / doc).read_text()
        assert DEMO_URL in text, f"{doc} does not link the live demo"

    try:
        with urllib.request.urlopen(DEMO_URL, timeout=20) as r:
            status, body = r.status, r.read()
    except urllib.error.URLError as exc:
        pytest.skip(f"no network here ({exc}); the URL is not verified in this run")
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"{DEMO_URL} could not be checked: {type(exc).__name__}: {exc}")

    assert status == 200, (
        f"{DEMO_URL} answered HTTP {status}. If this is a 302 to a login, "
        "Vercel Authentication is on -- ssoProtection: all_except_custom_domains "
        "-- and a judge cannot open the demo. See docs/S7-WORKFLOW.md."
    )
    assert len(body) > 10_000, f"{DEMO_URL} served {len(body)} bytes, not the app"
    # A redirect to a login page is a 200 on a login host. Catch it explicitly.
    assert b"Evidence portfolio" in body, (
        f"{DEMO_URL} returned 200 but not the application -- likely a login page"
    )


def test_static_demo_export_is_opt_in_only() -> None:
    """The static export must not reconfigure production.

    It is a demo affordance, so the risk is that it changes what the Docker
    image or Vercel serve. Two earlier approaches were abandoned -- a second
    config file, which `next build` cannot select, and the programmatic API,
    which does not expose build() -- and the shell alternative would have left
    the export config in place if a build were interrupted. So the export is a
    branch inside the one config, selected by an env var that production does
    not set.
    """
    cfg = (REPO / "frontend" / "next.config.mjs").read_text()
    assert "VERITAS_STATIC_DEMO" in cfg, "the static export is not env-gated"
    # The gate must be an equality check against "1", not a truthiness check on
    # the variable's mere presence: a stray empty value must not enable the
    # export, or an unset-but-declared variable would silently ship a static
    # bundle to the container.
    assert 'VERITAS_STATIC_DEMO === "1"' in cfg, (
        "the export gate is not an explicit ==1 check; a truthiness check would "
        "enable the export whenever the variable is merely present"
    )
    # And no alternate config file, because it could not be selected anyway.
    assert not (REPO / "frontend" / "next.export.config.mjs").exists(), (
        "an alternate config file exists but `next build` cannot select it"
    )
