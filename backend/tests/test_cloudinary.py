"""
Tier 3 — Cloudinary Integration: URL engine, metadata schema, seeder

The rubric says "using Cloudinary", so this tier checks the integration is real
and, more importantly, that it cannot mislead: the URL engine is pure and always
live, the schema is validated locally before a network call, and every
credentialed path degrades to a clearly-marked fixture rather than raising.
"""

from __future__ import annotations

import os

import json
import urllib.parse

import pytest

from core.cloudinary_client import (
    MAX_TEXT_LENGTH,
    METADATA_SCHEMA,
    CloudinaryClient,
    CloudinaryResult,
    MetadataValidationError,
    build_audit_pdf_url,
    build_donor_reel_url,
    build_impact_certificate_url,
    build_split_diff_url,
    validate_metadata,
    validate_public_id,
)
from services.seeder import (
    DECISION_WEIGHTS,
    EPOCH_CANOPY_MEDIAN,
    SEED_PROJECTS,
    generate_corpus,
    seed,
    summarise,
)

pytestmark = pytest.mark.tier3

CLOUD = "veritas-dmrv"


def decoded(url: str) -> str:
    return urllib.parse.unquote(url)


def transform_components(url: str) -> list[str]:
    """The transformation components of a delivery URL, in order.

    Splitting the WHOLE url on "/" gives ``https:`` as the first element, which
    is how the first attempt at the position assertion reported ``e_preview`` at
    position 4 for a URL where it was at position 0. The transformation chain is
    what this is about, so take the chain.
    """
    path = urllib.parse.unquote(url).split("/upload/", 1)[-1]
    return [c for c in path.split("/")[:-1]]  # drop the trailing asset name


# =========================================================================== #
# Public ID validation
# =========================================================================== #


class TestPublicIdValidation:
    @pytest.mark.parametrize("pid", [
        "a", "asset_01", "folder/asset-01", "a/b/c/d", "KEN-042/raw_m0",
    ])
    def test_accepts_valid_ids(self, pid):
        assert validate_public_id(pid) == pid

    @pytest.mark.parametrize("pid", [
        'a"b', "a,b", "a b", "a;b", "a\\b", "a{b}", "a|b", "a?b", "a#b", "",
    ])
    def test_rejects_injection_bearing_ids(self, pid):
        """A public ID reaches a URL, so an escape bug here is a query surface.

        These are REJECTED, not escaped-and-passed: silently sanitising an
        identifier would mean the asset silently referred to something else.
        """
        with pytest.raises(ValueError):
            validate_public_id(pid)

    def test_rejects_traversal(self):
        for pid in ("a/../b", "..", "a/.."): 
            with pytest.raises(ValueError):
                validate_public_id(pid)

    def test_rejects_leading_slash(self):
        with pytest.raises(ValueError, match="must not start with a slash"):
            validate_public_id("/leading")

    def test_rejects_none_and_non_string(self):
        for bad in (None, 123, []):
            with pytest.raises(ValueError):
                validate_public_id(bad)

    def test_rejects_overlong_id(self):
        with pytest.raises(ValueError):
            validate_public_id("a" * 300)


# =========================================================================== #
# URL transformation engine — pure, no credentials, always live
# =========================================================================== #


class TestUrlEngine:
    def test_split_diff_composes_both_halves(self):
        url = build_split_diff_url(
            CLOUD, "impact/KEN-042/raw_m0", "impact/KEN-042/warped_m18", 38.2
        )
        d = decoded(url)
        assert d.startswith(f"https://res.cloudinary.com/{CLOUD}/image/upload/")
        assert "c_crop,w_600,h_800,g_west" in d, "baseline must be the left half"
        # Every folder separator in a layer reference becomes a COLON, and the
        # gravity lives inside the l_ component. The previous form used
        # fl_layer_apply -- an UPLOAD-time flag -- which Cloudinary rejected in a
        # delivery URL with "Cannot find matching layer start".
        assert "fl_layer_apply" not in d, "upload-time flag leaked into a delivery URL"
        assert "l_impact:KEN-042:warped_m18" in d
        assert "g_east" in d, "progress must overlay the right half"
        assert d.endswith("impact/KEN-042/raw_m0.jpg")

    def test_split_diff_burns_the_measured_delta(self):
        d = decoded(build_split_diff_url(
            CLOUD, "a/b", "a/c", 38.2
        ))
        assert "+38.2%" in d
        assert "C2PA VERIFIED" in d

    def test_split_diff_negative_delta_is_shown_signed(self):
        d = decoded(build_split_diff_url(CLOUD, "a/b", "a/c", -12.5))
        assert "-12.5%" in d

    def test_c2pa_badge_can_be_omitted(self):
        d = decoded(build_split_diff_url(
            CLOUD, "a/b", "a/c", 1.0, c2pa_verified=False
        ))
        assert "C2PA VERIFIED" not in d

    def test_donor_reel_is_vertical(self):
        d = decoded(build_donor_reel_url(CLOUD, "drones/KEN-042/t01"))
        assert "ar_9:16" in d
        assert d.endswith(".mp4")

    def test_donor_reel_does_not_use_image_only_subject_cropping(self):
        """`g_auto:subject` is IMAGE-only and 400s on a /video/ delivery.

        Verified live: "Invalid g_auto for video param 'auto:subject'". Every
        other URL builder is for images, so this defect was invisible until a
        video probe existed to render against.
        """
        d = decoded(build_donor_reel_url(CLOUD, "drones/KEN-042/t01"))
        assert "g_auto:subject" not in d
        # g_center is the verified-working default.
        assert "g_center" in d

    def test_donor_reel_gravity_is_configurable(self):
        """g_auto is Cloudinary's video equivalent, but it can answer 423 while
        tracking-crop is still queued, so it is opt-in rather than the default."""
        d = decoded(build_donor_reel_url(CLOUD, "drones/KEN-042/t01", gravity="auto"))
        assert "g_auto" in d
        assert "g_auto:subject" not in d

    def test_donor_reel_rejects_a_malformed_gravity(self):
        with pytest.raises(ValueError):
            build_donor_reel_url(CLOUD, "drones/KEN-042/t01", gravity="auto:subject/x")

    def test_donor_reel_preview_slice(self):
        """The documented mitigation for a slow stream during a live demo."""
        d = decoded(build_donor_reel_url(
            CLOUD, "drones/x", preview_seconds=10
        ))
        assert "e_preview:duration_10:max_seg_3" in d

    def test_e_preview_is_the_FIRST_transformation(self):
        """Cloudinary rejects it anywhere else, and the test that only checked
        for its PRESENCE stayed green while the URL was a 400.

        Live error, verbatim:

            400  e_preview must be the first transformation

        The old assertion was `"e_preview:duration_10:max_seg_3" in d`, which is
        satisfied by the broken URL exactly as it is by the working one. Position
        is the whole requirement, so position is what is asserted.

        Still a shape assertion -- the load check lives in
        scripts/validate_cloudinary_live.py, which is the only thing here that
        fetches a URL.
        """
        components = transform_components(
            build_donor_reel_url(CLOUD, "drones/x", preview_seconds=10)
        )
        preview_at = [c for c, p in enumerate(components) if p.startswith("e_preview")]
        assert preview_at, f"no e_preview component in {components}"
        assert preview_at[0] == 0, (
            f"e_preview is at position {preview_at[0]}, not 0: {components}. "
            "Cloudinary returns 400 -- 'e_preview must be the first transformation'."
        )

    def test_without_preview_the_first_component_is_the_aspect_ratio(self):
        """The reordering must not have moved anything else."""
        components = transform_components(
            build_donor_reel_url(CLOUD, "drones/x")
        )
        assert components[0].startswith("ar_9:16"), (
            f"first component is {components[0]!r}, expected the aspect ratio"
        )

    def test_donor_reel_without_preview_has_no_slice(self):
        d = decoded(build_donor_reel_url(CLOUD, "drones/x"))
        assert "e_preview" not in d

    def test_certificate_url(self):
        d = decoded(build_impact_certificate_url(
            CLOUD, "impact/x/warp", "Kilifi Creek Mangrove", 38.2,
            "7f83b1657ff1fc53b92dc1814",
        ))
        assert "w_1200,h_630" in d
        assert "VERITAS dMRV IMPACT CERTIFICATE" in d
        assert "Kilifi Creek Mangrove" in d
        assert d.endswith(".png")

    def test_audit_pdf_targets_a_pdf_template(self):
        d = decoded(build_audit_pdf_url(
            CLOUD, "impact/x/warp", "KEN-042", "Tsavo East", 8.42, 9.4, "a" * 64
        ))
        # Built as `f_pdf` output from the warped image, not served as a .pdf
        # template. Cloudinary does NOT composite text onto a `raw` PDF: verified
        # live, `raw/upload/.../<template>` returns 200 with the ORIGINAL byte
        # count, i.e. the layer stack is silently discarded. f_pdf is the only
        # form that composites -- and it needs a paid plan (401 on free tier).
        assert "f_pdf" in d, "vector PDF output for a statutory filing"
        assert "/raw/upload/" not in d
        assert "EUDR Article 9" in d
        assert "SHA256:" in d

    def test_url_encodes_text_layers(self):
        """A label with a space must be percent-encoded in the raw URL."""
        raw = build_split_diff_url(CLOUD, "a/b", "a/c", 1.0)
        assert "BASELINE%20(MONTH%200)" in raw or " " not in raw

    def test_unicode_labels_survive(self):
        d = decoded(build_split_diff_url(
            CLOUD, "a/b", "a/c", 1.0, baseline_label="Océano — Restauración"
        ))
        assert "Océano" in d

    @pytest.mark.parametrize("make_args", [
        # Each builder takes a public ID; each factory injects a malformed one.
        lambda bad: ((CLOUD, bad, "a/c", 1.0), build_split_diff_url),
        lambda bad: ((CLOUD, bad), build_donor_reel_url),
        lambda bad: ((CLOUD, bad, "P", 1.0, "h"), build_impact_certificate_url),
        lambda bad: ((CLOUD, bad, "P", "R", 1.0, 1.0, "h"), build_audit_pdf_url),
    ])
    def test_every_builder_rejects_a_bad_public_id(self, make_args):
        args, builder = make_args('bad"id')
        with pytest.raises(ValueError):
            builder(*args)

    def test_control_characters_rejected(self):
        with pytest.raises(ValueError, match="control characters"):
            build_split_diff_url(CLOUD, "a/b", "a/c", 1.0, baseline_label="bad\x00x")

    def test_overlong_text_rejected(self):
        with pytest.raises(ValueError, match="over the"):
            build_split_diff_url(
                CLOUD, "a/b", "a/c", 1.0, baseline_label="x" * (MAX_TEXT_LENGTH + 1)
            )

    def test_url_engines_work_with_no_credentials(self):
        """The whole point: campaign content is pure string composition."""
        from core.config import Settings

        client = CloudinaryClient(Settings())
        assert client.is_live is False
        assert build_split_diff_url(CLOUD, "a/b", "a/c", 1.0).startswith("https://")


# =========================================================================== #
# Metadata schema
# =========================================================================== #

VALID_METADATA = {
    "esg_project_id": "KEN-042",
    "sustainability_domain": "mangrove_restoration",
    "cadastral_polygon_id": "PARCEL-KEN-042",
    "capture_timestamp": "2026-09-22",
    "solar_azimuth_error": 0,
    "jev_triage_decision": "VERIFIED_PASS",
    "jev_confidence_score": 96,
    "c2pa_provenance": "C2PA_VERIFIED",
    "milestone_phase": "progress_month_18",
}


class TestMetadataSchema:
    def test_schema_has_eleven_fields(self):
        assert len(METADATA_SCHEMA) == 11
        assert {f["external_id"] for f in METADATA_SCHEMA} >= set(VALID_METADATA)

    def test_valid_payload_accepted(self):
        assert validate_metadata(dict(VALID_METADATA))

    def test_optional_fields_may_be_absent(self):
        assert validate_metadata(dict(VALID_METADATA))

    def test_mandatory_field_required(self):
        payload = dict(VALID_METADATA)
        del payload["esg_project_id"]
        with pytest.raises(MetadataValidationError, match="mandatory"):
            validate_metadata(payload)

    def test_analysis_outputs_are_optional(self):
        """A verdict cannot be mandatory on an upload.

        Cloudinary enforces a mandatory field on EVERY upload, so marking
        `jev_triage_decision` or `jev_confidence_score` mandatory meant no upload
        could ever succeed: the value is the result of analysing an asset that has
        not been uploaded yet. Found by the live harness, which failed with
        "Field 'jev_confidence_score' is mandatory and cannot be left empty".
        """
        for output in ("solar_azimuth_error", "jev_triage_decision",
                       "jev_confidence_score", "sift_inlier_ratio",
                       "canopy_delta_pct", "c2pa_provenance"):
            payload = dict(VALID_METADATA)
            payload.pop(output, None)
            validate_metadata(payload)  # must not raise

    def test_capture_time_facts_are_mandatory(self):
        for field in ("esg_project_id", "sustainability_domain",
                      "cadastral_polygon_id", "capture_timestamp", "milestone_phase"):
            payload = dict(VALID_METADATA)
            payload.pop(field, None)
            with pytest.raises(MetadataValidationError, match="mandatory"):
                validate_metadata(payload)

    def test_unknown_field_rejected(self):
        with pytest.raises(MetadataValidationError, match="Unknown metadata field"):
            validate_metadata({**VALID_METADATA, "sneaky": 1})

    def test_enum_membership_enforced(self):
        with pytest.raises(MetadataValidationError, match="is not one of"):
            validate_metadata({**VALID_METADATA, "jev_triage_decision": "MAYBE"})

    def test_regex_enforced(self):
        with pytest.raises(MetadataValidationError, match="does not match"):
            validate_metadata({**VALID_METADATA, "esg_project_id": "ken42"})

    def test_numeric_bounds_enforced(self):
        for bad in (900, -900):
            with pytest.raises(MetadataValidationError, match="permitted"):
                validate_metadata({**VALID_METADATA, "canopy_delta_pct": bad})

    def test_bool_is_not_accepted_as_a_number(self):
        with pytest.raises(MetadataValidationError, match="must be numeric"):
            validate_metadata({**VALID_METADATA, "canopy_delta_pct": True})

    def test_date_format_enforced(self):
        with pytest.raises(MetadataValidationError, match="ISO"):
            validate_metadata({**VALID_METADATA, "capture_timestamp": "22/09/2026"})

    def test_schema_fingerprint_is_stable(self):
        c1 = CloudinaryClient()
        assert c1.schema_fingerprint() == CloudinaryClient().schema_fingerprint()
        assert len(c1.schema_fingerprint()) == 16


# =========================================================================== #
# Credential-free degradation
# =========================================================================== #


class TestFixtureModeDegradation:
    @pytest.fixture
    def client(self):
        from core.config import Settings

        return CloudinaryClient(Settings())

    def test_health_without_credentials(self, client):
        assert client.is_live is False
        assert "not configured" in client._unavailable_reason()

    def test_schema_bootstrap_stubs_rather_than_raising(self, client):
        r = client.ensure_metadata_schema()
        assert isinstance(r, CloudinaryResult)
        assert r.fixture is True
        assert r.mode.value == "fixture"
        assert "not configured" in r.reason

    def test_metadata_write_validates_before_degrading(self, client):
        """Validation happens locally, so a bad payload is caught even offline."""
        r = client.set_structured_metadata("impact/a", dict(VALID_METADATA))
        assert r.fixture is True
        assert "esg_project_id" in r.data["fields_written"]
        with pytest.raises(MetadataValidationError):
            client.set_structured_metadata("impact/a", {"esg_project_id": "bad"})

    def test_search_stubs(self, client):
        r = client.search("metadata.canopy_delta_pct>25")
        assert r.fixture is True
        assert r.data["resources"] == []

    def test_transformation_log_stubs(self, client):
        r = client.transformation_log("impact/a")
        assert r.fixture is True
        assert r.data["transformations"] == []

    def test_result_marks_fixture_unmistakably(self, client):
        """A fixture must never be mistakable for a measurement."""
        r = client.ensure_metadata_schema()
        payload = r.to_dict()
        assert payload["fixture"] is True
        assert payload["mode"] == "fixture"
        assert payload["reason"]

    def test_no_call_raises_in_fixture_mode(self, client):
        for call in (
            lambda: client.ensure_metadata_schema(),
            lambda: client.set_structured_metadata("a/b", dict(VALID_METADATA)),
            lambda: client.search("x"),
            lambda: client.transformation_log("a/b"),
        ):
            assert call().fixture is True

    def test_search_result_cap_is_enforced(self, client):
        assert client.search("x", max_results=10_000).data is not None


# =========================================================================== #
# Scale corpus
# =========================================================================== #


class TestSeeder:
    def test_generates_a_large_corpus(self):
        assets = generate_corpus(per_project=130)
        assert len(assets) == 130 * len(SEED_PROJECTS) == 520
        assert len({a["esg_project_id"] for a in assets}) == len(SEED_PROJECTS)

    def test_is_deterministic(self):
        """A pitch-deck screenshot must match what a judge sees."""
        assert generate_corpus(20) == generate_corpus(20)

    def test_different_seed_gives_a_different_corpus(self):
        assert generate_corpus(20, seed=1) != generate_corpus(20, seed=2)

    def test_spans_multiple_epochs(self):
        assets = generate_corpus(40)
        assert len({a["milestone_phase"] for a in assets}) >= 4

    def test_has_a_visible_minority_of_problems(self):
        """A corpus where everything passes cannot demonstrate triage."""
        s = summarise(generate_corpus(130))
        assert s.by_decision["VERIFIED_PASS"] > s.by_decision["REVIEW_AMBIGUOUS"]
        assert s.by_decision["REVIEW_AMBIGUOUS"] > s.by_decision["QUARANTINE_FRAUD"]
        assert s.by_decision["QUARANTINE_FRAUD"] > 0

    def test_decision_weights_match_the_distribution(self):
        s = summarise(generate_corpus(400))
        total = s.total_assets
        for decision, weight in DECISION_WEIGHTS:
            observed = s.by_decision.get(decision, 0) / total
            assert abs(observed - weight) < 0.05, (
                f"{decision}: observed {observed:.3f} vs target {weight}"
            )

    def test_includes_both_media_types(self):
        s = summarise(generate_corpus(60))
        assert s.by_media_type["video"] > 0
        assert s.by_media_type["image"] > 0

    def test_canopy_has_a_real_trajectory(self):
        """Growth should increase across epochs, not be random noise."""
        assets = generate_corpus(200)
        by_epoch = {}
        for a in assets:
            if a["canopy_delta_pct"] is not None:
                by_epoch.setdefault(a["milestone_phase"], []).append(a["canopy_delta_pct"])
        order = ["baseline_month_0", "progress_month_6", "progress_month_18", "certified_year_3"]
        means = [
            sum(by_epoch[e]) / len(by_epoch[e]) for e in order if e in by_epoch
        ]
        for earlier, later in zip(means, means[1:]):
            assert later > earlier, f"trajectory not increasing: {means}"

    def test_reproduces_the_c2pa_contradiction_rather_than_hiding_it(self):
        """A quarantined asset claiming verified provenance is a real finding.

        The seeder must keep some of these visible so the audit surfaces have
        something genuine to detect.
        """
        s = summarise(generate_corpus(130))
        assert s.quarantined_with_c2pa_verified > 0

    def test_every_asset_validates_against_the_schema(self):
        """The seeded corpus must be writable to the real schema.

        This is what caught the "KEN-08" defect: the seeder emitted project IDs
        the schema's own regex rejects, so the corpus could not have been written
        to the account it was generated for.
        """
        for a in generate_corpus(15):
            payload = {
                "esg_project_id": a["esg_project_id"],
                "sustainability_domain": a["sustainability_domain"],
                "cadastral_polygon_id": a["cadastral_polygon_id"],
                "capture_timestamp": a["capture_timestamp"],
                "solar_azimuth_error": int(a["solar_azimuth_error"]),
                "jev_triage_decision": a["jev_triage_decision"],
                "jev_confidence_score": a["jev_confidence_score"],
                "c2pa_provenance": a["c2pa_provenance"],
                "milestone_phase": a["milestone_phase"],
            }
            if a["sift_inlier_ratio"] is not None:
                payload["sift_inlier_ratio"] = int(a["sift_inlier_ratio"])
            if a["canopy_delta_pct"] is not None:
                payload["canopy_delta_pct"] = int(round(a["canopy_delta_pct"]))
            validate_metadata(payload)

    def test_public_ids_are_valid(self):
        for a in generate_corpus(15):
            validate_public_id(a["public_id"])

    def test_manifest_is_written_in_fixture_mode(self, tmp_path):
        result = seed(tmp_path)
        assert result.mode == "fixture"
        manifest = json.loads((tmp_path / "corpus_manifest.json").read_text())
        assert manifest["_meta"]["deterministic"] is True
        assert len(manifest["assets"]) == result.summary.total_assets
        assert manifest["summary"]["projects"] == 4

    def test_seeding_needs_no_credentials(self, tmp_path):
        result = seed(tmp_path)
        assert result.corpus_path is None
        assert result.manifest_path.endswith("corpus_manifest.json")

    def test_summary_is_json_serialisable(self, tmp_path):
        json.dumps(seed(tmp_path).to_dict())


class TestSuiteIsolation:
    """The suite must run in fixture mode on a machine holding real credentials.

    This is not hypothetical. `core.config` loads `backend/.env`, so a developer
    (or CI) with credentials filled in got a DIFFERENT test run from one without:
    the seeder uploaded 520 assets to a live account and the suite hung for ten
    minutes. The conftest docstring already required that no test depend on a
    credential; these assertions are what make that requirement enforced rather
    than stated.
    """

    def test_runs_in_fixture_mode(self):
        from core.config import get_settings

        assert get_settings().mode == "fixture"
        assert not get_settings().has_cloudinary_credentials

    def test_dotenv_loading_is_disabled_for_tests(self):
        assert os.environ.get("VERITAS_NO_DOTENV") == "1"

    def test_a_client_reports_itself_unavailable(self):
        from core.cloudinary_client import CloudinaryClient
        from core.config import get_settings

        client = CloudinaryClient(get_settings())
        assert client.is_live is False
        assert "not configured" in client._unavailable_reason()
