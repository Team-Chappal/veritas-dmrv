"""
Rate limiting (S5.8).

The shipped default is 60 req/min, but the suite raises the ceiling so a global
counter cannot make unrelated tests fail by execution order (see
core/rate_limit.py). So this file proves the MECHANISM at a low limit rather than
re-proving the default, and separately pins the default itself so it cannot be
changed silently.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded

from core.config import Settings, get_settings
from core.rate_limit import (
    build_limiter,
    client_identity,
    is_test_ceiling,
    limit_string,
    rate_limit_exceeded_handler,
    rate_limited,
    register,
)

pytestmark = pytest.mark.tier5


def _app(limit: str):
    app = FastAPI()
    app.state.limiter = build_limiter()
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    @app.get("/ping")
    @app.state.limiter.limit(limit)
    def ping(request: Request):
        return {"ok": True}

    return TestClient(app)


def _request(headers: dict | None = None, client=("10.0.0.1", 1234)) -> Request:
    """A real Request, so header and client-address handling is exercised."""
    raw = [(b"host", b"test")]
    for k, v in (headers or {}).items():
        raw.append((k.lower().encode(), v.encode()))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": raw,
            "client": client,
            "query_string": b"",
        }
    )


class TestEnforcement:
    def test_trips_at_the_configured_limit(self):
        c = _app("3/minute")
        codes = [c.get("/ping").status_code for _ in range(6)]
        assert codes[:3] == [200, 200, 200]
        assert codes[3:] == [429, 429, 429]

    def test_exactly_at_the_limit_is_still_allowed(self):
        """Off-by-one here would throttle a client that is within budget."""
        c = _app("2/minute")
        assert [c.get("/ping").status_code for _ in range(2)] == [200, 200]

    def test_429_advertises_when_to_retry(self):
        """No Retry-After turns a throttle into a load amplifier."""
        c = _app("1/minute")
        c.get("/ping")
        r = c.get("/ping")
        assert r.status_code == 429
        assert r.headers["Retry-After"] == "60"
        assert r.json()["retry_after_seconds"] == 60

    def test_429_does_not_execute_the_route(self):
        """A throttled request must not do work."""
        calls = []
        app = FastAPI()
        app.state.limiter = build_limiter()
        app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

        @app.get("/count")
        @app.state.limiter.limit("1/minute")
        def count(request: Request):
            calls.append(1)
            return {"calls": len(calls)}

        c = TestClient(app)
        c.get("/count")
        c.get("/count")
        assert len(calls) == 1

    def test_distinct_bucket_keys_get_distinct_budgets(self):
        """One throttled client must not lock out the rest.

        Keyed through a proxy-aware function here, because the shipped
        ``get_remote_address`` reads only ``request.client.host`` and would put
        every proxied request in one bucket — see the module docstring.
        """
        def proxy_aware(request: Request) -> str:
            return request.headers.get("x-forwarded-for", "unknown")

        app = FastAPI()
        app.state.limiter = build_limiter(proxy_aware)
        app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

        @app.get("/ping")
        @app.state.limiter.limit("1/minute")
        def ping(request: Request):
            return {"ok": True}

        c = TestClient(app)
        assert c.get("/ping", headers={"X-Forwarded-For": "10.0.0.1"}).status_code == 200
        assert c.get("/ping", headers={"X-Forwarded-For": "10.0.0.1"}).status_code == 429
        assert c.get("/ping", headers={"X-Forwarded-For": "10.0.0.2"}).status_code == 200

    def test_two_test_clients_share_the_default_address(self):
        """Pins the proxy caveat rather than implying per-client IP limiting."""
        a, b = _app("1/minute"), _app("1/minute")
        a.get("/ping")
        assert b.get("/ping").status_code == 200
        assert a.get("/ping").status_code == 429

    def test_limit_string_follows_settings(self, monkeypatch):
        monkeypatch.setattr(
            "core.rate_limit.get_settings", lambda: Settings(rate_limit_per_minute=17)
        )
        assert limit_string() == "17/minute"

    def test_shipped_decoration_would_be_60_per_minute_by_default(self, monkeypatch):
        monkeypatch.delenv("RATE_LIMIT_PER_MINUTE", raising=False)
        monkeypatch.setattr(
            "core.rate_limit.get_settings",
            lambda: Settings(rate_limit_per_minute=60),
        )
        assert limit_string() == "60/minute"

    def test_limit_string_never_zeroes_out(self, monkeypatch):
        """A misconfigured 0 would disable limiting entirely."""
        monkeypatch.setattr(
            "core.rate_limit.get_settings", lambda: Settings(rate_limit_per_minute=0)
        )
        assert limit_string() == "1/minute"

    def test_negative_limit_is_clamped(self, monkeypatch):
        monkeypatch.setattr(
            "core.rate_limit.get_settings", lambda: Settings(rate_limit_per_minute=-5)
        )
        assert limit_string() == "1/minute"

    def test_rate_limited_returns_a_decorator(self):
        assert callable(rate_limited())


class TestIdentityKeying:
    def test_unauthenticated_keys_on_ip(self):
        assert client_identity(_request()) == "ip:10.0.0.1"

    def test_missing_key_falls_back_to_ip(self, monkeypatch):
        """The limiter must not 500 on a malformed token before the route runs."""
        def boom(*a, **k):
            raise ValueError("bad token")

        monkeypatch.setattr("core.rate_limit.principal_from_header", boom)
        assert client_identity(_request({"Authorization": "Bearer nonsense"})).startswith("ip:")

    def test_verified_token_keys_on_subject(self, monkeypatch):
        from core.auth import Principal

        monkeypatch.setattr(
            "core.rate_limit.principal_from_header",
            lambda *a, **k: Principal(subject="officer7", scopes=frozenset()),
        )
        assert client_identity(_request({"Authorization": "Bearer x"})) == "sub:officer7"

    @pytest.mark.parametrize("forged", ["forged.jwt.token", "a.b.c", "Bearer  "])
    def test_forged_claims_cannot_mint_a_new_bucket(self, monkeypatch, forged):
        """Only a VERIFIED subject becomes a bucket key."""
        from core.auth import AuthError

        def boom(*a, **k):
            raise AuthError("bad token")

        monkeypatch.setattr("core.rate_limit.principal_from_header", boom)
        key = client_identity(_request({"Authorization": f"Bearer {forged}"}))
        assert key.startswith("ip:")

    def test_no_auth_header_skips_verification_entirely(self, monkeypatch):
        """An anonymous request must not pay for a signature check it cannot pass."""
        def boom(*a, **k):
            raise AssertionError("verification should not be attempted")

        monkeypatch.setattr("core.rate_limit.principal_from_header", boom)
        assert client_identity(_request()) == "ip:10.0.0.1"


class TestShippedDefault:
    def test_default_is_the_specified_60_per_minute(self, monkeypatch):
        """The env override the suite installs must not hide the real default."""
        monkeypatch.delenv("RATE_LIMIT_PER_MINUTE", raising=False)
        assert Settings().rate_limit_per_minute == 60

    def test_shipped_decoration_uses_the_configured_limit(self):
        assert limit_string().endswith("/minute")
        assert limit_string().split("/")[0].isdigit()

    def test_test_ceiling_is_active_for_this_suite(self):
        """Guards the module-docstring reasoning from silently lapsing."""
        assert is_test_ceiling() or get_settings().rate_limit_per_minute == 60


class TestRegistration:
    def test_register_attaches_limiter_and_handler(self):
        app = register(FastAPI())
        assert app.state.limiter is not None
        assert app.exception_handlers[RateLimitExceeded] is rate_limit_exceeded_handler

    def test_registered_app_returns_429_through_the_handler(self):
        app = register(FastAPI())

        @app.get("/ping")
        @app.state.limiter.limit("1/minute")
        def ping(request: Request):
            return {"ok": True}

        c = TestClient(app)
        c.get("/ping")
        r = c.get("/ping")
        assert r.status_code == 429
        assert r.json()["error"] == "Rate limit exceeded"
