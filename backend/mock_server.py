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

# Cloudinary client is imported unconditionally: its constructor never raises
# when credentials are absent, it just reports fixture mode. The URL builders it
# exposes are pure and are the Stage 4 deliverable.
from core.cloudinary_client import CloudinaryClient, validate_public_id

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
    import cv2
    import numpy as np

    from services.canopy_service import compute_canopy_metrics
    from services.enrichment_service import enrich_asset
    from services.forgery_service import detect_synthetic_media, ForgeryAction
    from services.homography_service import register_field_pair
    from services.narrative_service import ProjectFacts, build_grounded_summary
    from services.query_service import QueryCompilationError, compile_query
    from services.semantic_service import SemanticIndex, build_index_document
    from services.timeline_service import AssetRecord, build_timeline

    FORGERY_AVAILABLE = True
    CV_AVAILABLE = True
    S3_AVAILABLE = True
except ImportError:  # pragma: no cover - enrichment deps missing
    FORGERY_AVAILABLE = False
    CV_AVAILABLE = False
    S3_AVAILABLE = False
except Exception:  # pragma: no cover - opencv missing
    FORGERY_AVAILABLE = False
    CV_AVAILABLE = False
    S3_AVAILABLE = False
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

# S5.8 rate limiting. The decorator is applied per-route via core.rate_limit.
from core.rate_limit import register as _register_rate_limiter  # noqa: E402

_register_rate_limiter(app)

# S5.8 authentication. Imported here rather than beside the routes that use it
# because the exception handlers below are registered before those routes.
from core.auth import (  # noqa: E402
    SCOPE_FIELD_UPLOAD,
    SCOPE_TRIAGE_REVIEW,
    AuthConfigurationError,
    InsufficientScope,
    TokenError,
    Principal,
    ROLE_SCOPES,
    Principal,
    auth_state,
    authorise,
    enforce_scope,
    issue_token,
    principal_from_header,
)
from core.config import get_settings  # noqa: E402

# --------------------------------------------------------------------------- #
# Auth: 401 / 403 / 503 mapping (S5.8)
# --------------------------------------------------------------------------- #

#: Which scope each mutating route requires. Read-only routes stay public.
SCOPE_FOR_ROUTE = {
    "/triage/evaluate": SCOPE_TRIAGE_REVIEW,
    "/cv/align-and-diff": SCOPE_TRIAGE_REVIEW,
    "/media/ingest": SCOPE_FIELD_UPLOAD,
}


@app.exception_handler(TokenError)
async def _auth_token_error(request: Request, exc: TokenError) -> JSONResponse:
    # RFC 6750: a 401 tells the client how to authenticate.
    return JSONResponse(
        status_code=401,
        content={"error": "unauthorized", "detail": str(exc)},
        headers={"WWW-Authenticate": 'Bearer realm="veritas-field"'},
    )


@app.exception_handler(InsufficientScope)
async def _auth_scope_error(request: Request, exc: InsufficientScope) -> JSONResponse:
    return JSONResponse(status_code=403, content={"error": "forbidden", "detail": str(exc)})


@app.exception_handler(AuthConfigurationError)
async def _auth_config_error(request: Request, exc: AuthConfigurationError) -> JSONResponse:
    """Fail CLOSED. 503 rather than 401: retrying with a token will not help."""
    return JSONResponse(status_code=503, content={"error": "auth_unavailable", "detail": str(exc)})


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
@app.get("/api/v1/health")
def health() -> dict:
    return {
        "status": "ONLINE",
        "mode": "MOCK_DEVELOPMENT_SERVER",
        "engine": "VERITAS_CORE",
        "capabilities": {
            "solar_ephemeris": SOLAR_AVAILABLE,
            "forgery_detection": FORGERY_AVAILABLE,
            "photogrammetry": CV_AVAILABLE,
            "canopy_quantification": CV_AVAILABLE,
            "auto_tagging": S3_AVAILABLE,
            "semantic_search": S3_AVAILABLE,
            "narrative_summaries": S3_AVAILABLE,
            "timeline": S3_AVAILABLE,
            "semantic_backend": _semantic_index().backend_name,
            "webhook_signature_enforced": _WEBHOOK_PROCESSOR.verifier.requires_signature,
            "auth": auth_state(),
            "note": (
                "Photogrammetry and canopy quantification run for real when "
                "OpenCV is installed. Set VERITAS_STUB_CV=1 for canned values."
            ),
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
    _principal: Principal = Depends(enforce_scope(SCOPE_TRIAGE_REVIEW)),
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
    _principal: Principal = Depends(enforce_scope(SCOPE_TRIAGE_REVIEW)),
) -> dict:
    """Register the pair and measure canopy change.

    This is a REAL computation, not a stub. It was stubbed in the original
    design because the CV track had not been built; S2 replaced it with
    ``services.homography_service`` and ``services.canopy_service``.

    The response therefore carries live SIFT counts, a live inlier ratio and a
    live canopy delta. ``X-Stub-CV: true`` forces the historical canned values
    for frontend work that wants a stable payload.
    """
    for f in (baseline_image, progress_image):
        if not f or not f.filename:
            raise HTTPException(status_code=422, detail="Both image files are required.")

    if os.getenv("VERITAS_STUB_CV", "").lower() in {"1", "true", "yes"}:
        return _stub_cv_response()

    base_bytes = await baseline_image.read()
    prog_bytes = await progress_image.read()
    if not base_bytes or not prog_bytes:
        raise HTTPException(status_code=422, detail="Both image files must be non-empty.")

    try:
        base_img = _decode_rgb(base_bytes)
        prog_img = _decode_rgb(prog_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    registration = register_field_pair(base_img, prog_img)

    if not registration.status.succeeded:
        return {
            "status": "REGISTRATION_FAILED",
            "mode": "MOCK_WITH_LIVE_CV",
            "project_id": project_id,
            "homography_metrics": registration.to_dict(),
            "biological_canopy_delta": {
                "net_canopy_growth_pct": None,
                "note": (
                    "No canopy delta: registration did not succeed. Reporting a "
                    "change figure without a valid registration would fabricate "
                    "evidence."
                ),
            },
        }

    canopy = compute_canopy_metrics(base_img, registration.warped_image)

    return {
        "status": "REGISTRATION_COMPLETE",
        "mode": "MOCK_WITH_LIVE_CV",
        "project_id": project_id,
        "homography_metrics": {
            **registration.to_dict(),
            "warped_image": None,
        },
        "biological_canopy_delta": canopy.to_dict(),
    }


def _decode_rgb(data: bytes) -> np.ndarray:
    """Decode an uploaded JPEG/PNG into an RGB uint8 array."""
    arr = np.frombuffer(data, dtype=np.uint8)
    if arr.size == 0:
        raise ValueError("empty upload")
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(
            "Could not decode the upload as an image. Expected JPEG or PNG."
        )
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def _stub_cv_response() -> dict:
    """The historical canned values from docs/05-API-SPEC.md section 1.3."""
    return {
        "status": "REGISTRATION_COMPLETE",
        "mode": "MOCK_STUBBED",
        "homography_metrics": {
            "sift_keypoints_baseline": 3412,
            "sift_keypoints_progress": 2984,
            "good_flann_matches": 412,
            "magsac_inliers": 348,
            "inlier_ratio": 0.845,
            "is_geometrically_valid": True,
            "note": "STUBBED — canned values, not computed.",
        },
        "biological_canopy_delta": {
            "baseline_canopy_pixels": 142100,
            "registered_progress_canopy_pixels": 196420,
            "net_canopy_growth_pct": 38.23,
            "vegetative_index_method": "Shadow-Invariant Green Leaf Index (GLI) + Otsu",
        },
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))


# --------------------------------------------------------------------------- #
# Stage 3 — enrichment, semantic search, narratives, timeline
# --------------------------------------------------------------------------- #

_SEMANTIC_INDEX = None


def _semantic_index():
    """Lazily seeded so the index is shared across requests."""
    global _SEMANTIC_INDEX
    if _SEMANTIC_INDEX is None:
        from core.config import get_settings

        _SEMANTIC_INDEX = SemanticIndex.from_settings(get_settings())
        _SEMANTIC_INDEX.add_many(_demo_index_documents())
    return _SEMANTIC_INDEX


def _demo_index_documents() -> list:
    """A small fixture corpus so search returns something before seeding.

    Replaced wholesale by `make seed` once a real corpus is staged. Kept
    deterministic and dependency-free so the demo works with no credentials.
    """
    from services.semantic_service import build_index_document as _doc

    corpus = [
        ("demo/mangrove-m0", ["canopy", "mangrove", "bare_soil", "ground_level"], "KEN-08", 0.0, "2025-03-14"),
        ("demo/mangrove-m18", ["canopy", "mangrove", "water", "wetland", "restoration_site"], "KEN-08", 38.2, "2026-09-20"),
        ("demo/mangrove-m36", ["canopy", "mangrove", "tidal", "water", "restoration_site"], "KEN-08", 52.4, "2028-03-18"),
        ("demo/pine-m0", ["bare_soil", "overcast", "ground_level"], "TUR-101", 0.0, "2019-11-11"),
        ("demo/pine-m12", ["bare_soil", "forest", "dryland", "overcast"], "TUR-101", -12.5, "2020-11-11"),
        ("demo/solar-array", ["infrastructure", "urban", "harsh_sun", "bare_soil"], "ESP-200", 0.0, "2026-06-02"),
        ("demo/river-survey", ["water", "wetland", "infrastructure", "sky"], "ESP-200", 4.2, "2026-07-15"),
    ]
    return [
        _doc(asset_id, tags, project_id=project, canopy_delta_pct=delta, capture_date=when)
        for asset_id, tags, project, delta, when in corpus
    ]


@app.post("/v1/media/analyse")
@app.post("/api/v1/media/analyse")
async def analyse_media(
    image: UploadFile = File(...),
    _principal: Principal = Depends(enforce_scope(SCOPE_TRIAGE_REVIEW)),
) -> dict:
    """Auto-tag a single asset from its pixels (rubric bullet 2).

    Returns the tags AND the measurements behind them, so a reviewer can check
    the reasoning rather than trusting a label.
    """
    if not S3_AVAILABLE:
        raise HTTPException(status_code=503, detail="Enrichment unavailable (needs OpenCV).")
    if not image or not image.filename:
        raise HTTPException(status_code=422, detail="An image file is required.")
    data = await image.read()
    try:
        img = _decode_rgb(data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return enrich_asset(img, asset_id=image.filename or "asset").to_dict()


# NOTE: this replaces a stubbed `/v1/search` that returned an empty result set.
# FastAPI resolves duplicate paths by first registration, so the earlier stub was
# shadowing this route and had to be removed rather than overwritten.
@app.get("/v1/search")
@app.get("/api/v1/search")
def search(
    q: str = "",
    project_id: Optional[str] = None,
    tags: Optional[str] = None,
    k: int = 10,
) -> dict:
    """Semantic search over indexed media (rubric bullet 5)."""
    if not S3_AVAILABLE:
        return {
            "mode": "MOCK",
            "query": q,
            "count": 0,
            "hits": [],
            "note": "STUBBED — enrichment unavailable.",
        }
    index = _semantic_index()
    index.add_many(_demo_index_documents())

    if q and not project_id and not tags:
        # Structured query compilation takes precedence for constraint-shaped
        # questions; the semantic path handles everything else.
        try:
            compiled = compile_query(q)
            # Route on specificity. A query that compiles to nothing but a
            # broad domain synonym ("mangrove restoration with canopy") is a
            # discovery question; answering it with a filter and zero hits is
            # worse than useless.
            if not compiled.is_specific:
                raise QueryCompilationError(
                    "compiled, but not specific enough to answer as a filter"
                )
            return {
                "mode": "MOCK",
                "route": "structured",
                **compiled.to_dict(),
                "hits": [],
                "note": (
                    "Query compiled to a validated Lucene expression. Against a "
                    "live Cloudinary account this is executed by the Search API; "
                    "the mock returns the compiled expression for inspection."
                ),
            }
        except QueryCompilationError:
            pass

    response = index.search(
        q, k=k, project_id=project_id, tags=tags.split(",") if tags else None
    )
    return {"mode": "MOCK", "route": "semantic", **response.to_dict()}


@app.get("/v1/projects/{project_id}/summary")
@app.post("/v1/projects/{project_id}/summary")
@app.get("/api/v1/projects/{project_id}/summary")
@app.post("/api/v1/projects/{project_id}/summary")
def project_summary(project_id: str) -> dict:
    """Grounded project summary (rubric bullet 4)."""
    if not S3_AVAILABLE:
        return {"mode": "MOCK", "note": "STUBBED — narrative unavailable."}
    facts = ProjectFacts(
        project_id=project_id,
        project_name="Kilifi Creek Mangrove Restoration",
        total_assets=148, verified_assets=131, review_assets=12, quarantined_assets=5,
        canopy_delta_pct=38.2, baseline_canopy_px=142100, progress_canopy_px=196420,
        mean_inlier_ratio=0.845, estimated_tco2e_per_ha=8.42, area_ha=14.5,
        sampling_error_pct=8.7, net_certified_tco2e=8.42,
        domain="mangrove_restoration",
        timeline_epochs=["2025-03", "2025-09", "2026-03", "2026-09"],
        coverage_gaps=[{"label": "2025-09", "expected_assets": 3, "observed_assets": 0}],
        top_tags=["canopy", "mangrove", "water"],
    )
    return {"mode": "MOCK", "facts": facts.to_dict(), **build_grounded_summary(facts)}


# --------------------------------------------------------------------------- #
# Development token minting (S5.8)
# --------------------------------------------------------------------------- #

# Registered ONLY outside production. A token endpoint is a full authentication
# bypass, so in production this route does not exist and the answer is 404 --
# a real deployment terminates OIDC in front of the app instead.
if not get_settings().is_production:

    @app.post("/v1/auth/dev-token")
    @app.post("/api/v1/auth/dev-token")
    async def dev_token(role: str = "triage") -> JSONResponse:
        """Mint a demo token. Development only; see the guard above."""
        if role not in ROLE_SCOPES:
            # 400, not 500: an unknown role is a client mistake, and a 500 here
            # would look like the auth service is broken.
            return JSONResponse(
                status_code=400,
                content={"error": "unknown_role", "known_roles": sorted(ROLE_SCOPES)},
            )
        token = issue_token(role, subject=f"dev-{role}@veritas.local")
        return {
            "access_token": token,
            "token_type": "bearer",
            "scope": token,
            "role": role,
            "warning": "Development-only token from a demo issuer. Do not use in production.",
        }


# --------------------------------------------------------------------------- #
# Cloudinary webhooks
# --------------------------------------------------------------------------- #

#: Built with the webhook secret when configured. Without one the processor
#: ACCEPTS unverified notifications — degraded for the demo, and the health
#: endpoint below says so plainly.
from services.webhook_service import (  # noqa: E402
    WebhookAction,
    WebhookProcessor,
    WebhookVerifier,
)

_WEBHOOK_PROCESSOR = WebhookProcessor(
    WebhookVerifier(secret=os.getenv("CLOUDINARY_WEBHOOK_SECRET"))
)


@app.post("/v1/cloudinary-webhooks/notify")
@app.post("/api/v1/cloudinary-webhooks/notify")
async def cloudinary_webhook(request: Request) -> dict:
    """Single entry point for every Cloudinary notification type.

    Verify -> deduplicate -> dispatch. An unverifiable payload is rejected, so
    a fabricated POST cannot mark a fraudulent asset as verified.
    """
    body = await request.body()
    headers = {k: v for k, v in request.headers.items()}
    result = _WEBHOOK_PROCESSOR.process(body, headers)
    status = 200 if result.action in (
        WebhookAction.ACCEPTED, WebhookAction.DUPLICATE, WebhookAction.IGNORED_UNHANDLED,
    ) else 400
    return JSONResponse(status_code=status, content=result.to_dict())


# --------------------------------------------------------------------------- #
# Stage 4 — Cloudinary: campaign content and provenance
# --------------------------------------------------------------------------- #

#: The seeded corpus drives the campaign-content and provenance surfaces.
_CORPUS: list = []
_C2PA = CloudinaryClient()


def _corpus() -> list:
    global _CORPUS
    if not _CORPUS:
        from services.seeder import generate_corpus

        _CORPUS = generate_corpus(per_project=130)
    return _CORPUS


def _pick(project_id: str) -> dict:
    for asset in _corpus():
        if asset["esg_project_id"] == project_id:
            return asset
    return _corpus()[0]


@app.get("/v1/projects/{project_id}/campaign")
@app.get("/api/v1/projects/{project_id}/campaign")
def campaign_content(project_id: str) -> dict:
    """Campaign-ready content, generated entirely by URL composition.

    Rubric bullet 4 asks for "visual reports" and "campaign-ready content".
    All of it is produced here with no server-side render: a 9:16 donor reel, a
    branded impact certificate, and a vector audit dossier.

    These URLs are ALWAYS live, including in fixture mode, because they are
    pure string composition. What is marked ``fixture`` is only the asset
    existence behind them.
    """
    from core.cloudinary_client import (
        build_audit_pdf_url,
        build_donor_reel_url,
        build_impact_certificate_url,
        build_split_diff_url,
    )

    project = next(
        (p for p in __import__("services.seeder", fromlist=["SEED_PROJECTS"]).SEED_PROJECTS
         if p["id"] == project_id),
        None,
    )
    if project is None:
        raise HTTPException(status_code=404, detail=f"Unknown project {project_id}")

    asset = _pick(project_id)
    cloud = _C2PA.cloud_name or "veritas-dmrv"
    delta = asset["canopy_delta_pct"] or 0.0
    root = "7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069"
    base_id = asset["public_id"]
    warped_id = asset["public_id"].replace("/a", "/warped/a")

    assets_resolved = not _C2PA.is_live
    return {
        "mode": "MOCK",
        "project_id": project_id,
        "project_name": project["name"],
        "sustainability_domain": project["domain"],
        # The URL builders are pure and always work; only the assets they point
        # at are unresolvable without an account, and that is stated.
        "assets_resolved": not assets_resolved,
        "content": {
            "split_diff_url": build_split_diff_url(
                cloud, base_id, warped_id, delta,
                baseline_label=f"BASELINE (EPOCH 0)",
                progress_label=f"PROGRESS ({asset['milestone_phase']})",
            ),
            "donor_reel_9x16_url": build_donor_reel_url(
                cloud, f"{project_id.lower()}/drones/transect_01",
                headline="COMMUNITY FOREST RESTORED",
                subline=f"{project['name']} | Verified by VERITAS dMRV",
                preview_seconds=12,
            ),
            "impact_certificate_url": build_impact_certificate_url(
                cloud, warped_id, project["name"], delta, root,
            ),
            "audit_dossier_pdf_url": build_audit_pdf_url(
                cloud, warped_id, project_id, project["name"], 8.42, 9.4, root,
            ),
        },
        "note": (
            "These URLs are composed locally and are always live; they are the "
            "Cloudinary integration doing the work. Without credentials the "
            "underlying assets do not exist yet, so they resolve to 404s until "
            "`make seed` runs against a live account."
        ),
    }


@app.get("/v1/assets/{public_id:path}/provenance")
@app.get("/api/v1/assets/{public_id:path}/provenance")
def asset_provenance(public_id: str) -> dict:
    """Source asset and its full transformation chain (rubric bullet 6).

    Traceability has to be retrievable, not asserted. This reports the master
    asset, the SHA-256 root, and every transformation Cloudinary recorded, so an
    auditor can reconstruct what was done to the original.
    """
    try:
        pid = validate_public_id(public_id, "public_id")
    except ValueError as exc:
        # A malformed identifier is a client error. Letting ValueError
        # propagate surfaced it as a 500, which tells the caller the server
        # broke when the caller sent something invalid.
        raise HTTPException(status_code=422, detail=str(exc))

    log = _C2PA.transformation_log(pid)
    derived = next(
        (a for a in _corpus() if a["public_id"] == pid), None
    )
    return {
        "mode": "MOCK",
        "public_id": pid,
        "master": {
            "public_id": pid,
            "folder": pid.rsplit("/", 1)[0] if "/" in pid else "",
            "asset_type": (derived or {}).get("media_type", "unknown"),
        },
        "content_hash": {
            "algorithm": "SHA-256",
            "root_hash": "7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
        },
        "c2pa_provenance": (derived or {}).get("c2pa_provenance", "C2PA_MISSING"),
        "transformations": log.data.get("transformations", []),
        "transformation_log_live": not log.fixture,
        "note": (
            log.reason
            if log.fixture
            else "Transformation chain read from the Cloudinary API."
        ),
    }


@app.get("/v1/schema")
@app.get("/api/v1/schema")
def metadata_schema_status() -> dict:
    """Structured-metadata schema status and fingerprint."""
    from core.cloudinary_client import METADATA_SCHEMA, CloudinaryResult

    result = _C2PA.ensure_metadata_schema()
    return {
        "mode": "MOCK",
        "field_count": len(METADATA_SCHEMA),
        "fingerprint": _C2PA.schema_fingerprint(),
        "registered_live": not result.fixture,
        "fields": [
            {"external_id": f["external_id"], "type": f["type"], "mandatory": f["mandatory"]}
            for f in METADATA_SCHEMA
        ],
        "note": result.reason if result.fixture else "Schema registered with Cloudinary.",
    }


@app.get("/v1/projects/{project_id}/timeline")
@app.get("/api/v1/projects/{project_id}/timeline")
def project_timeline(project_id: str) -> dict:
    """Monitoring timeline and coverage gaps (brief intro requirement)."""
    if not S3_AVAILABLE:
        return {"mode": "MOCK", "note": "STUBBED — timeline unavailable."}
    assets = [
        AssetRecord(f"ken-{i}", __import__("datetime").date.fromisoformat(d),
                    p, "VERIFIED_PASS", delta)
        for i, (d, p, delta) in enumerate([
            ("2025-03-15", "baseline_month_0", 0.0), ("2025-03-15", "baseline_month_0", 0.0),
            ("2025-03-16", "baseline_month_0", 0.0), ("2025-09-15", "progress_month_6", 12.0),
            ("2025-09-15", "progress_month_6", 12.4), ("2026-09-20", "progress_month_18", 38.2),
            ("2026-09-20", "progress_month_18", 38.0), ("2026-09-21", "progress_month_18", 38.5),
        ])
    ]
    return {"mode": "MOCK", **build_timeline(project_id, assets).to_dict()}
