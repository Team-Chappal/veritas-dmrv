# Developer Experience (DX), Parallel Workflows & Mock Architecture
## Project Name: VERITAS dMRV
**Document Version:** 1.0.0 (Master Release)  
**Standard Compliance:** 3-Person Zero-Friction Hackathon Execution  
**Target:** Teammate A (Frontend), Teammate B (Backend/CV), Teammate C (Cloudinary/Demo)  

---

## 1. The 3-Person Parallel Execution Architecture

To ensure all three teammates can code simultaneously from Minute 1 without blocking each other or waiting for external API approvals, VERITAS dMRV adopts an **Interface-First Decoupled Architecture**:

```
                         [SHARED CONTRACT: docs/05-API-SPEC.md]
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        │                                │                                │
        ▼                                ▼                                ▼
  [STREAM A: FRONTEND]          [STREAM B: BACKEND/CV]          [STREAM C: CLOUDINARY/DEMO]
  • Next.js 15 App Router       • FastAPI Core (Port 8000)      • Cloudinary Admin API
  • Runs against Mock Server    • SIFT/TPS Photogrammetry       • Metadata Schema Initialization
  • Compare Slider & Video HUD  • pvlib Solar Ephemeris         • Video Hotspot Coordinates
  • Zero backend dependency     • Validated via pytest fixtures • Demo Assets & Fixture Seeding
```

### 1.1 Parallel Workstream Matrix

| Teammate | Focus Area | Directory | Unblocked By | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **Teammate A (Frontend)** | Next.js 15 UI, Compare Slider, Cloudinary Video Player, Forensic HUD | `/frontend` | Standalone Mock Server (`mock_server.py`) | Interactive Web Experience & Auditor Dashboard |
| **Teammate B (Backend/CV)** | Solar Ephemeris, SIFT + TPS Homography, GLI Canopy Delta, EUDR Validator | `/backend` | Offline sample images in `/fixtures` | Production FastAPI Services & Computer Vision Math |
| **Teammate C (Cloudinary/Demo)** | Structured Metadata Schema, Eager Presets, Hotspots, Dynamic PDF URL Engine | `/cloudinary` | Cloudinary REST API & Node SDK | Pre-rendered Edge Assets, Seeding Script & Pitch Demo |

---

## 2. Deterministic Dependency Specifications

To eliminate "works on my machine" version mismatches across Windows, macOS, and Linux, all versions are strictly pinned.

### 2.1 Backend: `backend/requirements.txt`
```text
# Web Framework & Server
fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic==2.9.2

# Computer Vision & Photogrammetry
opencv-python-headless==4.10.0.84
numpy==2.1.1
scipy==1.14.1

# Astronomical Physics & Geolocation
pvlib==0.11.1
pandas==2.2.3
shapely==2.0.6
pyproj==3.6.1

# Cloudinary Integration
cloudinary==1.41.0

# Testing & Utilities
pytest==8.3.3
httpx==0.27.2
python-multipart==0.0.9
```

### 2.2 Frontend: `frontend/package.json`
```json
{
  "name": "veritas-dmrv-frontend",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "dev:mock": "NEXT_PUBLIC_API_URL=http://localhost:8000/v1 next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "15.0.0",
    "react": "19.0.0-rc-66855b96-20241015",
    "react-dom": "19.0.0-rc-66855b96-20241015",
    "lucide-react": "^0.453.0",
    "react-compare-slider": "^3.0.1",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.2"
  },
  "devDependencies": {
    "typescript": "^5.6.2",
    "@types/node": "^22.7.4",
    "@types/react": "^19.0.0-rc-66855b96-20241015",
    "@types/react-dom": "^19.0.0-rc-66855b96-20241015",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.13"
  }
}
```

---

## 3. Standalone Executable Mock Server (`backend/mock_server.py`)

This lightweight mock server implements 100% of the API contracts in `docs/05-API-SPEC.md`. **The Frontend engineer can start this immediately** to test every screen without needing OpenCV or GPU dependencies.

```python
"""
VERITAS dMRV — Standalone Fast Mock Server for Frontend Unblocking
Run: uvicorn backend.mock_server:app --port 8000 --reload
"""
from fastapi import FastAPI, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import json

app = FastAPI(title="VERITAS dMRV Mock Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/v1/health")
async def health_check():
    return {"status": "ONLINE", "mode": "MOCK_DEVELOPMENT_SERVER"}

@app.post("/v1/triage/evaluate")
async def mock_triage(payload: dict, x_mock_scenario: Optional[str] = Header(None)):
    """Simulates JEV RLCD triage & astronomical physics evaluation."""
    if x_mock_scenario == "fraud_spoof" or payload.get("observed_shadow_azimuth_deg", 0) > 200:
        return {
            "status": "QUARANTINED",
            "decision": "QUARANTINE_FRAUD",
            "confidence_score": 98,
            "solar_physics": {
                "calculated_sun_azimuth_deg": 284.1,
                "calculated_sun_elevation_deg": 41.2,
                "expected_shadow_azimuth_deg": 104.1,
                "angular_error_deg": 170.4,
                "is_physically_coherent": False
            },
            "quarantine_reason": "SOLAR_EPHEMERIS_PHYSICAL_DISCREPANCY: Shadow angle contradicts GPS time."
        }
    return {
        "status": "SUCCESS",
        "decision": "VERIFIED_PASS",
        "confidence_score": 96,
        "solar_physics": {
            "calculated_sun_azimuth_deg": 94.2,
            "calculated_sun_elevation_deg": 38.6,
            "expected_shadow_azimuth_deg": 274.2,
            "angular_error_deg": 0.3,
            "is_physically_coherent": True
        },
        "deduplication": {"phash_min_distance_to_corpus": 18, "is_duplicate_or_nursery_reuse": False},
        "c2pa_status": "C2PA_VERIFIED",
        "audit_receipt_id": "rec_mock_8a91bc74e1"
    }

@app.post("/v1/cv/align-and-diff")
async def mock_cv_diff(
    baseline_image: UploadFile = File(...),
    progress_image: UploadFile = File(...),
    project_id: str = Form("KEN-042")
):
    """Simulates SIFT homography warping & GLI vegetative growth delta."""
    return {
        "status": "REGISTRATION_COMPLETE",
        "homography_metrics": {
            "sift_keypoints_baseline": 3412,
            "sift_keypoints_progress": 2984,
            "good_flann_matches": 412,
            "magsac_inliers": 348,
            "inlier_ratio": 0.845,
            "is_geometrically_valid": True
        },
        "biological_canopy_delta": {
            "baseline_canopy_pixels": 142100,
            "registered_progress_canopy_pixels": 196420,
            "net_canopy_growth_pct": 38.23,
            "vegetative_index_method": "Shadow-Invariant Green Leaf Index (GLI) + Otsu"
        },
        "cloudinary_warped_asset_id": "veritas_demo/after_warped_id",
        "dynamic_split_diff_url": "https://res.cloudinary.com/demo/image/upload/c_fill,w_1200,h_800/c_crop,w_600,h_800,g_west/sample.jpg"
    }

@app.get("/v1/audit/dossier/{project_id}")
async def mock_audit_dossier(project_id: str):
    """Simulates statutory EUDR / CSRD ESRS E4 audit dossier."""
    return {
        "project_id": project_id,
        "project_name": "Kilifi Community Mangrove Restoration",
        "cadastral_polygon_geojson": {
            "type": "Polygon",
            "coordinates": [[[39.851234, -3.631245], [39.855420, -3.631245], [39.855420, -3.636120], [39.851234, -3.636120], [39.851234, -3.631245]]]
        },
        "eudr_compliance_status": "COMPLIANT_ARTICLE_9",
        "csrd_esrs_e4_biodiversity_score": 0.92,
        "verified_milestone": "Month 18 Canopy Closure",
        "allometric_biomass_estimate": {
            "species_mix": ["Rhizophora mucronata", "Avicennia marina"],
            "mean_dbh_cm": 6.8,
            "mean_height_m": 3.9,
            "estimated_tco2e_per_hectare": 8.42,
            "statistical_uncertainty_ci90": "8.7% (Compliant <15%)"
        },
        "c2pa_root_manifest_hash": "sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
        "dynamic_pdf_certificate_url": "https://res.cloudinary.com/demo/image/upload/w_1200,h_630,c_fill/sample.pdf"
    }
```

---

## 4. Physical Fixtures Specification (`fixtures/mock_db.json`)

To enable instant seeding and offline development, the repository stores canonical metadata:

```json
{
  "projects": [
    {
      "id": "KEN-042",
      "name": "Kilifi Community Mangrove Estuary",
      "ecosystem": "MANGROVE_COASTAL",
      "latitude": -3.631245,
      "longitude": 39.851234,
      "target_hectares": 14.5,
      "cadastral_polygon": [
        [39.851234, -3.631245],
        [39.85542, -3.631245],
        [39.85542, -3.63612],
        [39.851234, -3.636120],
        [39.851234, -3.631245]
      ],
      "baseline_date": "2025-03-15",
      "monitored_date": "2026-09-15",
      "baseline_public_id": "veritas_demo/kenya_mangrove_baseline",
      "progress_public_id": "veritas_demo/kenya_mangrove_month18",
      "growth_pct": 38.2,
      "status": "VERIFIED_ACTIVE"
    },
    {
      "id": "TUR-101",
      "name": "Breath for the Future Reforestation",
      "ecosystem": "SEMI_ARID_PINE",
      "latitude": 39.920770,
      "longitude": 32.854110,
      "target_hectares": 25.0,
      "baseline_date": "2019-11-11",
      "monitored_date": "2020-02-15",
      "baseline_public_id": "veritas_demo/potemkin_nursery_baseline",
      "progress_public_id": "veritas_demo/potemkin_dead_progress",
      "growth_pct": -88.4,
      "status": "QUARANTINED_MORTALITY_FRAUD"
    }
  ]
}
```

---

## 5. Root Developer Automation Scripts

### 5.1 PowerShell Quickstart (`dev.ps1`)
```powershell
param (
    [string]$Mode = "mock"
)

if ($Mode -eq "mock") {
    Write-Host ">>> Starting VERITAS dMRV in MOCK MODE (Zero external dependencies)..." -ForegroundColor Green
    Start-Process powershell -ArgumentList "uvicorn backend.mock_server:app --port 8000 --reload"
    Start-Process powershell -ArgumentList "npm --prefix frontend run dev:mock"
} elseif ($Mode -eq "live") {
    Write-Host ">>> Starting VERITAS dMRV in FULL LIVE MODE (OpenCV + Cloudinary)..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "uvicorn backend.main:app --port 8000 --reload"
    Start-Process powershell -ArgumentList "npm --prefix frontend run dev"
}
```

With this architecture in place, **all 3 teammates are completely free to build and verify their respective modules concurrently**.
