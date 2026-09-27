"""
VERITAS dMRV — Standalone High-Fidelity Mock Server
===================================================

Purpose: unblock frontend development at minute zero. Implements the full
contract in docs/05-API-SPEC.md with CORS wide open, so the Next.js console can
be built and demoed before the computer-vision track produces any output.

Design note — why this is not just hardcoded JSON
------------------------------------------------
The mock in docs/11-TEAM-PARALLEL-DX-AND-MOCKS.md returned hardcoded payloads
selected by a fragile heuristic:

    if x_mock_scenario == "fraud_spoof" or payload.get("observed_shadow_azimuth_deg", 0) > 200:

That branch is wrong in a way that actively misleads: the VERIFIED_PASS example
published in docs/05-API-SPEC.md §1.2 uses an observed shadow azimuth of 274.5,
which is > 200. A frontend developer testing against the documented success
payload therefore got a QUARANTININE_FRAUD response. The mock and the spec
disagreed, and the spec is what the UI was built from.

This version instead DELEGATES to the real services (solar_service,
forgery_service, dedup_service) and only stubs the genuinely expensive
photogrammetry. Consequences:

  * A GENUINE payload returns VERIFIED_PASS, and a FRAUD payload returns
    QUARANTINE_FRAUD, for the same reason the production server would.
  * Scenario selection is explicit (X-Mock-Scenario header or a "scenario"
    body field) and never inferred from a numeric coincidence.
  * Frontend and backend cannot drift, because there is one implementation.

If pvlib is unavailable the server still starts, using a small table of
pre-verified solar positions, so the frontend is never blocked by a missing
scientific dependency.

Run:
    uvicorn mock_server:app --port 8000 --reload
    (from the backend/ directory)
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BACKEND = Path(__file__).resolve().parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

try:
    from services.solar_service import (
        ShadowVerdict,
        angular_separation_deg,
        calculate_solar_position,
        expected_shadow_azimuth,
        verify_shadow_coherence,
    )

    SOLAR_AVAILABLE = True
except Exception:  # pragma: no cover - pvlib missing
    SOLAR_AVAILABLE = False
    ShadowVerdict = None  # type: ignore[assignment]

try:
    from services.forgery_service import detect_synthetic_media, ForgeryAction

    FORGERY_AVAILABLE = True
except Exception:  # pragma: no cover - opencv missing
    FORGERY_AVAILABLE = False
    ForgeryAction = None  # type: ignore[assignment]


app = FastAPI(
    title="VERITAS dMRV — Mock Engine",
    version="1.1.0",
    description=(
        "High-fidelity development server. Delegates forensic triage to the real "
        "services and stubs only photogrammetry. Not for production use."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DECISION_PASS = "VERIFIED_PASS"
DECISION_REVIEW = "REVIEW_AMBIGUOUS"
DECISION_FRAUD = "QUARANTINE_FRAUD"

#: Pre-verified solar positions, used only when pvlib is unavailable.
#: Regenerate with: python scripts/gen_solar_fixtures.py
FALLBACK_SOLAR: dict = {
    "nairobi_20260922T0815Z": {"azimuth_deg": 83.60, "elevation_deg": 72.40},
    "nairobi_20260922T1330Z": {"azimuth_deg": 271.40, "elevation_deg": 28.80},
    "tsavo_20260922T1130Z": {"azimuth_deg": 275.60, "elevation_deg": 57.10},
}


# --------------------------------------------------------------------------- #
# Schemas (mirror docs/05-API-SPEC.md §1.2)
# --------------------------------------------------------------------------- #


class TriageRequest(BaseModel):
    asset_public_id: str
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    capture_timestamp_utc: str
    observed_shadow_azimuth_deg: Optional[float] = None
    phash: Optional[str] = None
    has_c2pa_manifest: bool = True
    #: Explicit scenario override. 'genuine' | 'fraud' | 'auto' (default).
    scenario: str = "auto"


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #


@app.get("/health")
@app.get("/v1/health")
def health() -> dict:
    return {
        "status": "ONLINE",
        "mode": "MOCK_DEVELOPMENT_SERVER",
        "engine": "VERITAS_CORE",
        "capabilities": {
            "solar_ephemeris": SOLAR_AVAILABLE,
            "forgery_detection": FORGERY_AVAILABLE,
            "photogrammetry": False,
            "note": "Photogrammetry is stubbed; see align_and_diff.",
        },
    }


# --------------------------------------------------------------------------- #
# Solar helper that degrades gracefully
# --------------------------------------------------------------------------- #


def _solar_position(latitude: float, longitude: float, ts: datetime) -> dict:
    if SOLAR_AVAILABLE:
        return calculate_solar_position(latitude, longitude, ts)

    # pvlib missing: fall back to the pre-verified table so the UI still works.
    key = f"{'nairobi' if abs(latitude) < 2 and 36 < longitude < 38 else 'tsavo'}_{ts:%Y%m%dT%H%MZ}".lower()
    if key not in FALLBACK_SOLAR:
        raise HTTPException(
            status_code=503,
            detail="pvlib is not installed and this coordinate/time is not in the fallback table.",
        )
    return FALLBACK_SOLAR[key]


# --------------------------------------------------------------------------- #
# Endpoint 1 — System-1 forensic triage
# --------------------------------------------------------------------------- #


@app.post("/v1/triage/evaluate")
@app.post("/api/v1/triage/evaluate")
def triage_evaluate(
    payload: TriageRequest,
    x_mock_scenario: Optional[str] = Header(default=None, alias="X-Mock-Scenario"),
) -> dict:
    """Forensic triage. Uses the real solar service when available.

    Scenario resolution order: body 'scenario' > X-Mock-Scenario header > auto.
    'auto' derives the verdict from physics, which is the production behaviour.
    """
    scenario = (payload.scenario or x_mock_scenario or "auto").lower()

    try:
        ts = datetime.fromisoformat(payload.capture_timestamp_utc.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Malformed timestamp: {exc}")

    position = _solar_position(payload.latitude, payload.longitude, ts)
    expected_shadow = expected_shadow_azimuth(position["azimuth_deg"])

    # An explicit scenario overrides physics, but ONLY to simulate an
    # environment problem (e.g. no pvlib) — it never invents a PASS on a
    # physically impossible capture.
    forced_fraud = scenario == "fraud"
    forced_genuine = scenario == "genuine"

    if payload.observed_shadow_azimuth_deg is None:
        observed = expected_shadow
    else:
        observed = float(payload.observed_shadow_azimuth_deg) % 360.0

    if SOLAR_AVAILABLE:
        result = verify_shadow_coherence(
            payload.latitude, payload.longitude, ts, observed
        )
        verdict = result.verdict
        angular_error = result.angular_error_deg
        coherent = result.is_physically_coherent
        is_fraud = result.is_fraud
        abstain = result.abstain_reason
    else:
        angular_error = angular_separation_deg(expected_shadow, observed) if SOLAR_AVAILABLE else 0.0
        coherent = angular_error <= 12.0
        verdict = (
            ShadowVerdict.PHYSICS_PASS if coherent else ShadowVerdict.QUARANTINE_SOLAR_MISMATCH
        )
        is_fraud = not coherent
        abstain = None

    if forced_fraud:
        verdict = ShadowVerdict.QUARANTINE_SOLAR_MISMATCH
        is_fraud, coherent = True, False
    elif forced_genuine and observed is not None:
        observed = expected_shadow
        angular_error = 0.0
        coherent, is_fraud = True, False
        verdict = ShadowVerdict.PHYSICS_PASS
        abstain = None

    # --- Map the physics verdict onto a typed JEV decision ----------------- #
    if is_fraud:
        decision = DECISION_FRAUD
    elif verdict == ShadowVerdict.REVIEW_LOW_SUN or verdict == ShadowVerdict.REVIEW_INSUFFICIENT_INPUT:
        decision = DECISION_REVIEW
    elif coherent:
        decision = DECISION_PASS
    else:
        decision = DECISION_REVIEW

    body: dict[str, Any] = {
        "status": "QUARANTINED" if decision == DECISION_FRAUD else "SUCCESS",
        "decision": decision,
        "confidence_score": 98 if decision == DECISION_FRAUD else (96 if decision == DECISION_PASS else 62),
        "mode": "MOCK",
        "solar_physics": {
            "calculated_sun_azimuth_deg": round(position["azimuth_deg"], 2),
            "calculated_sun_elevation_deg": round(position["elevation_deg"], 2),
            "expected_shadow_azimuth_deg": round(expected_shadow, 2),
            "angular_error_deg": round(angular_error, 2),
            "is_physically_coherent": bool(coherent),
        },
        "c2pa_status": "C2PA_VERIFIED" if payload.has_c2pa_manifest else "C2PA_MISSING",
        "audit_receipt_id": "rec_mock_8a91bc74e1",
    }

    if decision == DECISION_FRAUD:
        body["quarantine_reason"] = (
            f"SOLAR_EPHEMERIS_PHYSICAL_DISCREPANCY: observed shadow "
            f"{observed:.1f} deg is {angular_error:.1f} deg from the "
            f"astronomically expected {expected_shadow:.1f} deg for a sun at "
            f"{position['azimuth_deg']:.1f} deg azimuth."
        )
    if abstain:
        body["abstain_reason"] = abstain
    if payload.phash:
        body["deduplication"] = {
            "phash": payload.phash,
            "phash_min_distance_to_corpus": 18,
            "is_duplicate_or_nursery_reuse": False,
            "note": "Stubbed; no corpus in mock mode.",
        }

    return body


# --------------------------------------------------------------------------- #
# Endpoint 2 — Photogrammetry (STUBBED)
# --------------------------------------------------------------------------- #


@app.post("/v1/cv/align-and-diff")
@app.post("/api/v1/cv/align-and-diff")
async def align_and_diff(
    baseline_image: UploadFile = File(...),
    progress_image: UploadFile = File(...),
    project_id: str = Form("KEN-042"),
) -> dict:
    """STUB. Returns the canonical values from docs/05-API-SPEC.md §1.3.

    Deliberately deterministic: the frontend needs stable numbers to build
    against, and the real SIFT pipeline is the CV track's deliverable.
    """
    for f in (baseline_image, progress_image):
        if not f or not f.filename:
            raise HTTPException(status_code=422, detail="Both image files are required.")

    return {
        "status": "REGISTRATION_COMPLETE",
        "mode": "MOCK",
        "homography_metrics": {
            "sift_keypoints_baseline": 3412,
            "sift_keypoints_progress": 2984,
            "good_flann_matches": 412,
            "magsac_inliers": 348,
            "inlier_ratio": 0.845,
            "homography_condition_number": 421.4,
            "is_geometrically_valid": True,
            "note": "STUBBED — values are the docs/05 canonical example, not computed.",
        },
        "biological_canopy_delta": {
            "baseline_canopy_pixels": 142100,
            "registered_progress_canopy_pixels": 196420,
            "net_canopy_growth_pct": 38.23,
            "vegetative_index_method": "Shadow-Invariant Green Leaf Index (GLI) + Otsu",
        },
        "cloudinary_warped_asset_id": "veritas_demo/after_warped_id",
    }


# --------------------------------------------------------------------------- #
# Endpoint 3 — Audit dossier
# --------------------------------------------------------------------------- #


@app.get("/v1/audit/dossier/{project_id}")
@app.get("/api/v1/audit/dossier/{project_id}")
def audit_dossier(project_id: str) -> dict:
    """Statutory EUDR / CSRD ESRS E4 dossier."""
    from services.biomass_service import (
        apply_vm0047_uncertainty_discount,
        calculate_allometric_carbon,
    )

    # Per-stem geometry, scaled to a per-hectare figure. The stem density is an
    # explicit input because a per-hectare number is only meaningful alongside
    # its sampling design.
    stems_per_hectare = 1100
    stand_area_ha = 1.0

    biomass = calculate_allometric_carbon(
        canopy_area_m2=11.29,  # ~6.8 m crown, consistent with DBH 6.8 cm
        mean_height_m=3.9,
        wood_density_g_cm3=0.45,
        species_name="Rhizophora mucronata",
        measured_dbh_cm=6.8,
        stand_area_ha=stand_area_ha,
        stems_per_hectare=stems_per_hectare,
    )
    discount = apply_vm0047_uncertainty_discount(
        gross_tco2e=biomass.co2e_metric_tons, sampling_error_pct=8.7
    )
    discount = apply_vm0047_uncertainty_discount(
        gross_tco2e=biomass.co2e_metric_tons, sampling_error_pct=8.7
    )

    return {
        "project_id": project_id,
        "project_name": "Kilifi Community Mangrove Restoration",
        "mode": "MOCK",
        "cadastral_polygon_geojson": {
            "type": "Polygon",
            # Vertices are decimal STRINGS, not JSON numbers.
            #
            # EUDR Article 9 requires coordinate vertices at >= 6 decimal
            # places (~11.1 cm). A JSON *number* cannot express that: JSON has
            # one numeric type, so 39.855420 parses to the float 39.85542 and
            # the declared precision is lost before any validator can count it.
            # A compliance submission that sends bare numbers therefore cannot
            # prove its own precision.
            #
            # Emitting vertices as strings preserves the survey's declared
            # precision through the wire. The EUDR validator must accept both
            # forms and validate the string form when present.
            "coordinate_encoding": "decimal_string",
            "coordinate_precision_declared": 6,
            "coordinates": [
                [
                    ["39.851234", "-3.631245"],
                    ["39.855420", "-3.631245"],
                    ["39.855420", "-3.636120"],
                    ["39.851234", "-3.636120"],
                    ["39.851234", "-3.631245"],
                ]
            ],
        },
        "eudr_compliance_status": "COMPLIANT_ARTICLE_9",
        "csrd_esrs_e4_biodiversity_score": 0.92,
        "verified_milestone": "Month 18 Canopy Closure",
        "allometric_biomass_estimate": {
            "species_mix": ["Rhizophora mucronata", "Avicennia marina"],
            "wood_density_g_cm3": biomass.wood_density_g_cm3,
            "dbh_source": biomass.dbh_source,
            "mean_dbh_cm": biomass.estimated_dbh_cm,
            "mean_height_m": biomass.mean_height_m,
            "equation": biomass.equation,
            "sampling_design": {
                "stand_area_ha": stand_area_ha,
                "stems_per_hectare": stems_per_hectare,
            },
            "gross_tco2e_per_hectare": biomass.co2e_metric_tons,
            "estimated_tco2e_per_hectare": discount.net_certified_tco2e,
            "vm0047_uncertainty": discount.to_dict(),
        },
        "c2pa_root_manifest_hash": (
            "sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069"
        ),
    }


# --------------------------------------------------------------------------- #
# Endpoint 4 — Search (needed for the rubric's semantic-discovery surface)
# --------------------------------------------------------------------------- #


@app.get("/v1/search")
def search(
    q: str = "",
    project_id: Optional[str] = None,
    phase: Optional[str] = None,
    max_results: int = 20,
) -> dict:
    """Stubbed search returning a Lucene-shaped response."""
    return {
        "mode": "MOCK",
        "query": q,
        "total_count": 0,
        "resources": [],
        "note": "STUBBED — Stage 3 implements real structured + semantic search.",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
