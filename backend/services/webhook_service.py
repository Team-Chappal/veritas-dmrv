"""
VERITAS dMRV — Cloudinary Webhook Handling
==========================================

Cloudinary calls back when an upload finishes, when AI Video Analysis completes,
and when eager transformations are rendered. Three properties matter for a
platform whose webhooks can *write* verification metadata:

1. **Authenticity.** A webhook is an unauthenticated HTTP POST to a public URL.
   Anyone who learns the endpoint can POST a fabricated payload and mark a
   fraudulent asset as VERIFIED_PASS. So every notification is signature-verified
   before it is acted on, and an unverifiable payload is rejected outright
   rather than trusted-and-logged.

2. **Idempotency.** Cloudinary retries. The same notification arriving twice
   must not double-count an asset or re-apply a decision, so processed
   notification keys are remembered and replays are reported as duplicates
   rather than silently re-applied.

3. **Fail closed, degrade open.** Verification failure rejects. But a *missing*
   signature secret in fixture mode must not crash the demo, so
   :attr:`WebhookVerifier.requires_signature` is False when unconfigured and the
   reason is reported on every result.

SIGNATURE SCHEME — DELIBERATELY UNCONFIRMED
--------------------------------------------
Cloudinary signs notifications, and the exact construction has varied between
SDK versions and product tiers. Rather than assert one from memory — the error
that produced the allometric "correction" this project had to withdraw — the
scheme is a parameter, the algorithm is selectable, and
:func:`describe_scheme_uncertainty` says plainly that it must be confirmed
against Cloudinary's current documentation. ``scripts/validate_cloudinary_live.py``
prints the headers a real notification arrives with, so the scheme is settled by
observation on the first live run rather than by recall.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Optional

#: Header Cloudinary has used to carry a notification signature.
#: The scheme Cloudinary documents, from
#: cloudinary.com/documentation/notification_signatures:
#:
#:     signature = HEX( HASH( raw_body + X-Cld-Timestamp + api_secret ) )
#:
#: Three things this is NOT, all of which this module previously got wrong:
#:
#:   * not HMAC. It is a plain hash with the secret CONCATENATED ON, not keyed.
#:   * the timestamp is part of the signed string, and it lives in a HEADER, not
#:     the body -- so hashing the body alone can never be right.
#:   * the default digest is SHA-1, with SHA-256 also accepted.
#:
#: `hmac(secret, body)` would have rejected every genuine notification.
SCHEME_CLOUDINARY_DOCUMENTED = "cloudinary_documented"

#: Retained only so an old fixture or config naming still resolves rather than
#: raising on a string nobody remembers writing.
_LEGACY_SCHEME_ALIASES = {
    "body_plus_secret": SCHEME_CLOUDINARY_DOCUMENTED,
    "secret_plus_body": SCHEME_CLOUDINARY_DOCUMENTED,
    "plain_concat": SCHEME_CLOUDINARY_DOCUMENTED,
}

#: Cloudinary rejects a notification whose timestamp is older than this, in
#: seconds. Without a window, a captured signature replays forever.
DEFAULT_VALID_FOR_SECONDS = 7200

SIGNATURE_HEADERS = ("x-cld-signature", "x-cloudinary-signature")

#: Cloudinary also sends the timestamp in a header, and it is part of the signed
#: string, so it is read rather than parsed out of the body.
TIMESTAMP_HEADER = "x-cld-timestamp"

#: Default construction. Overridable because it is the one thing here that must
#: be confirmed against live traffic rather than assumed.
DEFAULT_SIGNATURE_SCHEME = SCHEME_CLOUDINARY_DOCUMENTED


class WebhookAction(str, Enum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    REJECTED_UNVERIFIED = "REJECTED_UNVERIFIED"
    REJECTED_MALFORMED = "REJECTED_MALFORMED"
    IGNORED_UNHANDLED = "IGNORED_UNHANDLED"


@dataclass
class WebhookResult:
    action: WebhookAction
    notification_type: str = ""
    public_id: str = ""
    reason: str = ""
    derived: dict = field(default_factory=dict)
    signature_checked: bool = False
    signature_scheme: str = ""

    @property
    def accepted(self) -> bool:
        return self.action == WebhookAction.ACCEPTED

    def to_dict(self) -> dict:
        d = asdict(self)
        d["action"] = self.action.value
        d["accepted"] = self.accepted
        return d




def compute_signature(
    body: bytes,
    secret: str,
    scheme: str = SCHEME_CLOUDINARY_DOCUMENTED,
    algorithm: str = "sha1",
    timestamp: str = "",
) -> str:
    """Compute a notification signature under the named scheme.

    ``timestamp`` is the raw ``X-Cld-Timestamp`` value. It is part of the signed
    string, so omitting it produces a signature that will never match a real
    notification -- which is why it is a named parameter rather than something
    a caller can forget.
    """
    if not secret:
        raise ValueError("A signature secret is required.")
    digest = getattr(hashlib, algorithm, None)
    if digest is None:
        raise ValueError(f"Unsupported signature algorithm: {algorithm}")

    scheme = _LEGACY_SCHEME_ALIASES.get(scheme, scheme)
    if scheme != SCHEME_CLOUDINARY_DOCUMENTED:
        raise ValueError(f"Unknown signature scheme: {scheme}")
    if not timestamp:
        raise ValueError(
            "timestamp is required: Cloudinary signs body + X-Cld-Timestamp + secret"
        )
    payload = body + str(timestamp).encode() + secret.encode()
    return digest(payload).hexdigest()


def verify_with_sdk(body: bytes, timestamp: str, signature: str, secret: str,
                    valid_for: int = DEFAULT_VALID_FOR_SECONDS) -> Optional[bool]:
    """Delegate to Cloudinary's own verifier when the SDK is importable.

    Preferred over :func:`compute_signature`, and the reason this module no longer
    has to be right about a security construction: the vendor ships a verifier,
    so reimplementing it is how the previous HMAC bug happened. Returns None when
    the SDK is absent, which is the caller's cue to use the local fallback.
    """
    try:
        import cloudinary
        import cloudinary.utils
    except Exception:  # noqa: BLE001 - any import problem means "not available"
        return None

    # The SDK verifier reads cloudinary.config().api_secret, NOT a secret passed
    # in. If a DEDICATED webhook API key is designated, the global secret is a
    # different one and the SDK would verify against the wrong key -- silently
    # rejecting every genuine notification. Fall back to the local path instead.
    configured = (cloudinary.config().api_secret or "")
    if not configured or not hmac.compare_digest(str(configured), str(secret)):
        return None

    try:
        return bool(
            cloudinary.utils.verify_notification_signature(
                # Two conversions, both load-bearing:
                #   body      -- the SDK raises ValueError on bytes.
                #   timestamp -- the SDK compares it numerically against
                #     time.time(), but then formats it into the signed string
                #     with '{}{}{}'. A float renders as '1759000000.0' and no
                #     longer matches the value Cloudinary actually sent, so
                #     every genuine notification would fail. int keeps both the
                #     comparison and the string form correct.
                body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body,
                int(float(timestamp)),
                signature,
                valid_for,
            )
        )
    except Exception:  # noqa: BLE001 - a verifier error is a failed verification
        return False


def describe_scheme_uncertainty() -> str:
    return (
        "The scheme is Cloudinary's documented construction: "
        "HEX(HASH(raw_body + X-Cld-Timestamp + api_secret)), SHA-1 by default. "
        "It is NOT HMAC, and the timestamp is part of the signed string. "
        "Verification delegates to cloudinary.utils."
        "verify_notification_signature when the SDK is importable. The scheme "
        "is still NOT confirmed against a real notification, because that needs "
        "a publicly reachable endpoint for Cloudinary to POST to; step 9 of "
        "scripts/validate_cloudinary_live.py reports the headers to watch for. "
        "Until that is done, treat signature verification as unverified and rely "
        "on the fixture-mode degradation."
    )


class WebhookVerifier:
    """Verifies notification signatures, with a fail-closed default."""

    def __init__(
        self,
        secret: Optional[str] = None,
        scheme: str = DEFAULT_SIGNATURE_SCHEME,
        algorithm: str = "sha1",
        valid_for: int = DEFAULT_VALID_FOR_SECONDS,
    ) -> None:
        self._secret = secret or None
        self._scheme = scheme
        self._algorithm = algorithm
        self._valid_for = int(valid_for)

    @property
    def requires_signature(self) -> bool:
        """False only when no secret is configured (fixture mode)."""
        return bool(self._secret)

    @property
    def scheme(self) -> str:
        return self._scheme

    def verify(self, body: bytes, headers: dict) -> tuple:
        """Return ``(ok, reason)``.

        Order matters. The timestamp is rejected as stale BEFORE the signature is
        checked, because a signature that verifies but is two hours old is a
        replay, and a replay is exactly what a captured request is.
        """
        if not self.requires_signature:
            return True, "no signature secret configured; verification skipped"

        lowered = {str(k).lower(): v for k, v in (headers or {}).items()}
        provided = next(
            (lowered[h] for h in SIGNATURE_HEADERS if lowered.get(h)), None
        )
        if not provided:
            return False, (
                f"no signature header present (looked for {list(SIGNATURE_HEADERS)})"
            )

        timestamp = str(lowered.get(TIMESTAMP_HEADER, "")).strip()
        if not timestamp:
            return False, (
                f"no {TIMESTAMP_HEADER} header. Cloudinary signs the body together "
                "with this value, so a signature cannot be checked without it."
            )
        stale = self._replay_reason(timestamp)
        if stale:
            return False, stale

        # Prefer the vendor's verifier: it is the reference implementation, and
        # reimplementing a security construction is what put HMAC in this file.
        sdk_result = verify_with_sdk(
            body, timestamp, str(provided), self._secret, self._valid_for
        )
        if sdk_result is not None:
            return (True, "signature verified (cloudinary SDK)") if sdk_result else \
                   (False, "signature mismatch (cloudinary SDK)")

        try:
            expected = compute_signature(
                body, self._secret, self._scheme, self._algorithm, timestamp
            )
        except ValueError as exc:
            return False, str(exc)

        if not hmac.compare_digest(str(provided), expected):
            return False, "signature mismatch"
        return True, "signature verified (local fallback)"

    def _replay_reason(self, timestamp: str) -> str:
        """Reject a notification outside the freshness window."""
        try:
            age = abs(time.time() - int(float(timestamp)))
        except (TypeError, ValueError):
            return f"{TIMESTAMP_HEADER} is not a unix timestamp: {timestamp!r}"
        if age > self._valid_for:
            return (
                f"notification is {int(age)}s old, outside the "
                f"{self._valid_for}s freshness window (possible replay)"
            )
        return ""


class WebhookProcessor:
    """Dispatches verified notifications into idempotent handlers."""

    def __init__(self, verifier: Optional[WebhookVerifier] = None) -> None:
        self.verifier = verifier or WebhookVerifier()
        self._seen: dict = {}
        self.results: list = []

    def notification_key(self, payload: dict, body: bytes) -> str:
        """Stable identity for a notification, for deduplication.

        Prefers an explicit notification id, then public_id + version, then a
        hash of the body. Cloudinary retries the same notification, so the key
        must survive a byte-identical resend.
        """
        payload = payload or {}
        for field_name in ("notification_id", "request_id"):
            if payload.get(field_name):
                return f"{field_name}:{payload[field_name]}"
        public_id = payload.get("public_id")
        if public_id:
            return f"asset:{public_id}:{payload.get('version', 'na')}"
        return "body:" + hashlib.sha256(body).hexdigest()[:24]

    def process(
        self, body: bytes, headers: Optional[dict] = None
    ) -> WebhookResult:
        """Verify, deduplicate, then dispatch."""
        import json

        ok, reason = self.verifier.verify(body, headers or {})
        if not ok:
            result = WebhookResult(
                action=WebhookAction.REJECTED_UNVERIFIED,
                reason=reason,
                signature_checked=True,
                signature_scheme=self.verifier.scheme,
            )
            self.results.append(result)
            return result

        try:
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            result = WebhookResult(
                action=WebhookAction.REJECTED_MALFORMED,
                reason=f"body is not valid JSON: {exc}",
                signature_checked=True,
                signature_scheme=self.verifier.scheme,
            )
            self.results.append(result)
            return result

        if not isinstance(payload, dict):
            result = WebhookResult(
                action=WebhookAction.REJECTED_MALFORMED,
                reason="payload is not a JSON object",
                signature_checked=True,
                signature_scheme=self.verifier.scheme,
            )
            self.results.append(result)
            return result

        key = self.notification_key(payload, body)
        notification_type = str(payload.get("notification_type") or "unknown")
        public_id = str(payload.get("public_id") or "")

        if key in self._seen:
            result = WebhookResult(
                action=WebhookAction.DUPLICATE,
                notification_type=notification_type,
                public_id=public_id,
                reason=f"already processed as {key}",
                signature_checked=True,
                signature_scheme=self.verifier.scheme,
            )
            self.results.append(result)
            return result

        handler = {
            "eager": self._handle_eager_ready,
            "upload": self._handle_upload,
            "video": self._handle_video_processed,
        }.get(notification_type)

        if handler is None:
            result = WebhookResult(
                action=WebhookAction.IGNORED_UNHANDLED,
                notification_type=notification_type,
                public_id=public_id,
                reason=f"no handler for notification_type={notification_type!r}",
                signature_checked=True,
                signature_scheme=self.verifier.scheme,
            )
            self.results.append(result)
            return result

        try:
            derived = handler(payload)
        except Exception as exc:
            result = WebhookResult(
                action=WebhookAction.REJECTED_MALFORMED,
                notification_type=notification_type,
                public_id=public_id,
                reason=f"handler failed: {type(exc).__name__}: {exc}",
                signature_checked=True,
                signature_scheme=self.verifier.scheme,
            )
            self.results.append(result)
            return result

        self._seen[key] = notification_type
        result = WebhookResult(
            action=WebhookAction.ACCEPTED,
            notification_type=notification_type,
            public_id=public_id,
            reason=reason,
            derived=derived,
            signature_checked=True,
            signature_scheme=self.verifier.scheme,
        )
        self.results.append(result)
        return result

    # -- handlers ---------------------------------------------------------- #

    def _handle_eager_ready(self, payload: dict) -> dict:
        transformations = payload.get("eager") or []
        return {
            "ready_transformations": [
                (t.get("transformation") if isinstance(t, dict) else str(t))
                for t in transformations
            ],
            "ready_count": len(transformations),
            "secure_url": payload.get("secure_url", ""),
        }

    def _handle_upload(self, payload: dict) -> dict:
        return {
            "resource_type": payload.get("resource_type", "image"),
            "format": payload.get("format", ""),
            "bytes": payload.get("bytes", 0),
            "secure_url": payload.get("secure_url", ""),
        }

    def _handle_video_processed(self, payload: dict) -> dict:
        """AI Video Analysis payload -> caption track plus player hotspots."""
        from services.video_service import (
            build_vtt,
            parse_google_video_tagging,
            segments_to_hotspots,
        )

        segments = parse_google_video_tagging(payload)
        derived = {
            "segment_count": len(segments),
            "tags": sorted({s.tag for s in segments}),
        }
        if segments:
            derived["vtt"] = build_vtt(segments)
            derived["hotspots"] = [
                h.to_dict() for h in segments_to_hotspots(segments)
            ]
        return derived
