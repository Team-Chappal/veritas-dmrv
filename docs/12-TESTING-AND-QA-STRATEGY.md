# Testing, Quality Assurance & CI/CD Strategy
## Project Name: VERITAS dMRV
**Document Version:** 1.0.0 (Master Release)  
**Standard Compliance:** ISO/IEC/IEEE 29119 Software Testing Standards  
**Target:** Teammates A, B, and C (All Engineers)  

---

## 1. Multi-Tiered Testing Pyramid

To guarantee that VERITAS dMRV is rock-solid and resilient during judging, the platform implements a 4-tier testing hierarchy:

```
                            /\
                           /  \
                          /E2E \     Tier 4: Playwright E2E Browser Flows (<10 tests)
                         /------\
                        / Integ  \   Tier 3: FastAPI & Cloudinary Webhook Tests (~25 tests)
                       /----------\
                      / CV & Vision\  Tier 2: OpenCV SIFT/TPS & Photogrammetry (~40 tests)
                     /--------------\
                    / Unit & Physics \ Tier 1: Solar Ephemeris & EUDR Math (>100 tests)
                   /------------------\
```

---

## 2. Tier 1: Physics & Unit Test Suite (`backend/tests/test_physics.py`)

Using `pytest`, `pvlib`, and `freezegun`, these tests verify astronomical ephemeris and statutory geometry in complete isolation:

```python
"""
VERITAS dMRV — Solar Physics & Astronomical Shadow Tests
Run: pytest backend/tests/test_physics.py -v
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

# Test Data Matrix: Ground coordinates, UTC timestamps, and true physical solar azimuths.
#
# CORRECTION (v1.2.0) — DO NOT HAND-WRITE THESE.
#
# The four vectors originally listed in this file were all outside their own
# stated tolerances, and one was physically impossible:
#
#   Nairobi 2026-09-22T08:15:30Z   documented  94.2   actual  85.06  ( 9.14 deg off)
#   Nairobi 2026-09-22T13:30:00Z   documented 268.4   actual 270.91  ( 2.51 deg off)
#   Ankara  2026-06-21T10:00:00Z   documented 138.5   actual 187.74  (49.24 deg off, IMPOSSIBLE)
#   Berlin  2026-12-21T11:00:00Z   documented 173.1   actual 178.95  ( 5.85 deg off)
#
# The Ankara case is diagnostic: at 10:00 UTC on the June solstice, solar noon
# at 32.85E is 09:48 UTC, so the sun is 12 minutes PAST the meridian and its
# azimuth MUST be ~188 deg. 138.5 deg cannot occur at any time of day there.
#
# Fixtures are now GENERATED from pvlib ground truth by
# `scripts/gen_solar_fixtures.py` into `backend/tests/fixtures/solar_vectors.json`
# and loaded below. `make fixtures-check` fails CI if that file is stale.
#
# The generator additionally refuses to emit any genuine fixture whose margin
# below the 12 deg fraud threshold is under 5 deg. The original headline demo
# fixture cleared by only 1.1 deg — a coin flip on stage.
#
SOLAR_FIXTURES = json.loads(
    (Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "solar_vectors.json")
    .read_text()
)["fixtures"]


@pytest.mark.parametrize("fixture", [f for f in SOLAR_FIXTURES if f["kind"] == "genuine"])
def test_genuine_fixture_passes_with_wide_margin(fixture):
    """A real capture must be affirmatively verified, and comfortably so."""
    from services.solar_service import (
        REQUIRED_FIXTURE_MARGIN_DEG,
        ShadowVerdict,
        verify_shadow_coherence,
    )

    ts = datetime.fromisoformat(fixture["timestamp_utc"].replace("Z", "+00:00"))
    result = verify_shadow_coherence(
        latitude=fixture["latitude"],
        longitude=fixture["longitude"],
        timestamp_utc=ts,
        observed_shadow_azimuth_deg=fixture["observed_shadow_azimuth_deg"],
    )

    assert result.verdict == ShadowVerdict.PHYSICS_PASS, fixture["scenario_id"]
    assert result.is_physically_coherent is True
    assert result.margin_to_tolerance_deg >= REQUIRED_FIXTURE_MARGIN_DEG, (
        f"{fixture['scenario_id']} margin {result.margin_to_tolerance_deg} deg is below "
        f"the required {REQUIRED_FIXTURE_MARGIN_DEG} deg — not demo-safe"
    )


@pytest.mark.parametrize("fixture", [f for f in SOLAR_FIXTURES if f["kind"] == "fraud"])
def test_fraud_fixture_is_quarantined(fixture):
    """A falsified capture time must be caught on geometry alone."""
    from services.solar_service import ShadowVerdict, verify_shadow_coherence

    ts = datetime.fromisoformat(fixture["timestamp_utc"].replace("Z", "+00:00"))
    result = verify_shadow_coherence(
        latitude=fixture["latitude"],
        longitude=fixture["longitude"],
        timestamp_utc=ts,
        observed_shadow_azimuth_deg=fixture["observed_shadow_azimuth_deg"],
    )

    assert result.verdict == ShadowVerdict.QUARANTINE_SOLAR_MISMATCH, fixture["scenario_id"]
    assert result.is_fraud is True
    assert result.angular_error_deg > 90.0


@pytest.mark.parametrize("fixture", [f for f in SOLAR_FIXTURES if f["kind"] == "abstain"])
def test_abstention_fixture_declines_to_judge(fixture):
    """A forensic tool that always answers confidently is a liability."""
    from services.solar_service import verify_shadow_coherence

    ts = datetime.fromisoformat(fixture["timestamp_utc"].replace("Z", "+00:00"))
    result = verify_shadow_coherence(
        latitude=fixture["latitude"],
        longitude=fixture["longitude"],
        timestamp_utc=ts,
        observed_shadow_azimuth_deg=fixture["observed_shadow_azimuth_deg"],
    )
    assert result.verdict.value == fixture["expected_verdict"], fixture["scenario_id"]


def test_solar_azimuth_convention_is_north_clockwise():
    """At solar noon the sun is due south (N hemi) or due north (S hemi).

    Guards the convention. The original design applied a spurious +180 deg
    offset, which silently swapped morning for afternoon.
    """
    from services.solar_service import calculate_solar_position

    # Ankara, summer solstice. Solar noon at 32.85E is 09:48 UTC.
    northern_noon = calculate_solar_position(
        39.9207, 32.8541, datetime(2026, 6, 21, 9, 48, tzinfo=timezone.utc)
    )
    assert abs(northern_noon["azimuth_deg"] - 180.0) < 5.0

    # Pretoria (-25.75 S), same instant: sun is due NORTH, just past noon.
    southern_noon = calculate_solar_position(
        -25.7479, 28.2293, datetime(2026, 6, 21, 7, 6, tzinfo=timezone.utc)
    )
    assert min(
        abs(southern_noon["azimuth_deg"] - 0.0), abs(southern_noon["azimuth_deg"] - 360.0)
    ) < 5.0


def test_morning_sun_is_east_of_the_same_days_noon_sun():
    from services.solar_service import calculate_solar_position

    lat, lon = -1.2921, 36.8219
    morning = calculate_solar_position(
        lat, lon, datetime(2026, 9, 22, 5, 15, tzinfo=timezone.utc)
    )
    noon = calculate_solar_position(
        lat, lon, datetime(2026, 9, 22, 9, 32, tzinfo=timezone.utc)
    )
    assert morning["azimuth_deg"] < noon["azimuth_deg"]


def test_naive_datetime_is_rejected():
    """A timezone slip is the exact bug this module exists to catch."""
    from services.solar_service import calculate_solar_position

    with pytest.raises(ValueError, match="timezone-aware"):
        calculate_solar_position(-1.2921, 36.8219, datetime(2026, 9, 22, 8, 15, 30))


def test_shadow_fraud_quarantine_rejection():
    """An inverted shadow vector must trigger quarantine, not a pass.

    08:15 UTC sun sits at azimuth ~83.6 deg (east), so the cast shadow MUST
    point west (~263.6 deg). A photo whose shadow points back east is
    reporting a moment the sun was not where it claimed.
    """
    from services.solar_service import ShadowVerdict, verify_shadow_coherence

    result = verify_shadow_coherence(
        latitude=-1.2921,
        longitude=36.8219,
        timestamp_utc=datetime(2026, 9, 22, 8, 15, 30, tzinfo=timezone.utc),
        observed_shadow_azimuth_deg=85.06,  # shadow pointing EAST — impossible
    )

    assert result.verdict == ShadowVerdict.QUARANTINE_SOLAR_MISMATCH
    assert result.angular_error_deg > 170.0
    assert result.is_physically_coherent is False

```

---

## 3. Tier 2: Photogrammetry & Computer Vision Regression Suite (`backend/tests/test_vision.py`)

Verifies SIFT feature matching, Thin Plate Splines (TPS) parallax handling, and radiometric histogram normalization:

```python
"""
VERITAS dMRV — Photogrammetric & Radiometric Alignment Tests
Run: pytest backend/tests/test_vision.py -v
"""
import pytest
import numpy as np
import cv2

@pytest.fixture
def synthetic_forest_pair():
    """Anchor baseline plus a known-transformed progress update.

    Superseded by the scene builders in ``backend/tests/conftest.py``
    (``make_cluttered_scene``, ``apply_transform``). The earlier version drew
    identical circles in both frames, so SIFT matched the *drawing artefact*
    rather than real scene structure, and the pHash fixtures shared identical
    geometry across "different" images.
    """
    h, w = 400, 600
    baseline = np.zeros((h, w, 3), dtype=np.uint8)
    # Paint synthetic tree crowns
    np.random.seed(42)
    for _ in range(80):
        cx, cy = np.random.randint(50, w-50), np.random.randint(50, h-50)
        radius = np.random.randint(10, 25)
        color = (0, np.random.randint(140, 220), np.random.randint(20, 80)) # Greenish
        cv2.circle(baseline, (cx, cy), radius, color, -1)
        
    # Rotate by 8 degrees and shift by 15px
    M = cv2.getRotationMatrix2D((w/2, h/2), 8.0, 1.0)
    M[0, 2] += 15.0
    progress = cv2.warpAffine(baseline, M, (w, h))
    
    return baseline, progress

def test_sift_registration_inlier_ratio(synthetic_forest_pair):
    """register_field_pair now returns a result object carrying an explicit
    status, rather than a tuple, so that a failure cannot be silently ignored
    by a caller that forgets to check it.
    """
    from services.homography_service import (
        INLIER_RATIO_FLOOR, RegistrationStatus, register_field_pair,
    )

    result = register_field_pair(
        synthetic_forest_pair["baseline"], synthetic_forest_pair["progress"]
    )
    assert result.status == RegistrationStatus.ALIGNED_HOMOGRAPHY
    assert result.inlier_ratio > 0.70
    assert result.residual_rmse_px < 2.0
    assert result.warped_image.shape == synthetic_forest_pair["baseline"].shape
    # A registration too weak to back a compliance claim must say so.
    if result.inlier_ratio < INLIER_RATIO_FLOOR:
        assert any("Inlier ratio" in w for w in result.warnings)

def test_gli_is_invariant_to_illumination():
    """The property that makes illumination correction unnecessary.

    Replaces the original ``test_radiometric_histogram_matching``, which called
    a function that no longer exists and asserted the wrong thing: that a
    cloud-shadowed image should be *brightened back*. It should not be. GLI is
    algebraically invariant to any per-pixel scalar gain, so the shadow needs no
    correction at all -- and per-channel histogram matching, the alternative,
    was measured to inject 2-4x more GLI error than the drift it removes.

    See services/radiometric_service.py for the measurements.
    """
    from services.canopy_service import compute_gli

    base = make_soil_scene(canopy_fraction=0.18, seed=3)
    gli = compute_gli(base)
    for gain in (0.5, 0.65, 0.8):
        scaled = np.clip(base.astype(np.float32) * gain, 0, 255).astype(np.uint8)
        assert np.abs(compute_gli(scaled) - gli).max() < 0.02
```

---

## 4. Tier 3: Integration & Webhook Suite (`backend/tests/test_integration.py`)

Using FastAPI's `TestClient` to verify the entire pipeline without hitting live third-party services:

```python
"""
VERITAS dMRV — API Integration & Cloudinary Webhook Tests
Run: pytest backend/tests/test_integration.py -v
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_triage_endpoint_verified_pass():
    payload = {
        "asset_public_id": "impact_evidence/KEN-042/raw_01",
        "latitude": -1.2921,
        "longitude": 36.8219,
        "capture_timestamp_utc": "2026-09-22T08:15:30Z",
        "observed_shadow_azimuth_deg": 274.5,
        "phash": "d8f1e2c4b8a91034",
        "has_c2pa_manifest": True
    }
    response = client.post("/api/v1/triage/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "VERIFIED_PASS"
    assert data["solar_physics"]["is_physically_coherent"] is True

def test_cloudinary_video_webhook_ingestion():
    webhook_payload = {
        "notification_type": "upload",
        "public_id": "veritas_drones/KEN-042/transect_flight_01",
        "secure_url": "https://res.cloudinary.com/test/video.mp4",
        "info": {
            "categorization": {
                "google_video_tagging": {
                    "data": [{"tag": "canopy", "confidence": 0.96}]
                }
            }
        }
    }
    response = client.post("/api/v1/cloudinary-webhooks/video-processed", json=webhook_payload)
    assert response.status_code == 200
    assert response.json()["status"] == "PROCESSED"
```

---

## 5. Tier 4: Frontend Playwright E2E Suite (`frontend/e2e/audit_flow.spec.ts`)

```typescript
import { test, expect } from '@playwright/test';

test.describe('VERITAS dMRV Auditor Verification Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:3000');
  });

  test('Should render interactive before/after split slider and allow dragging', async ({ page }) => {
    const slider = page.locator('.react-compare-slider');
    await expect(slider).toBeVisible();

    // Verify baseline and progress badges are rendered
    await expect(page.locator('text=MONTH 0 (BASELINE)')).toBeVisible();
    await expect(page.locator('text=MONTH 18 (WARPED)')).toBeVisible();

    // Verify certified growth metric is rendered
    await expect(page.locator('text=+38.2%')).toBeVisible();
  });

  test('Should open Cloudinary interactive video player with spatial hotspots', async ({ page }) => {
    const playerContainer = page.locator('#veritas-drone-video');
    await expect(playerContainer).toBeVisible();

    // Verify AI visual transcription subtitle track is active
    await expect(page.locator('text=AI Video Analysis (Visual Transcription Active)')).toBeVisible();
  });

  test('Should trigger one-click statutory EUDR/CSRD dossier export modal', async ({ page }) => {
    const exportButton = page.locator('button:has-text("Export Statutory Dossier")');
    await exportButton.click();

    const modal = page.locator('text=EUDR Article 9 Cadastral Compliance');
    await expect(modal).toBeVisible();
    await expect(page.locator('text=SHA256 Root Manifest')).toBeVisible();
  });
});
```

---

## 6. GitHub Actions Continuous Integration (`.github/workflows/ci.yml`)

```yaml
name: VERITAS dMRV CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"
      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
          pip install pytest pytest-cov
      - name: Run Pytest Suite with Coverage
        run: |
          pytest --cov=backend --cov-report=xml --cov-fail-under=85 backend/tests/

  frontend-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Node.js 22
        uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: "npm"
          cache-dependency-path: frontend/package.json
      - name: Install dependencies
        run: npm --prefix frontend ci
      - name: Next.js Production Build
        run: npm --prefix frontend run build
```
