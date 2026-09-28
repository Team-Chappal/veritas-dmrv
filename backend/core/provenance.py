"""
Provenance stamping (S5 exit criterion: every response carries the block).

Implemented as middleware rather than a per-route helper for one reason: a
helper has to be remembered, and the exit criterion is that NOBODY forgets. A
route added later and not stamped fails the exit criterion; a route added later
and stamped by hand is correct until the day someone forgets.

The block answers, for any response, without a second request: what mode this
was served in, when, which request, and where the underlying evidence lives. In
fixture mode it says so, because a provenance block on a fabricated response
that does not admit to being fabricated is worse than no block at all.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Callable

from fastapi import FastAPI, Request, Response

from core.config import Settings

log = logging.getLogger(__name__)

#: Key under which the block is attached. Underscore-prefixed to make obvious it
#: is envelope metadata rather than part of a route's own payload.
PROVENANCE_KEY = "_provenance"

#: Header a client can send to correlate its own records with ours.
REQUEST_ID_HEADER = "X-Request-Id"

#: Paths whose JSON is a contract with tooling rather than a payload for a human.
#: Stamping these makes generated clients wrong, which is a worse outcome than
#: one unstamped response.
_UNSTAMPED_PATHS = frozenset({"/openapi.json"})


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def build_block(
    *,
    request: Request,
    settings: Settings,
    request_id: str,
    started: float,
) -> dict:
    """The provenance block for one response."""
    return {
        "request_id": request_id,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": settings.mode,
        "evidence": (
            "live Cloudinary" if settings.has_cloudinary_credentials
            else "FIXTURE — synthetic, no Cloudinary call was made"
        ),
        "app_env": settings.app_env,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "path": request.url.path,
        "method": request.method,
        "provenance_endpoint": f"{settings.app_url.rstrip('/')}/api/v1/assets/{{public_id}}/provenance",
        "caveat": (
            ""
            if settings.has_cloudinary_credentials
            else "Figures in this response are fixtures. Run "
                 "scripts/validate_cloudinary_live.py to exercise the live paths."
        ),
    }


def stamp(payload: Any, block: dict) -> Any:
    """Attach the block to a JSON body.

    Only dicts are stamped. A list or a string response is left alone rather
    than being reshaped into ``{"data": ...}``, which would silently break any
    client already reading the array.
    """
    if not isinstance(payload, dict) or PROVENANCE_KEY in payload:
        return payload
    return {**payload, PROVENANCE_KEY: block}


def provenance_middleware(
    app: FastAPI, settings: Settings | None = None
) -> Callable:
    """Build the ASGI middleware. Exposed for tests without a live server."""

    async def middleware(request: Request, call_next: Callable) -> Response:
        from core.config import get_settings

        cfg = settings or get_settings()
        started = time.perf_counter()
        request_id = request.headers.get(REQUEST_ID_HEADER) or new_request_id()
        request.state.request_id = request_id

        response = await call_next(request)

        # FastAPI's schema document is consumed by code generators, not humans,
        # and an extra top-level key there is schema pollution. Docs endpoints
        # are static and carry nothing worth stamping.
        if request.url.path in _UNSTAMPED_PATHS:
            response.headers[REQUEST_ID_HEADER] = request_id
            return response

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type or response.status_code >= 400:
            # Errors keep their own shape: a 401 must not grow a body field that
            # a client might mistake for a successful payload.
            response.headers[REQUEST_ID_HEADER] = request_id
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk if isinstance(chunk, bytes) else str(chunk).encode()

        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            response.headers[REQUEST_ID_HEADER] = request_id
            return response

        stamped = json.dumps(
            stamp(payload, build_block(request=request, settings=cfg,
                                       request_id=request_id, started=started))
        ).encode()

        headers = dict(response.headers)
        headers["content-length"] = str(len(stamped))
        headers[REQUEST_ID_HEADER] = request_id
        return Response(
            content=stamped,
            status_code=response.status_code,
            headers=headers,
            media_type=response.headers.get("content-type"),
        )

    return middleware


def register(app: FastAPI, settings: Settings | None = None) -> FastAPI:
    app.middleware("http")(provenance_middleware(app, settings))
    return app
