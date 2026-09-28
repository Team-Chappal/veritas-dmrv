"""
Stage 5.8 — authentication and authorisation.

The tests that matter here are the ADVERSARIAL ones: forged signature, expired
token, `alg: none`, wrong issuer, wrong audience, and — the one specific to this
scope design — a token that claims a role it was not granted. A suite that only
round-trips a valid token would pass against an implementation with no
verification at all.
"""

from __future__ import annotations

import datetime as dt
import time

import jwt
import pytest

from core.auth import (
    ALGORITHM,
    ALL_SCOPES,
    ANONYMOUS,
    ROLE_SCOPES,
    SCOPE_FIELD_UPLOAD,
    SCOPE_TRIAGE_REVIEW,
    SCOPE_VVB_SIGNOFF,
    AuthConfigurationError,
    AuthError,
    InsufficientScope,
    Principal,
    TokenError,
    auth_state,
    authorise,
    enforce_scope,
    decode_token,
    extract_bearer,
    issue_token,
    principal_from_header,
    require_scope,
    scope_grants,
    signing_key,
)
from core.config import Settings

pytestmark = pytest.mark.tier5

SECRET = "unit-test-signing-key-not-a-real-secret"


@pytest.fixture()
def settings() -> Settings:
    return Settings(jwt_secret=SECRET, app_env="development", jwt_ttl_seconds=3600)


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #


class TestIssueAndVerify:
    def test_round_trips(self, settings):
        p = decode_token(issue_token("vvb", "auditor@field.co", settings=settings), settings=settings)
        assert p.subject == "auditor@field.co"
        assert p.has_scope(SCOPE_VVB_SIGNOFF)
        assert p.role == "vvb"

    @pytest.mark.parametrize("role,scope", sorted(ROLE_SCOPES.items()))
    def test_each_role_maps_to_its_own_scope(self, settings, role, scope):
        p = decode_token(issue_token(role, settings=settings), settings=settings)
        assert p.has_scope(scope)

    def test_token_carries_a_unique_jti(self, settings):
        a = decode_token(issue_token("triage", settings=settings), settings=settings)
        b = decode_token(issue_token("triage", settings=settings), settings=settings)
        assert a.jti and a.jti != b.jti

    def test_extra_scopes_require_being_named(self, settings):
        p = decode_token(
            issue_token("field", settings=settings, extra_scopes=(SCOPE_TRIAGE_REVIEW,)),
            settings=settings,
        )
        assert p.has_scope(SCOPE_TRIAGE_REVIEW)

    def test_unknown_role_refused(self, settings):
        with pytest.raises(AuthError, match="Unknown role"):
            issue_token("admin", settings=settings)

    def test_unknown_extra_scope_refused(self, settings):
        with pytest.raises(AuthError, match="Unknown scope"):
            issue_token("field", settings=settings, extra_scopes=("mrv:god",))

    def test_ttl_cannot_exceed_the_configured_lifetime(self, settings):
        """Otherwise a sign-off token could be minted for a year."""
        claims = jwt.decode(
            issue_token("vvb", settings=settings, ttl_seconds=10**9),
            SECRET, algorithms=[ALGORITHM], audience=settings.jwt_audience,
        )
        assert claims["exp"] - claims["iat"] <= settings.jwt_ttl_seconds


# --------------------------------------------------------------------------- #
# No implicit escalation
# --------------------------------------------------------------------------- #


class TestNoPrivilegeEscalation:
    def test_vvb_cannot_upload(self, settings):
        """The core of the scope design: sign-off is not a superset of upload."""
        p = decode_token(issue_token("vvb", settings=settings), settings=settings)
        assert not p.has_scope(SCOPE_FIELD_UPLOAD)

    def test_field_cannot_review(self, settings):
        p = decode_token(issue_token("field", settings=settings), settings=settings)
        assert not p.has_scope(SCOPE_TRIAGE_REVIEW)

    def test_field_cannot_sign_off(self, settings):
        p = decode_token(issue_token("field", settings=settings), settings=settings)
        assert not p.has_scope(SCOPE_VVB_SIGNOFF)

    def test_triage_cannot_sign_off(self, settings):
        p = decode_token(issue_token("triage", settings=settings), settings=settings)
        assert not p.has_scope(SCOPE_VVB_SIGNOFF)

    def test_role_claim_restores_its_own_scope_when_stripped(self, settings):
        """A token cannot claim a role while omitting the scope it stands for."""
        token = issue_token("vvb", settings=settings)
        claims = jwt.decode(token, SECRET, algorithms=[ALGORITHM], audience=settings.jwt_audience)
        claims["scope"] = ""
        tampered = jwt.encode(claims, SECRET, algorithm=ALGORITHM)
        assert decode_token(tampered, settings=settings).has_scope(SCOPE_VVB_SIGNOFF)

    def test_authorise_raises_for_the_wrong_role(self, settings):
        field = decode_token(issue_token("field", settings=settings), settings=settings)
        with pytest.raises(InsufficientScope, match=SCOPE_TRIAGE_REVIEW):
            authorise(field, SCOPE_TRIAGE_REVIEW)

    def test_authorise_returns_the_principal_when_permitted(self, settings):
        vvb = decode_token(issue_token("vvb", settings=settings), settings=settings)
        assert authorise(vvb, SCOPE_VVB_SIGNOFF) is vvb

    def test_403_message_does_not_echo_the_token(self, settings):
        p = Principal(subject="u", scopes=frozenset())
        with pytest.raises(InsufficientScope) as exc:
            authorise(p, SCOPE_VVB_SIGNOFF)
        assert "eyJ" not in str(exc.value)

    def test_scope_grants_non_raising_form(self, settings):
        p = decode_token(issue_token("field", settings=settings), settings=settings)
        assert scope_grants(p, SCOPE_FIELD_UPLOAD)
        assert not scope_grants(p, SCOPE_VVB_SIGNOFF)


# --------------------------------------------------------------------------- #
# Forgery and tampering
# --------------------------------------------------------------------------- #


def _reissue(claims: dict, key: str = SECRET) -> str:
    return jwt.encode(claims, key, algorithm=ALGORITHM)


class TestForgeryRejected:
    def test_wrong_key_rejected(self, settings):
        forged = jwt.encode(
            {"sub": "attacker", "role": "vvb", "scope": SCOPE_VVB_SIGNOFF,
             "iat": int(time.time()), "exp": int(time.time()) + 600,
             "iss": settings.jwt_issuer, "aud": settings.jwt_audience, "jti": "x"},
            "attacker-key", algorithm=ALGORITHM,
        )
        with pytest.raises(TokenError):
            decode_token(forged, settings=settings)

    def test_alg_none_rejected(self, settings):
        """The classic unsigned-token attack."""
        unsigned = jwt.encode(
            {"sub": "attacker", "role": "vvb", "scope": SCOPE_VVB_SIGNOFF,
             "iat": int(time.time()), "exp": int(time.time()) + 600,
             "iss": settings.jwt_issuer, "aud": settings.jwt_audience, "jti": "x"},
            key="", algorithm="none",
        )
        with pytest.raises(TokenError):
            decode_token(unsigned, settings=settings)

    def test_token_signed_with_another_key_cannot_be_edited_in_place(self, settings):
        """Editing the scope of a real token invalidates it."""
        token = issue_token("field", settings=settings)
        claims = jwt.decode(token, SECRET, algorithms=[ALGORITHM], audience=settings.jwt_audience)
        claims["scope"] = SCOPE_VVB_SIGNOFF
        with pytest.raises(TokenError):
            decode_token(_reissue(claims, key="not-the-key"), settings=settings)

    def test_expired_token_rejected(self, settings):
        now = dt.datetime.now(dt.timezone.utc)
        expired = jwt.encode(
            {"sub": "o", "role": "vvb", "scope": SCOPE_VVB_SIGNOFF,
             "iat": int((now - dt.timedelta(hours=3)).timestamp()),
             "exp": int((now - dt.timedelta(hours=2)).timestamp()),
             "iss": settings.jwt_issuer, "aud": settings.jwt_audience, "jti": "x"},
            SECRET, algorithm=ALGORITHM,
        )
        with pytest.raises(TokenError, match="expired"):
            decode_token(expired, settings=settings)

    def test_wrong_issuer_rejected(self, settings):
        now = int(time.time())
        tok = jwt.encode(
            {"sub": "o", "role": "vvb", "scope": SCOPE_VVB_SIGNOFF, "iat": now,
             "exp": now + 600, "iss": "somebody-else", "aud": settings.jwt_audience, "jti": "x"},
            SECRET, algorithm=ALGORITHM,
        )
        with pytest.raises(TokenError):
            decode_token(tok, settings=settings)

    def test_wrong_audience_rejected(self, settings):
        now = int(time.time())
        tok = jwt.encode(
            {"sub": "o", "role": "vvb", "scope": SCOPE_VVB_SIGNOFF, "iat": now,
             "exp": now + 600, "iss": settings.jwt_issuer, "aud": "another-app", "jti": "x"},
            SECRET, algorithm=ALGORITHM,
        )
        with pytest.raises(TokenError):
            decode_token(tok, settings=settings)

    def test_missing_required_claim_rejected(self, settings):
        now = int(time.time())
        tok = jwt.encode(
            {"sub": "o", "role": "vvb", "iat": now, "exp": now + 600,
             "iss": settings.jwt_issuer, "aud": settings.jwt_audience},
            SECRET, algorithm=ALGORITHM,
        )
        with pytest.raises(TokenError):
            decode_token(tok, settings=settings)

    @pytest.mark.parametrize("token", ["", "   ", "not.a.jwt", "a.b", "...."])
    def test_junk_rejected(self, settings, token):
        with pytest.raises(TokenError):
            decode_token(token, settings=settings)

    def test_error_message_is_coarse(self, settings):
        """A detailed parse error tells an attacker which check failed."""
        try:
            decode_token("not.a.jwt", settings=settings)
        except TokenError as exc:
            assert str(exc) == "Token invalid."


# --------------------------------------------------------------------------- #
# Fails closed
# --------------------------------------------------------------------------- #


class TestFailsClosed:
    def test_production_without_a_key_raises(self):
        s = Settings(jwt_secret=None, app_env="production")
        with pytest.raises(AuthConfigurationError, match="production"):
            signing_key(s)

    def test_production_state_reports_not_enforced(self):
        state = auth_state(Settings(jwt_secret=None, app_env="production"))
        assert state["auth_enforced"] is False
        assert "production" in state["reason"]

    def test_production_never_falls_back_to_an_ephemeral_key(self):
        s = Settings(jwt_secret=None, app_env="production")
        with pytest.raises(AuthConfigurationError):
            signing_key(s)
        with pytest.raises(AuthConfigurationError):
            decode_token("a.b.c", settings=s)

    def test_development_gets_a_random_ephemeral_key(self):
        s = Settings(jwt_secret=None, app_env="development")
        state = auth_state(s)
        assert state["auth_enforced"] is True
        assert state["ephemeral_signing_key"] is True
        assert state["signing_key_configured"] is False

    def test_ephemeral_keys_differ_between_processes(self, monkeypatch):
        """No hardcoded default to forge."""
        import core.auth as auth

        auth._ephemeral_key.cache_clear()
        first = auth._ephemeral_key()
        auth._ephemeral_key.cache_clear()
        second = auth._ephemeral_key()
        assert first != second
        auth._ephemeral_key.cache_clear()

    def test_health_summary_never_contains_the_secret(self, settings):
        s = Settings(jwt_secret="super-secret-value", app_env="development")
        blob = str(s.public_summary())
        assert "super-secret-value" not in blob
        assert s.public_summary()["jwt_signing_key_configured"] is True

    def test_token_minting_unavailable_in_production(self):
        state = auth_state(Settings(jwt_secret="k", app_env="production"))
        assert state["token_minting_available"] is False

    def test_token_minting_available_in_development(self):
        state = auth_state(Settings(jwt_secret="k", app_env="development"))
        assert state["token_minting_available"] is True


# --------------------------------------------------------------------------- #
# Header parsing and dependencies
# --------------------------------------------------------------------------- #


class TestHeaderParsing:
    @pytest.mark.parametrize("header", [
        "Bearer abc.def.ghi", "bearer abc.def.ghi", "BEARER abc.def.ghi",
    ])
    def test_scheme_is_case_insensitive(self, header, settings):
        assert extract_bearer(header) == "abc.def.ghi"

    @pytest.mark.parametrize("header", [
        None, "", "abc.def.ghi", "Bearer", "Bearer   ", "Basic dXNlcjpwYXNz",
        "Token abc.def.ghi",
    ])
    def test_malformed_header_rejected(self, header):
        with pytest.raises(TokenError):
            extract_bearer(header)

    def test_principal_from_header(self, settings):
        token = issue_token("triage", settings=settings)
        p = principal_from_header(f"Bearer {token}", settings)
        assert p.has_scope(SCOPE_TRIAGE_REVIEW)

    def test_dependency_returns_anonymous_without_a_header(self, settings):
        dep = require_scope(SCOPE_TRIAGE_REVIEW, settings)
        assert dep(authorization=None) is ANONYMOUS
        assert not dep(authorization=None).is_authenticated

    def test_dependency_resolves_a_bearer_token(self, settings):
        dep = require_scope(SCOPE_VVB_SIGNOFF, settings)
        token = issue_token("vvb", settings=settings)
        assert dep(authorization=f"Bearer {token}").has_scope(SCOPE_VVB_SIGNOFF)

    def test_dependency_rejects_an_unknown_scope_at_build_time(self):
        with pytest.raises(AuthError, match="Unknown scope"):
            require_scope("mrv:overlord")

    def test_enforce_rejects_an_unknown_scope_at_build_time(self):
        """A typo'd scope must fail at wiring time, not authorise nothing."""
        with pytest.raises(AuthError, match="Unknown scope"):
            enforce_scope("mrv:overlord")

    def test_enforce_401s_without_a_token_and_403s_with_the_wrong_one(self, settings):
        dep = enforce_scope(SCOPE_TRIAGE_REVIEW, settings)
        with pytest.raises(TokenError):
            dep(authorization=None)
        with pytest.raises(TokenError):
            dep(authorization="   ")
        with pytest.raises(InsufficientScope):
            dep(authorization=f"Bearer {issue_token('field', settings=settings)}")

    def test_enforce_passes_a_matching_token(self, settings):
        dep = enforce_scope(SCOPE_TRIAGE_REVIEW, settings)
        p = dep(authorization=f"Bearer {issue_token('triage', settings=settings)}")
        assert p.has_scope(SCOPE_TRIAGE_REVIEW)


# --------------------------------------------------------------------------- #
# Scope vocabulary
# --------------------------------------------------------------------------- #


class TestScopeVocabulary:
    def test_exactly_three_scopes(self):
        assert len(ALL_SCOPES) == 3

    def test_role_map_is_one_to_one(self):
        """One-to-one is the property that makes escalation impossible."""
        assert len(ROLE_SCOPES) == 3
        assert len(set(ROLE_SCOPES.values())) == 3

    def test_every_scope_is_reachable_by_some_role(self):
        assert set(ROLE_SCOPES.values()) == set(ALL_SCOPES)

    def test_all_scopes_are_prefixed_as_specified(self):
        for scope in ALL_SCOPES:
            assert scope.startswith("mrv:"), scope
