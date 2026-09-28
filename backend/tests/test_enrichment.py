"""
Tier 3 — Enrichment, Semantic Search, Query Compilation, Narrative & Timeline

Covers rubric bullets 2 (identify visual signals), 4 (summaries) and 5 (AI
metadata, tagging, semantic discovery), plus the timeline requirement named in
the brief's opening line.

Several tests are regression guards for defects found while building these
modules. The notable ones:

* ``TestGrounding::test_rounded_integer_is_not_a_valid_rendering`` — an earlier
  version of the grounding whitelist included ``round(8.42) -> "8"``, so a
  fabricated "8.0" passed against a source of 8.42 tCO2e/ha. Rounding a carbon
  volume to a whole number lets it be read as a count, which is precisely the
  quiet corruption the check exists to prevent.
* ``TestQueryCompilation::test_comparator_is_inside_the_match`` — the
  comparator search looked *before* the match, so "confidence under 60"
  compiled to ``>= 60``.
* ``TestTimeline::test_asset_is_counted_in_exactly_one_epoch`` — pooling the
  date window with the declared phase counted 12 assets as 24.
* ``TestHueBands`` — hue constants were written against OpenCV's 0-179 scale
  while the code converted to degrees, so green vegetation measured 0.000.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from conftest import make_cluttered_scene, make_soil_scene
from services.enrichment_service import (
    BAND_BLUE,
    BAND_BROWN,
    BAND_GREEN,
    BAND_YELLOW,
    Tag,
    TagEvidence,
    assert_tags_are_grounded,
    enrich_asset,
    fuse_cloudinary_tags,
    measure_image,
)
from services.narrative_service import (
    GroundingError,
    ProjectFacts,
    build_grounded_summary,
    enhance_with_llm,
    extract_numbers,
    assert_summary_is_grounded,
)
from services.query_service import (
    QueryCompilationError,
    compile_query,
)
from services.semantic_service import (
    SemanticIndex,
    TfIdfSemanticBackend,
    build_index_document,
    tokenize,
)
from services.timeline_service import (
    AssetRecord,
    EpochStatus,
    TimelineStatus,
    add_months,
    build_timeline,
    months_between,
)

pytestmark = pytest.mark.tier3


# =========================================================================== #
# Hue bands
# =========================================================================== #


class TestHueBands:
    def test_bands_are_in_degrees_not_opencv_units(self):
        """OpenCV hue is 0-179. These constants are on the 0-360 wheel."""
        assert BAND_BROWN == (0.0, 45.0)
        assert BAND_YELLOW == (45.0, 75.0)
        assert BAND_GREEN == (75.0, 165.0)
        assert BAND_BLUE == (195.0, 270.0)

    def test_green_pixels_land_in_the_green_band(self):
        img = np.zeros((40, 40, 3), np.uint8)
        img[:, :] = (58, 150, 52)  # canopy green, hue ~120 deg
        s = measure_image(img)
        assert s.green_fraction > 0.9, f"got {s.green_fraction}"

    def test_soil_pixels_land_in_the_brown_band(self):
        img = np.zeros((40, 40, 3), np.uint8)
        img[:, :] = (128, 96, 68)  # soil, hue ~30 deg
        s = measure_image(img)
        assert s.brown_fraction > 0.9, f"got {s.brown_fraction}"

    def test_dry_grass_lands_in_the_yellow_band(self):
        img = np.zeros((40, 40, 3), np.uint8)
        img[:, :] = (150, 160, 60)
        s = measure_image(img)
        assert s.yellow_fraction > 0.5, f"got {s.yellow_fraction}"

    def test_water_lands_in_the_blue_band(self):
        img = np.zeros((40, 40, 3), np.uint8)
        img[:, :] = (40, 90, 150)
        s = measure_image(img)
        assert s.blue_fraction > 0.9, f"got {s.blue_fraction}"


# =========================================================================== #
# Enrichment / auto-tagging
# =========================================================================== #


class TestEnrichment:
    def test_bare_soil_is_tagged_not_canopy(self):
        result = enrich_asset(make_soil_scene(canopy_fraction=0.02, seed=1), "bare")
        names = result.tag_names()
        assert Tag.BARE_SOIL in names
        assert Tag.CANOPY not in names
        assert Tag.WATER not in names, "dry soil must not be tagged as water"

    def test_dense_vegetation_is_tagged_canopy(self):
        result = enrich_asset(make_soil_scene(canopy_fraction=0.55, seed=2), "dense")
        names = result.tag_names()
        assert Tag.CANOPY in names
        assert Tag.FOREST in names

    def test_every_tag_cites_its_measurement(self):
        result = enrich_asset(make_soil_scene(canopy_fraction=0.3, seed=3), "m")
        assert_tags_are_grounded(result)
        for t in result.tags:
            assert t.basis, f"{t.tag} has no basis"
            if t.evidence == TagEvidence.PIXEL:
                assert "=" in t.basis, f"{t.tag} pixel basis must cite a value"

    def test_grounded_guard_rejects_an_invented_tag(self):
        from services.enrichment_service import TagHit, EnrichmentResult

        bad = EnrichmentResult(
            asset_id="x", tags=[TagHit("canopy", 0.9, TagEvidence.PIXEL, "")], signals={}
        )
        with pytest.raises(ValueError, match="no basis"):
            assert_tags_are_grounded(bad)

    def test_grounded_guard_rejects_a_basis_without_a_value(self):
        from services.enrichment_service import TagHit, EnrichmentResult

        bad = EnrichmentResult(
            asset_id="x", tags=[TagHit("canopy", 0.9, TagEvidence.PIXEL, "looks green")],
            signals={},
        )
        with pytest.raises(ValueError, match="measured value"):
            assert_tags_are_grounded(bad)

    def test_tolerates_a_frame_with_no_vegetation_signal(self):
        """Open water and flat frames must still be taggable."""
        flat = np.full((300, 400, 3), 128, np.uint8)
        result = enrich_asset(flat, "flat")
        assert result.signals["canopy_detectable"] is False
        assert result.signals["canopy_cover"] == 0.0
        assert Tag.CANOPY not in result.tag_names()

    def test_water_needs_a_contiguous_body(self):
        """Scattered blue patches are not a lake."""
        h, w = 400, 600
        img = np.full((h, w, 3), (120, 96, 68), np.uint8)
        import cv2

        for i in range(40):
            cv2.circle(
                img,
                (int(np.random.default_rng(i).integers(0, w)),
                 int(np.random.default_rng(i + 99).integers(0, h))),
                12, (40, 90, 150), -1,
            )
        result = enrich_asset(img, "scattered blue")
        assert result.signals["water_fraction"] == 0.0

    def test_context_phase_adds_programme_tags(self):
        result = enrich_asset(
            make_soil_scene(canopy_fraction=0.3, seed=3), "m",
            context={
                "milestone_phase": "progress_month_18",
                "sustainability_domain": "mangrove_restoration",
                "media_type": "image",
            },
        )
        names = result.tag_names()
        assert Tag.PROGRESS in names
        assert Tag.MANGROVE in names
        assert Tag.RESTORATION_SITE in names
        assert Tag.STILL in names
        for t in result.tags:
            if t.tag in (Tag.PROGRESS, Tag.MANGROVE):
                assert t.evidence == TagEvidence.CONTEXT

    def test_media_type_video(self):
        result = enrich_asset(
            make_soil_scene(canopy_fraction=0.3, seed=3), "v",
            context={"media_type": "video"},
        )
        assert Tag.VIDEO in result.tag_names()

    def test_result_is_json_serialisable(self):
        import json

        payload = enrich_asset(make_soil_scene(canopy_fraction=0.3, seed=3), "m").to_dict()
        json.dumps(payload)

    def test_rejects_empty_image(self):
        with pytest.raises(ValueError):
            measure_image(np.zeros((0, 0, 3), np.uint8))


class TestCloudinaryFusion:
    def test_ai_tag_is_added_when_no_local_evidence(self):
        merged, added, conflicts = fuse_cloudinary_tags([], {"forest": 0.9})
        assert [t.tag for t in merged] == [Tag.FOREST.value]
        assert added == {"forest": 0.9}
        assert conflicts == []

    def test_weak_ai_tag_cannot_contradict_a_measurement(self):
        """A local measurement outranks a weak AI suggestion."""
        from services.enrichment_service import TagHit

        local = [TagHit(Tag.CANOPY.value, 0.92, TagEvidence.PIXEL, "canopy_cover=0.42")]
        merged, added, conflicts = fuse_cloudinary_tags(local, {"vegetation": 0.2})
        assert len(merged) == 1, "the weak AI tag must not add a second entry"
        assert conflicts[0]["resolution"] == "kept_local"
        assert conflicts[0]["tag"] == Tag.CANOPY.value

    def test_unmapped_ai_tags_are_dropped(self):
        merged, added, _ = fuse_cloudinary_tags([], {"zzzz": 0.99})
        assert merged == [] and added == {}, "vocabulary must stay closed"

    def test_no_cloudinary_input_changes_nothing(self):
        merged, added, conflicts = fuse_cloudinary_tags([], None)
        assert merged == [] and added == {} and conflicts == []


# =========================================================================== #
# Semantic search
# =========================================================================== #


def _seed_index() -> SemanticIndex:
    index = SemanticIndex(TfIdfSemanticBackend())
    corpus = [
        ("mangrove-1", ["canopy", "mangrove", "water", "restoration_site"], "KEN-08", 42.0),
        ("mangrove-2", ["canopy", "mangrove", "water"], "KEN-08", 38.2),
        ("mangrove-3", ["canopy", "mangrove", "water", "tidal"], "KEN-08", 51.0),
        ("pine-1", ["canopy", "forest", "dryland"], "TUR-101", 12.0),
        ("pine-2", ["forest", "bare_soil", "overcast"], "TUR-101", -3.0),
        ("solar-1", ["infrastructure", "urban", "harsh_sun"], "ESP-200", 0.0),
        ("solar-2", ["infrastructure", "sky", "bare_soil"], "ESP-200", 0.0),
    ]
    for asset_id, tags, project, delta in corpus:
        index.add(build_index_document(asset_id, tags, project_id=project, canopy_delta_pct=delta))
    return index


class TestSemanticIndex:
    def test_finds_the_right_group(self):
        """The mangrove set must outrank every other group.

        Ordering WITHIN the group is not asserted: tf-idf correctly ranks a
        shorter, more query-focused document above a longer one that shares the
        same terms, so mangrove-2 legitimately precedes mangrove-1.
        """
        index = _seed_index()
        response = index.search("mangrove water canopy")
        ids = [h.asset_id for h in response.hits]
        assert set(ids[:3]) == {"mangrove-1", "mangrove-2", "mangrove-3"}, ids
        # The best unrelated match must be far below the best true match.
        assert response.hits[0].score > 5 * response.hits[3].score
        assert "solar-1" not in ids[:3]

    def test_related_group_outranks_unrelated(self):
        index = _seed_index()
        hits = index.search("forest pine dryland", k=7).hits
        assert {h.asset_id for h in hits[:2]} <= {"pine-1", "pine-2"}

    def test_domain_synonyms_collapse(self):
        """Rhizophora and mangrove are the same thing in this domain."""
        assert "mangrove" in tokenize("a stand of Rhizophora mangle")
        assert tokenize("trees") == tokenize("forest")

    def test_stopwords_are_removed(self):
        assert "the" not in tokenize("show me the pictures")
        assert "mangrove" in tokenize("show me the mangrove pictures")

    def test_unmatched_terms_are_reported(self):
        index = _seed_index()
        response = index.search("mangrove zeppelin")
        assert "zeppelin" in response.unmatched_terms
        assert response.hits, "matched terms should still return results"

    def test_project_scope_filter(self):
        index = _seed_index()
        response = index.search("canopy", project_id="ESP-200", k=10)
        assert {h.asset_id for h in response.hits} <= {"solar-1", "solar-2"}

    def test_tag_filter(self):
        index = _seed_index()
        response = index.search("canopy", tags=["water"], k=10)
        assert all("water" in h.tags for h in response.hits)

    def test_empty_query_returns_nothing(self):
        index = _seed_index()
        assert index.search("   ").hits == []

    def test_empty_index_returns_nothing(self):
        assert SemanticIndex().search("mangrove").hits == []

    def test_similar_to_finds_neighbours(self):
        index = _seed_index()
        similar = index.similar_to("mangrove-1", k=3)
        ids = [h.asset_id for h in similar]
        assert "mangrove-2" in ids and "mangrove-3" in ids
        assert "mangrove-1" not in ids

    def test_similar_to_unknown_asset(self):
        assert _seed_index().similar_to("nope") == []

    def test_response_reports_the_backend_honestly(self):
        """A tf-idf index must not be advertised as a neural embedding model."""
        index = _seed_index()
        response = index.search("mangrove")
        assert response.backend == "tfidf_lexical"
        assert "LEXICAL" in response.notes
        assert index.is_neural_embedding is False

    def test_response_is_json_serialisable(self):
        import json

        json.dumps(_seed_index().search("mangrove").to_dict())

    def test_remove_drops_the_document(self):
        index = _seed_index()
        before = len(index)
        index.remove("mangrove-1")
        assert len(index) == before - 1
        assert "mangrove-1" not in [h.asset_id for h in index.search("mangrove").hits]

    def test_idf_downweights_common_terms(self):
        """A term in every document must contribute less than a rare one."""
        index = _seed_index()
        rare = index.search("zeppelin")
        common = index.search("canopy")
        assert common.hits[0].score > 0
        assert rare.hits == []

    def test_from_settings_without_credentials_uses_local_backend(self):
        from core.config import Settings

        index = SemanticIndex.from_settings(Settings())
        assert index.backend_name == "tfidf_lexical"


# =========================================================================== #
# Query compilation
# =========================================================================== #


class TestQueryCompilation:
    def test_compiles_a_real_sentence(self):
        q = compile_query("show mangrove plots with canopy growth over 25%")
        assert 'metadata.sustainability_domain="mangrove_restoration"' in q.expression
        assert "metadata.canopy_delta_pct>=25.0" in q.expression

    def test_comparator_is_inside_the_match(self):
        """REGRESSION: 'under 60' once compiled to '>= 60'."""
        q = compile_query("quarantined photos with confidence under 60 percent")
        assert "metadata.jev_confidence_score<=60.0" in q.expression
        assert ">=" not in q.expression

    def test_negative_bound_keeps_its_sign(self):
        q = compile_query("assets with canopy growth less than -10 percent")
        assert "metadata.canopy_delta_pct<=-10.0" in q.expression

    def test_negative_bound_out_of_range_is_rejected(self):
        with pytest.raises(QueryCompilationError, match="outside the permitted range"):
            compile_query("mangrove with canopy over -500")

    def test_spaced_phase_is_recognised(self):
        """REGRESSION: 'month 18' missed the unspaced 'month18' synonym."""
        q = compile_query("month 18 progress assets")
        assert 'metadata.milestone_phase="progress_month_18"' in q.expression

    def test_year3_spaced_form(self):
        q = compile_query("certified year 3 plots")
        assert 'metadata.milestone_phase="certified_year_3"' in q.expression

    def test_project_id_is_pattern_validated(self):
        q = compile_query("assets for KEN-042")
        assert 'metadata.esg_project_id="KEN-042"' in q.expression

    def test_parcel_id_is_extracted(self):
        q = compile_query("show parcel PARCEL-KEN-042")
        assert "metadata.cadastral_polygon_id" in q.expression

    def test_multiple_constraints_are_anded(self):
        q = compile_query("verified mangrove assets for KEN-042 with canopy over 30 percent")
        assert q.expression.count(" AND ") == 3
        assert len(q.constraints) == 4

    def test_unparseable_query_is_rejected_not_emptied(self):
        with pytest.raises(QueryCompilationError, match="Could not find"):
            compile_query("show me the pretty pictures of trees")

    def test_empty_query_rejected(self):
        with pytest.raises(QueryCompilationError):
            compile_query("   ")

    @pytest.mark.parametrize("bad", [
        "canopy over 5000", "confidence over 900", "KEN042", "project = X; DROP",
    ])
    def test_malformed_input_is_rejected(self, bad):
        with pytest.raises(QueryCompilationError):
            compile_query(bad)

    def test_field_names_never_come_from_user_text(self):
        """No part of the query may reach the expression structure."""
        q = compile_query("mangrove with canopy over 25%")
        for constraint in q.constraints:
            assert constraint["field"] in {
                "sustainability_domain", "jev_triage_decision", "milestone_phase",
                "c2pa_provenance", "esg_project_id", "cadastral_polygon_id",
                "capture_timestamp", "canopy_delta_pct", "jev_confidence_score",
                "sift_inlier_ratio", "solar_azimuth_error",
            }
            assert f"metadata.{constraint['field']}" in q.expression

    def test_result_is_json_serialisable(self):
        import json

        json.dumps(compile_query("verified mangrove assets").to_dict())


# =========================================================================== #
# Narrative grounding
# =========================================================================== #


def _facts() -> ProjectFacts:
    return ProjectFacts(
        project_id="KEN-042",
        project_name="Kilifi Creek Mangrove Restoration",
        total_assets=148,
        verified_assets=131,
        review_assets=12,
        quarantined_assets=5,
        canopy_delta_pct=38.2,
        baseline_canopy_px=142100,
        progress_canopy_px=196420,
        mean_inlier_ratio=0.845,
        estimated_tco2e_per_ha=8.42,
        area_ha=14.5,
        sampling_error_pct=8.7,
        net_certified_tco2e=8.42,
        domain="mangrove_restoration",
        timeline_epochs=["2025-03", "2025-09", "2026-03", "2026-09"],
        coverage_gaps=[{"label": "2025-09", "expected_assets": 12, "observed_assets": 0}],
        top_tags=["canopy", "mangrove", "water"],
    )


class TestGrounding:
    def test_deterministic_summary_is_grounded(self):
        summary = build_grounded_summary(_facts())
        assert summary["grounded"] is True
        assert summary["llm_enhanced"] is False
        assert extract_numbers(summary["text"])

    def test_rounded_integer_is_not_a_valid_rendering(self):
        """REGRESSION: round(8.42) -> '8' let a fabricated '8.0' pass.

        Rounding a carbon volume to a whole number lets it be read as a count,
        which is exactly the quiet corruption this guard exists to stop.
        """
        facts = _facts()
        for bad in ["Registrations reached 8.0.", "Biomass rounded to 8 tCO2e/ha."]:
            with pytest.raises(GroundingError):
                assert_summary_is_grounded(bad, facts.numeric_values())

    @pytest.mark.parametrize("bad", [
        "Canopy grew 92%.", "7 new trees.", "Register 47 assets.",
    ])
    def test_fabricated_figures_are_rejected(self, bad):
        with pytest.raises(GroundingError):
            assert_summary_is_grounded(bad, _facts().numeric_values())

    @pytest.mark.parametrize("ok", [
        "ISO/IEC 14064 across 14.5 ha.",
        "ISSA 5000 assurance.",
        "ESRS E1 and E4 disclosures.",
        "EUDR Article 9 for 14.5 ha.",
        "Section 8.4 of VM0047.",
        "Verra VM0047 over 148 assets.",
        "C2PA-verified, 131 assets.",
        "8.42 tCO2e per hectare.",
        "Canopy +38.2%.",
    ])
    def test_labels_and_citations_are_not_figures(self, ok):
        assert_summary_is_grounded(ok, _facts().numeric_values())

    def test_summary_omits_rather_than_invents(self):
        """A fact that is None must not become a number."""
        facts = ProjectFacts(project_id="K", project_name="Bare", total_assets=4)
        text = build_grounded_summary(facts)["text"]
        assert "tCO2e" not in text
        assert "canopy surface area" not in text

    def test_summary_respects_the_sentence_cap(self):
        facts = _facts()
        summary = build_grounded_summary(facts, max_sentences=2)
        assert summary["sentence_count"] <= 2

    def test_summary_is_json_serialisable(self):
        import json

        json.dumps(build_grounded_summary(_facts()))


class TestLlmBoundary:
    """The designed line: narrative may be rewritten, numbers may not."""

    def test_grounded_llm_prose_is_accepted(self):
        summary = build_grounded_summary(_facts())
        out = enhance_with_llm(
            summary, _facts(),
            call_fn=lambda: "Canopy change of +38.2 percent was recorded across 148 assets.",
        )
        assert out["generator"] == "llm_prose_grounded"
        assert out["llm_enhanced"] is True

    def test_ungrounded_llm_prose_is_discarded(self):
        summary = build_grounded_summary(_facts())
        out = enhance_with_llm(
            summary, _facts(),
            call_fn=lambda: "Outstanding results: 92% growth and 400 new trees.",
        )
        assert out["generator"] == "deterministic_grounded"
        assert "rejected" in out["llm_note"]

    def test_failing_llm_falls_back(self):
        summary = build_grounded_summary(_facts())
        out = enhance_with_llm(
            summary, _facts(),
            call_fn=lambda: (_ for _ in ()).throw(RuntimeError("API down")),
        )
        assert out["generator"] == "deterministic_grounded"
        assert "API down" in out["llm_note"]

    def test_empty_llm_output_falls_back(self):
        summary = build_grounded_summary(_facts())
        out = enhance_with_llm(summary, _facts(), call_fn=lambda: "   ")
        assert out["generator"] == "deterministic_grounded"

    def test_absent_llm_leaves_summary_untouched(self):
        summary = build_grounded_summary(_facts())
        assert enhance_with_llm(summary, _facts())["generator"] == "deterministic_grounded"


# =========================================================================== #
# Timeline
# =========================================================================== #


def _asset(i, date_iso, phase="", decision="VERIFIED_PASS", delta=None):
    return AssetRecord(
        asset_id=f"a{i}",
        capture_date=dt.date.fromisoformat(date_iso),
        milestone_phase=phase,
        triage_decision=decision,
        canopy_delta_pct=delta,
    )


def _healthy_schedule():
    assets = [_asset(i, "2025-03-15", "baseline_month_0", delta=0.0) for i in range(3)]
    assets += [_asset(i, "2025-09-15", "progress_month_6", delta=12.0) for i in range(3, 6)]
    assets += [_asset(i, "2026-09-20", "progress_month_18", delta=38.2) for i in range(6, 9)]
    assets += [_asset(i, "2028-03-20", "certified_year_3", delta=52.0) for i in range(9, 12)]
    return assets


class TestDateHelpers:
    def test_add_months_clamps_the_day(self):
        assert add_months(dt.date(2025, 1, 31), 1) == dt.date(2025, 2, 28)

    def test_add_months_crosses_the_year(self):
        assert add_months(dt.date(2025, 11, 15), 3) == dt.date(2026, 2, 15)

    def test_add_months_handles_leap_day(self):
        assert add_months(dt.date(2024, 2, 29), 12) == dt.date(2025, 2, 28)

    def test_months_between_counts_whole_months(self):
        assert months_between(dt.date(2025, 3, 15), dt.date(2025, 9, 14)) == 5
        assert months_between(dt.date(2025, 3, 15), dt.date(2025, 9, 15)) == 6

    def test_months_between_is_negative_backwards(self):
        assert months_between(dt.date(2025, 9, 15), dt.date(2025, 3, 15)) == -6


class TestTimeline:
    def test_healthy_project_is_on_schedule(self):
        report = build_timeline("KEN-042", _healthy_schedule())
        assert report.status == TimelineStatus.ON_SCHEDULE
        assert report.gaps == []
        assert report.coverage_pct == 100.0
        assert all(e.status == EpochStatus.FULL for e in report.epochs)

    def test_missing_epoch_is_detected(self):
        assets = [a for a in _healthy_schedule() if a.milestone_phase != "certified_year_3"]
        report = build_timeline("KEN-042", assets)
        assert report.status == TimelineStatus.GAPS_DETECTED
        assert [g.label for g in report.gaps] == ["certified_year_3"]
        assert report.gaps[0].severity == "missing"
        assert report.coverage_pct == 75.0

    def test_asset_is_counted_in_exactly_one_epoch(self):
        """REGRESSION: pooling the date window with the declared phase counted
        12 assets as 24 and inflated coverage."""
        burst = [_asset(i, "2026-09-20", "progress_month_18", delta=38.0) for i in range(12)]
        report = build_timeline("KEN-042", burst)
        placed = sum(e.observed_assets for e in report.epochs)
        assert placed == report.total_assets == 12

    def test_count_trap_is_caught(self):
        """12 assets in one week at month 18 is not twelve months of evidence."""
        burst = [_asset(i, "2026-09-20", "progress_month_18", delta=38.0) for i in range(12)]
        report = build_timeline("KEN-042", burst)
        assert report.total_assets == 12
        assert len(report.gaps) == 3, "three epochs have no evidence at all"
        assert "Entirely absent" in report.notes

    def test_unplaceable_asset_is_reported_not_silently_dropped(self):
        stray = _asset(100, "2030-01-01", delta=1.0)
        report = build_timeline("KEN-042", _healthy_schedule() + [stray])
        assert report.total_assets == 13
        assert sum(e.observed_assets for e in report.epochs) == 12
        assert "could not be placed" in report.notes

    def test_empty_project_reports_no_evidence(self):
        report = build_timeline("EMPTY", [])
        assert report.status == TimelineStatus.NO_EVIDENCE
        assert report.epochs == []
        assert report.coverage_pct == 0.0

    def test_partial_epoch_is_distinguished_from_missing(self):
        assets = [_asset(i, "2025-03-15", "baseline_month_0", delta=0.0) for i in range(3)]
        assets += [_asset(3, "2025-09-15", "progress_month_6", delta=10.0)]
        report = build_timeline("KEN-042", assets)
        partial = [g for g in report.gaps if g.label == "progress_month_6"]
        assert partial and partial[0].severity == "partial"
        assert partial[0].shortfall == 2

    def test_quarantine_counts_are_aggregated(self):
        assets = _healthy_schedule()
        assets[0] = _asset(0, "2025-03-15", "baseline_month_0", decision="QUARANTINE_FRAUD", delta=0.0)
        report = build_timeline("KEN-042", assets)
        baseline = next(e for e in report.epochs if e.label == "baseline_month_0")
        assert baseline.quarantined_assets == 1
        assert baseline.verified_assets == 2

    def test_mean_canopy_delta_per_epoch(self):
        report = build_timeline("KEN-042", _healthy_schedule())
        m18 = next(e for e in report.epochs if e.label == "progress_month_18")
        assert m18.mean_canopy_delta_pct == pytest.approx(38.2)

    def test_custom_expected_count_is_honoured(self):
        report = build_timeline(
            "KEN-042", _healthy_schedule(), expected_assets_per_epoch=5
        )
        assert report.status == TimelineStatus.GAPS_DETECTED
        assert report.coverage_pct == pytest.approx(60.0)

    def test_dict_records_are_accepted(self):
        report = build_timeline(
            "KEN-042",
            [{"asset_id": "x", "capture_date": "2025-03-15", "milestone_phase": "baseline_month_0"}],
        )
        assert report.total_assets == 1

    def test_records_without_a_usable_date_are_dropped(self):
        report = build_timeline("KEN-042", [{"asset_id": "x", "capture_date": None}])
        assert report.status == TimelineStatus.NO_EVIDENCE

    def test_result_is_json_serialisable(self):
        import json

        json.dumps(build_timeline("KEN-042", _healthy_schedule()).to_dict())
