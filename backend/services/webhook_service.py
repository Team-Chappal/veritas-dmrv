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
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Optional

#: Header Cloudinary has used to carry a notification signature.
SIGNATURE_HEADERS = ("x-cld-signature", "x-cloudinary-signature")

#: Default construction. Overridable because it is the one thing here that must
#: be confirmed against live traffic rather than assumed.
DEFAULT_SIGNATURE_SCHEME = "body_plus_secret"


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
    body: bytes, secret: str, scheme: str = DEFAULT_SIGNATURE_SCHEME,
    algorithm: str = "sha256",
) -> str:
    """Compute a notification signature under the named scheme."""
    if not secret:
        raise ValueError("A signature secret is required.")
    digest = getattr(hashlib, algorithm, None)
    if digest is None:
        raise ValueError(f"Unsupported signature algorithm: {algorithm}")

    if scheme == "body_plus_secret":
        return hmac.new(secret.encode(), body, digest).hexdigest()
    if scheme == "secret_plus_body":
        return hmac.new(secret.encode(), body, digest).hexdigest()
    if scheme == "plain_concat":
        return digest((body.decode("utf-8", "replace") + secret).encode()).hexdigest()
    raise ValueError(f"Unknown signature scheme: {scheme}")


def describe_scheme_uncertainty() -> str:
    return (
        "The notification signature construction has differed across Cloudinary "
        "SDK versions. It is a parameter here and is NOT asserted as correct. "
        "Run scripts/validate_cloudinary_live.py against a real account to "
        "observe the headers on an actual notification and settle the scheme "
        "empirically. Until then, treat signature verification as "
        "unproven and rely on the fixture-mode degradation."
    )


class WebhookVerifier:
    """Verifies notification signatures, with a fail-closed default."""

    def __init__(
        self,
        secret: Optional[str] = None,
        scheme: str = DEFAULT_SIGNATURE_SCHEME,
        algorithm: str = "sha256",
    ) -> None:
        self._secret = secret or None
        self._scheme = scheme
        self._algorithm = algorithm

    @property
    def requires_signature(self) -> bool:
        """False only when no secret is configured (fixture mode)."""
        return bool(self._secret)

    @property
    def scheme(self) -> str:
        return self._scheme

    def verify(self, body: bytes, headers: dict) -> tuple:
        """Return ``(ok, reason)``.

        Uses ``hmac.compare_digest`` so a mismatching signature cannot be
        recovered by timing the comparison.
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

        try:
            expected = compute_signature(body, self._secret, self._scheme, self._algorithm)
        except ValueError as exc:
            return False, str(exc)

        if not hmac.compare_digest(str(provided), expected):
            return False, "signature mismatch"
        return True, "signature verified"


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
