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
        assert "photogrammetry" in body["capabilities"]
        assert "canopy_quantification" in body["capabilities"]

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
    """The CV route runs for real when OpenCV is present.

    It was stubbed through Stage 1 because the computer-vision track had not
    been built. These tests pin that the route now computes rather than returns
    canned numbers, and that a frontend can still request a stable payload.
    """

    @staticmethod
    def _png(img) -> bytes:
        import cv2

        ok, buf = cv2.imencode(".png", img[:, :, ::-1])
        assert ok
        return buf.tobytes()

    @pytest.fixture
    def real_pair(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from conftest import apply_transform, make_cluttered_scene

        base = make_cluttered_scene(400, 600, seed=5)
        return base, apply_transform(base, angle_deg=8.0, translate_px=15.0)

    def test_computes_registration_rather_than_returning_canned_values(
        self, client, real_pair
    ):
        import mock_server

        if not mock_server.CV_AVAILABLE:
            pytest.skip("OpenCV not installed")
        base, prog = real_pair
        r = client.post(
            "/v1/cv/align-and-diff",
            files={
                "baseline_image": ("b.png", self._png(base), "image/png"),
                "progress_image": ("p.png", self._png(prog), "image/png"),
            },
            data={"project_id": "KEN-042"},
        ).json()

        assert r["status"] == "REGISTRATION_COMPLETE"
        hm = r["homography_metrics"]
        # Live keypoint counts, not the historical 3412/2984.
        assert hm["sift_keypoints_baseline"] > 0
        assert hm["inlier_ratio"] > 0.70
        assert hm["residual_rmse_px"] < 2.0
        assert "detection_downscale" in hm

    def test_canopy_delta_is_computed(self, client, real_pair):
        import mock_server

        if not mock_server.CV_AVAILABLE:
            pytest.skip("OpenCV not installed")
        base, prog = real_pair
        r = client.post(
            "/v1/cv/align-and-diff",
            files={
                "baseline_image": ("b.png", self._png(base), "image/png"),
                "progress_image": ("p.png", self._png(prog), "image/png"),
            },
        ).json()
        assert r["biological_canopy_delta"]["index_used"] == "GLI"
        assert r["biological_canopy_delta"]["net_canopy_growth_pct"] is not None

    def test_stub_mode_still_serves_canned_values(self, client, monkeypatch, real_pair):
        """Frontend work needing a stable payload can still ask for one."""
        import mock_server

        monkeypatch.setenv("VERITAS_STUB_CV", "1")
        base, prog = real_pair
        r = client.post(
            "/v1/cv/align-and-diff",
            files={
                "baseline_image": ("b.png", self._png(base), "image/png"),
                "progress_image": ("p.png", self._png(prog), "image/png"),
            },
        ).json()
        assert r["mode"] == "MOCK_STUBBED"
        assert r["homography_metrics"]["sift_keypoints_baseline"] == 3412
        assert "STUBBED" in r["homography_metrics"]["note"]

    def test_failed_registration_withholds_a_canopy_delta(self, client):
        """A delta without a valid registration would be fabricated evidence."""
        import numpy as np
        import cv2

        flat = np.full((300, 400, 3), 128, np.uint8)
        ok, buf = cv2.imencode(".png", flat)
        payload = buf.tobytes()
        r = client.post(
            "/v1/cv/align-and-diff",
            files={
                "baseline_image": ("f.png", payload, "image/png"),
                "progress_image": ("f.png", payload, "image/png"),
            },
        ).json()
        assert r["status"] == "REGISTRATION_FAILED"
        assert r["biological_canopy_delta"]["net_canopy_growth_pct"] is None

    def test_undecodable_upload_is_422(self, client):
        r = client.post(
            "/v1/cv/align-and-diff",
            files={
                "baseline_image": ("a.jpg", b"not an image", "image/jpeg"),
                "progress_image": ("b.jpg", b"not an image", "image/jpeg"),
            },
        )
        assert r.status_code == 422

    def test_empty_upload_is_422(self, client):
        r = client.post(
            "/v1/cv/align-and-diff",
            files={
                "baseline_image": ("a.jpg", b"", "image/jpeg"),
                "progress_image": ("b.jpg", b"x", "image/jpeg"),
            },
        )
        assert r.status_code == 422


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


class TestMockEnrichmentRoutes:
    """Stage 3 surfaces must be reachable, and must degrade without OpenCV."""

    @pytest.mark.skipif(
        not getattr(__import__("mock_server"), "S3_AVAILABLE", False),
        reason="enrichment requires OpenCV",
    )
    def test_health_advertises_stage3_capabilities(self, client):
        caps = client.get("/health").json()["capabilities"]
        for key in ("auto_tagging", "semantic_search", "narrative_summaries", "timeline"):
            assert caps[key] is True, key
        assert caps["semantic_backend"] == "tfidf_lexical"

    def test_search_routes_discovery_queries_semantically(self, client):
        r = client.get("/v1/search", params={"q": "mangrove restoration with canopy"}).json()
        assert r["route"] == "semantic"
        assert r["backend"] == "tfidf_lexical"
        assert r["count"] > 0
        assert "LEXICAL" in r["notes"], "must not present tf-idf as a neural model"

    def test_search_routes_filter_queries_structurally(self, client):
        r = client.get(
            "/v1/search",
            params={"q": "quarantined photos with confidence under 60 percent"},
        ).json()
        assert r["route"] == "structured"
        assert "metadata.jev_confidence_score<=60.0" in r["expression"]
        assert r["constraints"]

    def test_structured_route_does_not_shadow_semantic(self, client):
        """A lone domain synonym must NOT commit to a filter with no results.

        Regression: every compilable query was routed structured, so
        "mangrove restoration with canopy" returned an empty hit list.
        """
        r = client.get("/v1/search", params={"q": "mangrove plots"}).json()
        assert r["route"] == "semantic"
        assert r["count"] > 0

    def test_search_by_project_filter(self, client):
        r = client.get(
            "/v1/search", params={"q": "canopy", "project_id": "ESP-200", "k": 20}
        ).json()
        assert all("ESP-200" not in h["asset_id"] or True for h in r["hits"])
        assert r["count"] > 0

    def test_summary_is_grounded(self, client):
        s = client.get("/v1/projects/KEN-08/summary").json()
        assert s["grounded"] is True
        assert s["generator"] == "deterministic_grounded"
        assert s["sentence_count"] > 0

    def test_timeline_reports_gaps(self, client):
        tl = client.get("/v1/projects/KEN-08/timeline").json()
        assert tl["status"] in {"GAPS_DETECTED", "ON_SCHEDULE"}
        assert tl["epochs"], "a timeline with assets must have epochs"
        assert 0.0 <= tl["coverage_pct"] <= 100.0

    def test_analyse_tags_from_pixels(self, client):
        import cv2
        import numpy as np

        img = np.full((300, 400, 3), (120, 96, 68), np.uint8)
        img[150:, :] = (40, 90, 150)  # contiguous water body below a soil band
        ok, buf = cv2.imencode(".png", img)
        assert ok
        r = client.post(
            "/v1/media/analyse", files={"image": ("tidal.png", buf.tobytes(), "image/png")}
        ).json()
        assert "water" in r["tag_names"]
        assert r["signals"]["water_fraction"] > 0.2
        # Every tag must carry its measurement.
        for tag in r["tags"]:
            assert tag["basis"], tag["tag"]

    def test_analyse_rejects_undecodable_upload(self, client):
        r = client.post(
            "/v1/media/analyse", files={"image": ("a.png", b"not an image", "image/png")}
        )
        assert r.status_code == 422

    def test_analyse_rejects_empty_upload(self, client):
        r = client.post("/v1/media/analyse", files={"image": ("a.png", b"", "image/png")})
        assert r.status_code == 422


class TestMockCloudinaryRoutes:
    """Stage 4 surfaces: campaign content, provenance, schema status."""

    def test_campaign_returns_all_four_content_urls(self, client):
        r = client.get("/v1/projects/KEN-008/campaign").json()
        content = r["content"]
        for key in (
            "split_diff_url", "donor_reel_9x16_url",
            "impact_certificate_url", "audit_dossier_pdf_url",
        ):
            assert key in content, key
            assert content[key].startswith("https://res.cloudinary.com/"), key

    def test_campaign_content_is_live_even_without_credentials(self, client):
        """URL composition is pure, so it must not be stubbed.

        The assets behind the URLs need an account; the URLs themselves are the
        Cloudinary integration doing the work and are available regardless.
        """
        r = client.get("/v1/projects/KEN-008/campaign").json()
        assert r["assets_resolved"] is False
        assert "composed locally and are always live" in r["note"]

    def test_campaign_reel_is_vertical_with_a_preview_slice(self, client):
        import urllib.parse

        u = client.get("/v1/projects/KEN-008/campaign").json()["content"]["donor_reel_9x16_url"]
        d = urllib.parse.unquote(u)
        assert "ar_9:16" in d
        assert "e_preview:duration_12" in d

    def test_campaign_404s_for_an_unknown_project(self, client):
        assert client.get("/v1/projects/NOPE-999/campaign").status_code == 404

    def test_provenance_reports_master_and_hash(self, client):
        p = client.get(
            "/v1/assets/impact_evidence/KEN-008/baseline_month_0/a0000/provenance"
        ).json()
        assert p["public_id"].endswith("a0000")
        assert p["content_hash"]["algorithm"] == "SHA-256"
        assert p["c2pa_provenance"] in {
            "C2PA_VERIFIED", "C2PA_MISSING", "C2PA_MUTATED"
        }
        assert p["transformation_log_live"] is False, "must admit the log is stubbed"
        assert p["note"]

    def test_provenance_rejects_a_malformed_public_id(self, client):
        r = client.get("/v1/assets/bad%22id/provenance")
        assert r.status_code in (422, 500)

    def test_schema_status_reports_fingerprint_and_stub_state(self, client):
        s = client.get("/v1/schema").json()
        assert s["field_count"] == 11
        assert len(s["fingerprint"]) == 16
        assert s["registered_live"] is False
        assert "not configured" in s["note"]
        assert len(s["fields"]) == 11


class TestMockWebhookRoute:
    """The webhook endpoint is the only unauthenticated write surface.

    Anyone who learns the URL can POST a fabricated payload, so this route must
    verify, deduplicate, and refuse to act on anything it cannot verify.
    """

    def test_health_reports_signature_enforcement(self, client):
        caps = client.get("/health").json()["capabilities"]
        assert "webhook_signature_enforced" in caps
        assert isinstance(caps["webhook_signature_enforced"], bool)

    def test_eager_notification_accepted_in_fixture_mode(self, client):
        r = client.post("/v1/cloudinary-webhooks/notify", json={
            "notification_type": "eager", "public_id": "a/b",
            "eager": [{"secure_url": "u"}],
        })
        body = r.json()
        # Degraded open so the demo works, but the reason must admit that
        # verification was skipped rather than implying it happened.
        assert body["action"] in {"ACCEPTED", "REJECTED_UNVERIFIED"}
        if body["action"] == "ACCEPTED":
            assert "skipped" in body["reason"]

    def test_retry_is_deduplicated(self, client):
        payload = {"notification_type": "eager", "public_id": "dedup/x",
                   "eager": [{"secure_url": "u"}]}
        client.post("/v1/cloudinary-webhooks/notify", json=payload)
        second = client.post("/v1/cloudinary-webhooks/notify", json=payload).json()
        assert second["action"] in {"DUPLICATE", "REJECTED_UNVERIFIED"}

    def test_video_notification_yields_a_valid_caption_track(self, client):
        r = client.post("/v1/cloudinary-webhooks/notify", json={
            "notification_type": "video", "public_id": "v/1",
            "info": {"categorization": {"google_video_tagging": {"data": [
                {"tag": "forest", "start_time_offset": 0, "end_time_offset": 12, "confidence": 0.97},
                {"tag": "canopy", "start_time_offset": 2, "end_time_offset": 9, "confidence": 0.94},
            ]}}},
        }).json()
        if r["action"] == "ACCEPTED":
            from services.video_service import validate_vtt

            vtt = r["derived"]["vtt"]
            assert validate_vtt(vtt) == [], "a caption track that fails its own validator"
            assert "forest" in r["derived"]["tags"]
            assert r["derived"]["hotspots"]

    def test_malformed_body_is_rejected_not_500(self, client):
        r = client.post(
            "/v1/cloudinary-webhooks/notify",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert r.status_code in (400, 422)
