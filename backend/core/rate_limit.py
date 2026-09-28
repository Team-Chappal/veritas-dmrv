"""
Request rate limiting.

S5.8 specifies 60 requests per minute. Two decisions are worth stating, because
both are ways a rate limiter silently stops limiting anything.

KEY ON THE AUTHENTICATED SUBJECT, NOT ONLY THE IP

An office behind one NAT shares a single egress address, so a pure IP limiter
either throttles the whole field team when one phone retries on a weak signal,
or gets raised until it stops throttling anyone. Keying on the verified subject
when a valid token is present gives each field officer their own budget, and
falls back to IP only for unauthenticated traffic — which is the traffic actually
worth limiting.

A token that fails verification falls back to IP rather than raising: the limiter
runs before route logic, and an exception here would turn every malformed
request into a 500 instead of a 401.

THE LIMIT IS CONFIGURED, AND THE TEST SUITE RAISES IT

The shipped default is the specified 60/min. The suite sets
``RATE_LIMIT_PER_MINUTE`` high in ``conftest.py``, because a global counter shared
across every test would make unrelated tests fail depending on execution order —
the worst possible property for a test suite. Enforcement is proven instead by
``test_rate_limit.py``, which builds its own limiter at a low limit and checks
the 429. So the *default* is untested and the *mechanism* is tested; that is the
trade, and it is deliberate.

ONE DEPLOYMENT FACT WORTH KNOWING

``get_remote_address`` reads ``request.client.host`` and nothing else — it does
NOT read ``X-Forwarded-For``. Behind a reverse proxy or load balancer every
request therefore arrives with the proxy's address, so unauthenticated traffic
collapses into a single bucket and the limit becomes all-or-nothing for the whole
deployment. That is the concrete reason authenticated traffic is keyed on subject
instead. A deployment that needs per-client IP limiting behind a proxy must
supply its own ``key_func``; do not assume the default is proxy-aware.
"""

from __future__ import annotations

import logging
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from core.auth import principal_from_header
from core.config import get_settings

log = logging.getLogger(__name__)

#: Below this many requests a minute, tests raise the ceiling; see module docstring.
_TEST_CEILING = 100_000

#: How long each limit granularity takes to refill, in seconds. This is the
#: window a Retry-After should advertise.
_GRANULARITY_SECONDS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}


def client_identity(request: Request) -> str:
    """Bucket key: verified subject, else the peer's address.

    Note the trust order: the subject is only used once a token has actually
    verified, so an attacker cannot mint unlimited buckets by forging claims.
    """
    authorization = request.headers.get("authorization")
    if authorization:
        try:
            principal = principal_from_header(authorization)
        except Exception:  # noqa: BLE001 - any failure means "not authenticated"
            principal = None
        if principal and principal.is_authenticated:
            return f"sub:{principal.subject}"
    return f"ip:{get_remote_address(request)}"


def limit_string() -> str:
    """The configured limit, in the form slowapi's decorator wants."""
    n = max(1, int(get_settings().rate_limit_per_minute))
    return f"{n}/minute"


def build_limiter(key_func: Callable[[Request], str] = client_identity) -> Limiter:
    return Limiter(key_func=key_func)


#: Module-level limiter, shared by the app's decorated routes.
limiter = build_limiter()


def rate_limited() -> Callable:
    """Decorator applying the configured per-minute limit to one route.

    A route using this must accept a ``request: Request`` parameter — slowapi
    reads the connection from it.
    """
    return limiter.limit(limit_string())


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """429 with a ``Retry-After`` header.

    slowapi's stock handler returns a bare 429 with no Retry-After, so a client
    that respects the header has no way to know when to come back and a client
    that ignores it just retries immediately — turning a throttle into a
    self-inflicted load amplifier. The header is derived from the limit window
    rather than from when this request happened to land.
    """
    retry_after = _retry_after_seconds(exc)
    return JSONResponse(
        status_code=429,
        content={"error": "Rate limit exceeded", "retry_after_seconds": retry_after},
        headers={"Retry-After": str(retry_after)},
    )


def _retry_after_seconds(exc: RateLimitExceeded, default_window: int = 60) -> int:
    """Seconds until the bucket refills, from the limit's own granularity.

    Read from ``GRANULARITY`` rather than from ``amount``: ``amount`` is the
    request BUDGET (5), not the window (60s for "5/minute"). An earlier version
    conflated the two and so reported 60s for every window, which was right only
    because the shipped limit happens to be per-minute.
    """
    item = getattr(getattr(exc, "limit", None), "limit", None)
    granularity = getattr(item, "GRANULARITY", None)
    if granularity is not None:
        seconds = _GRANULARITY_SECONDS.get(str(getattr(granularity, "name", granularity)))
        if seconds:
            return seconds
    return max(1, int(default_window))


def register(app: FastAPI) -> FastAPI:
    """Attach the limiter and its 429 handler to an app."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    return app


def is_test_ceiling() -> bool:
    """True when the suite has raised the limit out of the way."""
    return int(get_settings().rate_limit_per_minute) >= _TEST_CEILING
