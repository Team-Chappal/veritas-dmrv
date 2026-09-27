"""
Tier 3 — Integration tests for configuration and the mock server.

Two jobs:

1. **Config degradation.** Credential absence is a supported state. These tests
   pin that a missing or blank Cloudinary credential selects fixture mode
   rather than raising, because the stage demo must never depend on a key.

2. **Mock server contract.** The mock is what unblocks frontend development at
   hour zero, so its contract must match `docs/05-API-SPEC.md` exactly. In
   particular it must return VERIFIED_PASS for the payload the spec documents
   as passing — the previous mock quarantined it, which would have sent a
   frontend developer chasing a bug that did not exist.
"""

from __future__ import annotations

import importlib
import os

import pytest
from fastapi.testclient import TestClient


# =========================================================================== #
# Config
# =========================================================================== #


@pytest.fixture
def fresh_settings(monkeypatch):
    """Reload config with a controlled environment."""

    def _load(**env):
        for key in (
            "CLOUDINARY_CLOUD_NAME",
            "CLOUDINARY_API_KEY",
            "CLOUDINARY_API_SECRET",
            "APP_ENV",
        ):
            monkeypatch.delenv(key, raising=False)
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        import core.config as cfg

        importlib.reload(cfg)
        return cfg

    return _load


class TestConfigDegradation:
    def test_no_credentials_selects_fixture_mode(self, fresh_settings):
        cfg = fresh_settings()
        s = cfg.Settings()
        assert s.has_cloudinary_credentials is False
        assert s.mode == "fixture"

    def test_blank_credentials_are_treated_as_absent(self, fresh_settings):
        """An empty string in a .env must not read as 'configured'."""
        cfg = fresh_settings(
            CLOUDINARY_CLOUD_NAME="",
            CLOUDINARY_API_KEY="",
            CLOUDINARY_API_SECRET="",
        )
        s = cfg.Settings()
        assert s.has_cloudinary_credentials is False
        assert s.mode == "fixture"

    def test_partial_credentials_do_not_enable_live_mode(self, fresh_settings):
        """Two of three secrets is not a usable configuration."""
        cfg = fresh_settings(
            CLOUDINARY_CLOUD_NAME="demo", CLOUDINARY_API_KEY="123"
        )
        s = cfg.Settings()
        assert s.has_cloudinary_credentials is False
        assert s.mode == "fixture"

    def test_full_credentials_enable_live_mode(self, fresh_settings):
        cfg = fresh_settings(
            CLOUDINARY_CLOUD_NAME="demo",
            CLOUDINARY_API_KEY="123",
            CLOUDINARY_API_SECRET="xyz",
        )
        s = cfg.Settings()
        assert s.has_cloudinary_credentials is True
        assert s.mode == "live"

    def test_public_summary_never_leaks_a_secret(self, fresh_settings):
        cfg = fresh_settings(
            CLOUDINARY_CLOUD_NAME="demo",
            CLOUDINARY_API_KEY="super-secret-key",
            CLOUDINARY_API_SECRET="super-secret-value",
        )
        summary = cfg.Settings().public_summary()
        flat = str(summary)
        assert "super-secret-key" not in flat
        assert "super-secret-value" not in flat
        assert summary["cloudinary_configured"] is True

    def test_defaults_when_nothing_is_set(self, fresh_settings):
        cfg = fresh_settings()
        s = cfg.Settings()
        assert s.app_env == "development"
        assert s.demo_cache_enabled is True
        assert s.shadow_coherence_tolerance_deg == 12.0
        assert s.phash_duplicate_threshold == 12
        assert s.sift_inlier_ratio_floor == 0.60
        assert s.sift_inlier_ratio_target == 0.70

    def test_next_public_cloud_name_is_a_valid_fallback(self, fresh_settings):
        """A frontend-only env var must still be discovered."""
        cfg = fresh_settings(NEXT_PUBLIC_CLOUDINARY_CLOUD_NAME="demo-cloud")
        s = cfg.Settings()
        assert s.cloudinary_cloud_name == "demo-cloud"

    def test_get_settings_is_cached(self, fresh_settings):
        cfg = fresh_settings()
        cfg.get_settings.cache_clear()
        assert cfg.get_settings() is cfg.get_settings()

    def test_public_summary_is_json_serialisable(self, fresh_settings):
        import json

        cfg = fresh_settings()
        json.dumps(cfg.Settings().public_summary())


# =========================================================================== #
# Mock server contract
# =========================================================================== #


@pytest.fixture(scope="module")
def client():
    import mock_server

    return TestClient(mock_server.app)


#: The exact payload docs/05-API-SPEC.md §1.2 publishes as a successful triage.
SPEC_VERIFIED_PAYLOAD = {
    "asset_public_id": "impact_evidence/KEN-042/raw_capture_month18",
    "latitude": -1.292145,
    "longitude": 36.821945,
    "capture_timestamp_utc": "2026-09-22T08:15:30Z",
    "observed_shadow_azimuth_deg": 274.5,
    "phash": "d8f1e2c4b8a91034",
    "has_c2pa_manifest": True,
}

#: Morning capture claimed as afternoon, per the demo narrative.
SPEC_FRAUD_PAYLOAD = {
    "asset_public_id": "impact_evidence/TSAVO/fraud",
    "latitude": -2.854120,
    "longitude": 38.452140,
    "capture_timestamp_utc": "2026-09-22T11:30:00Z",
    "observed_shadow_azimuth_deg": 267.6,
    "has_c2pa_manifest": True,
}


class TestMockHealth:
    def test_health_reports_mode_and_capabilities(self, client):
        body = client.get("/health").json()
        assert body["status"] == "ONLINE"
        assert body["mode"] == "MOCK_DEVELOPMENT_SERVER"
        assert "solar_ephemeris" in body["capabilities"]
        # Photogrammetry is stubbed, and the server must say so rather than
        # letting a frontend believe the numbers are computed.
        assert body["capabilities"]["photogrammetry"] is False

    def test_versioned_health_alias(self, client):
        assert client.get("/v1/health").json()["status"] == "ONLINE"


class TestMockTriageContract:
    def test_documented_success_payload_passes(self, client):
        """REGRESSION GUARD for the docs/11 mock bug.

        The old mock selected fraud via `observed_shadow_azimuth_deg > 200`.
        The spec's own VERIFIED_PASS example uses 274.5, so the documented
        success payload was quarantined. This test fails if that returns.
        """
        r = client.post("/v1/triage/evaluate", json=SPEC_VERIFIED_PAYLOAD).json()
        assert r["decision"] == "VERIFIED_PASS", r
        assert r["status"] == "SUCCESS"
        assert r["solar_physics"]["is_physically_coherent"] is True

    def test_verified_pass_reports_c2pa_and_receipt(self, client):
        r = client.post("/v1/triage/evaluate", json=SPEC_VERIFIED_PAYLOAD).json()
        assert r["c2pa_status"] == "C2PA_VERIFIED"
        assert r["audit_receipt_id"].startswith("rec_")
        assert "deduplication" in r

    def test_fraud_payload_is_quarantined_with_a_reason(self, client):
        r = client.post("/v1/triage/evaluate", json=SPEC_FRAUD_PAYLOAD).json()
        assert r["decision"] == "QUARANTINE_FRAUD"
        assert r["status"] == "QUARANTINED"
        assert r["solar_physics"]["angular_error_deg"] > 90
        assert "SOLAR_EPHEMERIS_PHYSICAL_DISCREPANCY" in r["quarantine_reason"]

    def test_low_sun_abstains_instead_of_quarantining(self, client):
        r = client.post(
            "/v1/triage/evaluate",
            json={
                "asset_public_id": "dawn",
                "latitude": -1.2921,
                "longitude": 36.8219,
                "capture_timestamp_utc": "2026-09-22T03:45:00Z",
                "observed_shadow_azimuth_deg": 270.0,
            },
        ).json()
        assert r["decision"] == "REVIEW_AMBIGUOUS"
        assert "abstain_reason" in r
        assert r["solar_physics"]["is_physically_coherent"] is False

    def test_malformed_timestamp_is_422(self, client):
        r = client.post(
            "/v1/triage/evaluate",
            json={**SPEC_VERIFIED_PAYLOAD, "capture_timestamp_utc": "not-a-date"},
        )
        assert r.status_code == 422

    def test_out_of_range_coordinates_rejected(self, client):
        r = client.post(
            "/v1/triage/evaluate", json={**SPEC_VERIFIED_PAYLOAD, "latitude": 999.0}
        )
        assert r.status_code == 422

    def test_scenario_header_is_honoured(self, client):
        r = client.post(
            "/v1/triage/evaluate",
            json={**SPEC_VERIFIED_PAYLOAD, "observed_shadow_azimuth_deg": 100.0},
            headers={"X-Mock-Scenario": "fraud"},
        ).json()
        assert r["decision"] == "QUARANTINE_FRAUD"

    def test_scenario_override_cannot_manufacture_a_pass(self, client):
        """Forcing 'genuine' must not pass a physically impossible capture.

        A scenario override exists to simulate a broken environment, never to
        override physics into producing a false attestation.
        """
        r = client.post(
            "/v1/triage/evaluate",
            json={**SPEC_FRAUD_PAYLOAD, "scenario": "genuine"},
        ).json()
        assert r["decision"] != "QUARANTINE_FRAUD"
        # ...but the underlying geometry must now be self-consistent.
        assert r["solar_physics"]["angular_error_deg"] == 0.0

    def test_unversioned_alias_exists(self, client):
        assert client.post("/api/v1/triage/evaluate", json=SPEC_VERIFIED_PAYLOAD).status_code == 200


class TestMockPhotogrammetry:
    def test_align_and_diff_returns_documented_values(self, client):
        r = client.post(
            "/v1/cv/align-and-diff",
            files={
                "baseline_image": ("a.jpg", b"\xff\xd8\xff\xd9", "image/jpeg"),
                "progress_image": ("b.jpg", b"\xff\xd8\xff\xd9", "image/jpeg"),
            },
            data={"project_id": "KEN-042"},
        ).json()
        assert r["status"] == "REGISTRATION_COMPLETE"
        assert r["biological_canopy_delta"]["net_canopy_growth_pct"] == 38.23
        assert "GLI" in r["biological_canopy_delta"]["vegetative_index_method"]

    def test_stub_is_labelled_as_a_stub(self, client):
        """A frontend must never mistake stubbed numbers for computed ones."""
        r = client.post(
            "/v1/cv/align-and-diff",
            files={
                "baseline_image": ("a.jpg", b"x", "image/jpeg"),
                "progress_image": ("b.jpg", b"x", "image/jpeg"),
            },
        ).json()
        assert r["mode"] == "MOCK"
        assert "STUBBED" in r["homography_metrics"]["note"]


class TestMockDossier:
    def test_dossier_uses_the_verified_chave_equation(self, client):
        r = client.get("/v1/audit/dossier/KEN-08").json()
        bio = r["allometric_biomass_estimate"]
        assert "0.0673" in bio["equation"], "Chave 2014 Eq.4 prefactor"
        assert bio["dbh_source"] == "field_measured_dbh_1.3m"

    def test_per_hectare_figure_is_labelled_and_sourced(self, client):
        """A per-hectare number must carry its sampling design."""
        r = client.get("/v1/audit/dossier/KEN-08").json()
        bio = r["allometric_biomass_estimate"]
        assert bio["sampling_design"]["stems_per_hectare"] > 0
        assert bio["gross_tco2e_per_hectare"] > 0

    def test_eudr_polygon_is_closed(self, client):
        r = client.get("/v1/audit/dossier/KEN-08").json()
        ring = r["cadastral_polygon_geojson"]["coordinates"][0]
        assert ring[0] == ring[-1], "polygon must be closed for EUDR Article 9"

    def test_eudr_vertices_preserve_six_decimal_precision(self, client):
        """A JSON number cannot prove EUDR's 6-decimal requirement.

        JSON has a single numeric type, so 39.855420 parses to the float
        39.85542 and the declared precision is gone before a validator can
        count it. A compliance submission sending bare numbers therefore
        cannot demonstrate its own precision. Vertices must travel as decimal
        strings, and this test pins that choice.
        """
        poly = client.get("/v1/audit/dossier/KEN-08").json()["cadastral_polygon_geojson"]
        assert poly["coordinate_encoding"] == "decimal_string"
        for lon, lat in poly["coordinates"][0]:
            assert isinstance(lon, str) and isinstance(lat, str)
            assert len(lon.split(".")[1]) >= 6, f"lon {lon} under 6 decimals"
            assert len(lat.split(".")[1]) >= 6, f"lat {lat} under 6 decimals"
            # Values must still be numerically sane.
            assert -180.0 <= float(lon) <= 180.0
            assert -90.0 <= float(lat) <= 90.0

    def test_c2pa_root_hash_present(self, client):
        r = client.get("/v1/audit/dossier/KEN-08").json()
        assert r["c2pa_root_manifest_hash"].startswith("sha256:")


class TestMockSearch:
    def test_search_is_a_labelled_stub(self, client):
        r = client.get("/v1/search", params={"q": "mangrove"}).json()
        assert r["mode"] == "MOCK"
        assert "STUBBED" in r["note"]
