"""
Application configuration.

Credential absence is a SUPPORTED state, not an error. Every Cloudinary-touching
stage must degrade to local fixtures so the stage demo cannot fail on a missing
API key. ``has_cloudinary_credentials`` is the single flag the rest of the
codebase branches on.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _env(*names: str, default: str | None = None) -> str | None:
    for n in names:
        v = os.getenv(n)
        if v:
            return v
    return default


@dataclass(frozen=True)
class Settings:
    app_env: str = field(default_factory=lambda: _env("APP_ENV", default="development"))
    app_url: str = field(default_factory=lambda: _env("APP_URL", default="http://localhost:8000"))

    cloudinary_cloud_name: str | None = field(
        default_factory=lambda: _env("CLOUDINARY_CLOUD_NAME", "NEXT_PUBLIC_CLOUDINARY_CLOUD_NAME")
    )
    cloudinary_api_key: str | None = field(default_factory=lambda: _env("CLOUDINARY_API_KEY"))
    cloudinary_api_secret: str | None = field(default_factory=lambda: _env("CLOUDINARY_API_SECRET"))

    c2pa_signing_private_key: str | None = field(
        default_factory=lambda: _env("C2PA_SIGNING_PRIVATE_KEY")
    )

    # --- Authentication (Stage 5) -------------------------------------------
    # NOTE the deliberate asymmetry with Cloudinary: a missing Cloudinary key
    # degrades to fixtures, but a missing JWT key must NOT degrade to
    # unauthenticated access. See core/auth.py — protected routes fail CLOSED.
    jwt_secret: str | None = field(default_factory=lambda: _env("VERITAS_JWT_SECRET"))
    jwt_issuer: str = field(default_factory=lambda: _env("JWT_ISSUER", default="veritas-dmrv"))
    jwt_audience: str = field(
        default_factory=lambda: _env("JWT_AUDIENCE", default="veritas-field")
    )
    #: 8h — one field shift. A VVB sign-off token should not outlive the day.
    jwt_ttl_seconds: int = field(
        default_factory=lambda: int(_env("JWT_TTL_SECONDS", default="28800") or 28800)
    )
    #: Spec S5.8: 60 req/min. Read at call time so a test can lower it.
    rate_limit_per_minute: int = field(
        default_factory=lambda: int(_env("RATE_LIMIT_PER_MINUTE", default="60") or 60)
    )

    demo_cache_enabled: bool = field(
        default_factory=lambda: (_env("DEMO_CACHE_ENABLED", default="true") or "").lower()
        in {"1", "true", "yes", "on"}
    )

    # Rubric-relevant tuning
    shadow_coherence_tolerance_deg: float = 12.0
    phash_duplicate_threshold: int = 12
    sift_inlier_ratio_floor: float = 0.60
    sift_inlier_ratio_target: float = 0.70
    homography_reproj_threshold_px: float = 3.0
    max_homography_condition_number: float = 1e6
    tps_condition_number_threshold: float = 85.0
    tps_residual_rmse_threshold_px: float = 3.5

    @property
    def has_cloudinary_credentials(self) -> bool:
        return bool(
            self.cloudinary_cloud_name and self.cloudinary_api_key and self.cloudinary_api_secret
        )

    @property
    def mode(self) -> str:
        return "live" if self.has_cloudinary_credentials else "fixture"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    def public_summary(self) -> dict:
        """Safe to log. Never contains a secret value."""
        return {
            "app_env": self.app_env,
            "mode": self.mode,
            "cloudinary_configured": self.has_cloudinary_credentials,
            "cloud_name": self.cloudinary_cloud_name or "<unset>",
            "c2pa_signing_configured": bool(self.c2pa_signing_private_key),
            "demo_cache_enabled": self.demo_cache_enabled,
            # Booleans only — the secret itself is never summarised.
            "jwt_signing_key_configured": bool(self.jwt_secret),
            "rate_limit_per_minute": self.rate_limit_per_minute,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
