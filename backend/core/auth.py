"""
Authentication and authorisation for field capture, triage and sign-off.

Three scopes, matching the three real jobs in a monitoring, reporting and
verification workflow:

    mrv:field_upload    a field officer attaching evidence
    mrv:triage_review   an analyst reviewing and annotating
    mrv:vvb_signoff     a verification body signing a project off

There is deliberately NO implicit escalation between them. A token carrying
``mrv:vvb_signoff`` cannot upload, and a field token cannot sign off. Role
hierarchies feel convenient right up until the day they are the vulnerability,
because a check written against the wrong link in the chain silently grants
everything above it.

THE ASYMMETRY WITH CLOUDINARY, AND WHY IT MATTERS

Every other credential in this codebase degrades to fixtures when absent, because
a missing API key must not fail a demo. That is the wrong trade for auth: if the
signing key is missing, protected routes must fail CLOSED with 503 rather than
degrade open to "anyone may sign off". A demo that runs unauthenticated is fine; a
verification system that runs unauthenticated in production is a legal liability.
The degradation is therefore loud — :func:`auth_state` reports it and
``/health`` surfaces it.

No public token endpoint is mounted in production. A route that mints a valid
token is a full authentication bypass, so in development only, the dev helper
issues tokens; a real deployment puts an OIDC provider in front of this module
and never calls :func:`issue_token` at all.
"""

from __future__ import annotations

import datetime as dt
import logging
import secrets
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable

import jwt

from core.config import Settings, get_settings

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Scopes
# --------------------------------------------------------------------------- #

SCOPE_FIELD_UPLOAD = "mrv:field_upload"
SCOPE_TRIAGE_REVIEW = "mrv:triage_review"
SCOPE_VVB_SIGNOFF = "mrv:vvb_signoff"

ALL_SCOPES: frozenset[str] = frozenset(
    {SCOPE_FIELD_UPLOAD, SCOPE_TRIAGE_REVIEW, SCOPE_VVB_SIGNOFF}
)

#: Role -> the single scope that role grants. One-to-one by design.
ROLE_SCOPES: dict[str, str] = {
    "field": SCOPE_FIELD_UPLOAD,
    "triage": SCOPE_TRIAGE_REVIEW,
    "vvb": SCOPE_VVB_SIGNOFF,
}

ALGORITHM = "HS256"
#: Pinned on decode. The token's own `alg` header is never trusted, which is
#: what closes the `alg: none` and RS256->HS256 confusion attacks.
_DECODE_ALGORITHMS = [ALGORITHM]

#: Small, deliberate clock-skew allowance. Generous leeway is a replay window.
LEEWAY_SECONDS = 5


class AuthError(Exception):
    """Base for every auth failure. Callers map these to HTTP statuses."""


class AuthConfigurationError(AuthError):
    """No signing key available. Fails CLOSED."""


class TokenError(AuthError):
    """The token is absent, malformed, expired or signed by someone else."""


class InsufficientScope(AuthError):
    """Valid token, wrong role for this route."""


# --------------------------------------------------------------------------- #
# Signing key
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def _ephemeral_key() -> str:
    """A random per-process key used ONLY outside production.

    Deliberately not a hardcoded development secret: a published default key is
    a forgeable token waiting to be deployed by accident. The cost is that
    tokens do not survive a restart, which no field app should want anyway.
    """
    key = secrets.token_urlsafe(48)
    log.warning(
        "VERITAS_JWT_SECRET is unset; using a random per-process signing key. "
        "Tokens will not survive a restart and cannot be minted by another process."
    )
    return key


def signing_key(settings: Settings | None = None) -> str:
    """Return the signing key, or raise :class:`AuthConfigurationError`.

    Production with no configured key is an error rather than a fallback: there
    is no safe default to invent, and inventing one is the bug this guards.
    """
    s = settings or get_settings()
    if s.jwt_secret:
        return s.jwt_secret
    if s.is_production:
        raise AuthConfigurationError(
            "VERITAS_JWT_SECRET is not set in production. Refusing to serve "
            "protected routes rather than accepting unauthenticated writes."
        )
    return _ephemeral_key()


def auth_state(settings: Settings | None = None) -> dict:
    """Deployment-visible auth posture. Contains booleans, never secrets."""
    s = settings or get_settings()
    try:
        signing_key(s)
        reason = ""
    except AuthConfigurationError as exc:
        reason = str(exc)
    return {
        "auth_enforced": not reason,
        "signing_key_configured": bool(s.jwt_secret),
        "ephemeral_signing_key": bool(not s.jwt_secret and not s.is_production),
        "token_minting_available": not s.is_production,
        "app_env": s.app_env,
        "reason": reason,
    }


# --------------------------------------------------------------------------- #
# Principal
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Principal:
    """Who is calling, and what they are allowed to do."""

    subject: str
    scopes: frozenset[str] = field(default_factory=frozenset)
    role: str | None = None
    jti: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return bool(self.subject)

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def missing(self, required: str) -> str:
        """Human-readable 403 body. Never echoes the token."""
        return (
            f"Scope {required} required. "
            f"This token carries: {sorted(self.scopes) or ['none']}."
        )


ANONYMOUS = Principal(subject="", scopes=frozenset())


# --------------------------------------------------------------------------- #
# Issue / verify
# --------------------------------------------------------------------------- #

_REQUIRED_CLAIMS = ["sub", "role", "scope", "exp", "iat", "iss", "aud", "jti"]


def issue_token(
    role: str,
    subject: str | None = None,
    *,
    ttl_seconds: int | None = None,
    extra_scopes: tuple[str, ...] = (),
    settings: Settings | None = None,
) -> str:
    """Mint a token for ``role``. One role -> exactly one scope.

    Callers needing a second scope pass ``extra_scopes`` explicitly; nothing is
    granted implicitly. The TTL is capped at the configured lifetime so a
    sign-off token cannot be minted for a year by passing ``ttl_seconds``.
    """
    s = settings or get_settings()
    if role not in ROLE_SCOPES:
        raise AuthError(f"Unknown role {role!r}. Known: {sorted(ROLE_SCOPES)}")

    ttl = int(ttl_seconds if ttl_seconds is not None else s.jwt_ttl_seconds)
    ttl = max(1, min(ttl, s.jwt_ttl_seconds))

    scopes = {ROLE_SCOPES[role], *extra_scopes}
    unknown = scopes - ALL_SCOPES
    if unknown:
        raise AuthError(f"Unknown scope(s): {sorted(unknown)}")

    now = dt.datetime.now(dt.timezone.utc)
    claims = {
        "sub": subject or f"{role}@veritas.local",
        "role": role,
        # Space-delimited per RFC 8693 / OAuth 2.0 practice.
        "scope": " ".join(sorted(scopes)),
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(seconds=ttl)).timestamp()),
        "iss": s.jwt_issuer,
        "aud": s.jwt_audience,
        "jti": secrets.token_urlsafe(12),
    }
    return jwt.encode(claims, signing_key(s), algorithm=ALGORITHM)


def decode_token(token: str, *, settings: Settings | None = None) -> Principal:
    """Verify a token and return its Principal.

    Every check the library gives us is enabled explicitly rather than relying
    on defaults, because a future library default change should not silently
    relax verification. Signature comparison is constant-time inside PyJWT
    (``hmac.compare_digest``), so a wrong signature leaks no timing signal.
    """
    s = settings or get_settings()
    if not token or not token.strip():
        raise TokenError("No bearer token supplied.")

    try:
        claims = jwt.decode(
            token,
            signing_key(s),
            algorithms=_DECODE_ALGORITHMS,
            audience=s.jwt_audience,
            issuer=s.jwt_issuer,
            leeway=LEEWAY_SECONDS,
            options={
                "require": _REQUIRED_CLAIMS,
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token expired.") from exc
    except jwt.InvalidTokenError as exc:
        # Deliberately coarse: the detail belongs in the log, not the response.
        log.info("Token rejected: %s", exc.__class__.__name__)
        raise TokenError("Token invalid.") from exc

    scopes = frozenset(str(claims.get("scope", "")).split())
    role = claims.get("role")
    if role in ROLE_SCOPES:
        # A role's own scope is implied by the claim carrying that role, so a
        # token cannot claim a role while omitting the scope it stands for.
        scopes = scopes | {ROLE_SCOPES[role]}

    return Principal(
        subject=str(claims["sub"]),
        scopes=scopes,
        role=role,
        jti=claims.get("jti"),
    )


# --------------------------------------------------------------------------- #
# FastAPI dependencies
# --------------------------------------------------------------------------- #


def extract_bearer(authorization: str | None) -> str:
    """Pull the token out of an ``Authorization: Bearer <token>`` header."""
    if not authorization:
        raise TokenError("Authorization header absent.")
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise TokenError("Expected 'Authorization: Bearer <token>'.")
    return parts[1].strip()


def principal_from_header(authorization: str | None, settings: Settings | None = None) -> Principal:
    """Resolve the caller. Raises :class:`AuthError` subclasses on failure."""
    return decode_token(extract_bearer(authorization), settings=settings)


def require_scope(
    scope: str, settings: Settings | None = None
) -> Callable[..., Principal]:
    """Build a FastAPI dependency that enforces ``scope``.

    An absent token yields the anonymous principal so public routes can share
    this one function; a route that requires a scope checks it explicitly.

    ``settings`` is captured at BUILD time rather than as a parameter, because
    FastAPI would otherwise try to read a ``Settings`` dataclass off the request
    as a query parameter. Routes leave it None and resolve the global singleton;
    tests inject a fixed key.
    """
    if scope not in ALL_SCOPES:
        raise AuthError(f"Unknown scope {scope!r}")

    def dependency(authorization: str | None = None) -> Principal:
        if not authorization:
            return ANONYMOUS
        return principal_from_header(authorization, settings)

    dependency.__name__ = f"require_{scope.replace(':', '_').replace('-', '_')}"
    return dependency


def authorise(principal: Principal, scope: str) -> Principal:
    """Raise unless ``principal`` carries ``scope``."""
    if not principal.has_scope(scope):
        raise InsufficientScope(principal.missing(scope))
    return principal


def scope_grants(principal: Principal, scope: str) -> bool:
    """Non-raising form, for filters that should hide rather than 403."""
    return principal.has_scope(scope)
