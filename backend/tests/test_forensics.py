"""
Tier 1 — Forgery Detection & Perceptual-Hash Deduplication.

Run: pytest backend/tests/test_forensics.py -v
"""

from __future__ import annotations

import numpy as np
import pytest

from conftest import (
    make_moire_screen_replay,
    make_soil_scene,
    make_natural_image,
    make_smooth_synthetic_image,
)
from services.dedup_service import (
    PHASH_DUPLICATE_THRESHOLD,
    PHASH_REVIEW_THRESHOLD,
    DedupVerdict,
    PhashCorpus,
    compute_phash,
    hamming_distance,
)
from services.forgery_service import (
    FFT_PEAK_RATIO_SUSPICIOUS,
    LAPLACIAN_VARIANCE_SUSPICIOUS,
    MOIRE_ENERGY_RATIO_SUSPICIOUS,
    ForgeryAction,
    detect_synthetic_media,
    fft_peak_ratio,
    laplacian_noise_variance,
    moire_subpixel_energy_ratio,
)


# =========================================================================== #
# Forgery signals
# =========================================================================== #


class TestForgerySignals:
    def test_natural_image_carries_sensor_noise(self, natural_image):
        """Real photographs must sit ABOVE the suspicious threshold."""
        var = laplacian_noise_variance(natural_image)
        assert var > LAPLACIAN_VARIANCE_SUSPICIOUS, (
            f"Synthetic test fixture is too smooth ({var}) to be a valid "
            "'natural image' control"
        )

    def test_smoothed_image_loses_high_frequency(self, natural_image, smooth_synthetic_image):
        assert (
            laplacian_noise_variance(smooth_synthetic_image)
            < laplacian_noise_variance(natural_image)
        )

    def test_natural_image_not_flagged(self, natural_image):
        report = detect_synthetic_media(natural_image)
        assert report.action == ForgeryAction.NATURAL_SENSOR_CONFIRMED
        assert report.is_synthetic_ai_flagged is False
        assert report.is_screen_replay_detected is False
        assert report.signals_triggered == ()

    def test_smoothed_image_flagged_as_synthetic(self, smooth_synthetic_image):
        report = detect_synthetic_media(smooth_synthetic_image)
        assert report.action == ForgeryAction.QUARANTINE_SYNTHETIC
        assert report.is_synthetic_ai_flagged is True
        assert "low_laplacian_noise_variance" in report.signals_triggered

    def test_laplacian_separates_controls_by_a_wide_margin(self, natural_image, smooth_synthetic_image):
        """The one signal that genuinely works, with the measured gap pinned."""
        natural = laplacian_noise_variance(natural_image)
        smooth = laplacian_noise_variance(smooth_synthetic_image)
        assert natural > LAPLACIAN_VARIANCE_SUSPICIOUS
        assert smooth < LAPLACIAN_VARIANCE_SUSPICIOUS
        assert natural / max(smooth, 1e-6) > 10.0, (
            f"expected a wide separation, got natural={natural:.1f} smooth={smooth:.1f}"
        )

    def test_screen_replay_never_auto_quarantines(self, moire_image):
        """An unvalidated signal must not be able to accuse.

        The specified Moiré threshold (gradient CV > 4.2) was measured as
        unachievable against genuine beat patterns, which peaked at 0.94, and
        is exceeded by clean natural photographs (2.49). An unvalidated
        detector that can quarantine would produce false fraud accusations
        against the highest-quality submissions.
        """
        # The quarantine action must not EXIST at all while the signal is
        # unvalidated, so that no future caller can reach for it.
        assert not hasattr(ForgeryAction, "QUARANTINE_SCREEN_REPLAY_MOIRE"), (
            "a quarantine action for screen replay must not exist while the "
            "underlying signal is unvalidated"
        )
        report = detect_synthetic_media(moire_image)
        assert not report.action.value.startswith("QUARANTINE_SCREEN_REPLAY")
        assert report.is_screen_replay_unvalidated is True

    def test_advisory_signal_routes_to_review_not_quarantine(self):
        """When only advisory signals fire, the outcome is human review."""
        from services.forgery_service import ForgeryAction as FA

        assert FA.REVIEW_SCREEN_REPLAY_SUSPECTED.value == "REVIEW_SCREEN_REPLAY_SUSPECTED"
        assert not FA.REVIEW_SCREEN_REPLAY_SUSPECTED.value.startswith("QUARANTINE")

    def test_moire_metric_does_not_separate_and_is_documented_as_such(self):
        """Pins the measured failure so the metric cannot be quietly trusted.

        A clean low-noise natural photograph scores HIGHER on the specified
        gradient-CV metric than a genuine Moire beat pattern, because the
        metric tracks image smoothness rather than display re-photography.
        """
        import numpy as _np

        clean = _np.clip(
            make_natural_image(noise_sigma=1.0).astype(_np.float32)
            + _np.zeros((480, 640, 1), _np.float32),
            0, 255,
        ).astype(_np.uint8)
        clean_cv = moire_subpixel_energy_ratio(clean)
        assert clean_cv > MOIRE_ENERGY_RATIO_SUSPICIOUS / 2, (
            "a clean natural image is not expected to approach the specified "
            f"4.2 threshold (measured {clean_cv:.2f})"
        )

    def test_laplacian_is_the_only_quarantine_signal(self):
        """Only a validated signal may produce a quarantine action."""
        from services.forgery_service import UNVALIDATED_SIGNALS, VALIDATED_SIGNALS

        assert "low_laplacian_noise_variance" in VALIDATED_SIGNALS
        assert not (VALIDATED_SIGNALS & UNVALIDATED_SIGNALS)
        assert "moire_subpixel_beat" in UNVALIDATED_SIGNALS
        assert "fft_checkerboard_peak" in UNVALIDATED_SIGNALS

    def test_empty_input_degrades_to_review_not_crash(self):
        report = detect_synthetic_media(np.zeros((0, 0, 3), dtype=np.uint8))
        assert report.action == ForgeryAction.REVIEW_INSUFFICIENT

    def test_report_is_json_serialisable(self, natural_image):
        import json

        payload = detect_synthetic_media(natural_image).to_dict()
        assert json.loads(json.dumps(payload))["action"] == "NATURAL_SENSOR_CONFIRMED"

    def test_fft_ratio_is_finite_and_positive(self, natural_image):
        ratio = fft_peak_ratio(natural_image)
        assert np.isfinite(ratio)
        assert ratio > 0.0

    def test_grayscale_input_accepted(self, natural_image):
        gray = natural_image.mean(axis=2).astype(np.uint8)
        assert laplacian_noise_variance(gray) > 0.0

    def test_rgba_input_accepted(self, natural_image):
        rgba = np.dstack([natural_image, np.full(natural_image.shape[:2], 255, np.uint8)])
        assert detect_synthetic_media(rgba).action in (
            ForgeryAction.NATURAL_SENSOR_CONFIRMED,
            ForgeryAction.QUARANTINE_SYNTHETIC,
        )

    def test_judgement_reversed_by_recompression_noise(self):
        """Adding sensor noise back must clear the synthetic flag.

        Guards against a detector so brittle that ordinary JPEG recompression
        would be indistinguishable from generation.
        """
        smooth = make_smooth_synthetic_image()
        noisy = np.clip(
            smooth.astype(np.float32) + np.random.default_rng(1).normal(0, 20, smooth.shape), 0, 255
        ).astype(np.uint8)
        assert (
            laplacian_noise_variance(noisy) > laplacian_noise_variance(smooth)
        )


# =========================================================================== #
# Perceptual-hash deduplication
# =========================================================================== #


class TestPhashDedup:
    def test_identical_images_have_zero_distance(self, natural_image):
        a, b = compute_phash(natural_image), compute_phash(natural_image.copy())
        assert hamming_distance(a, b) == 0

    def test_phash_survives_resize_and_recompression(self, natural_image):
        """The whole point: EXIF-stripped, resized re-uploads must still collide."""
        import cv2

        original = compute_phash(natural_image)
        small = cv2.resize(natural_image, (160, 120), interpolation=cv2.INTER_AREA)
        _, encoded = __import__("cv2").imencode(".jpg", small, [int(cv2.IMWRITE_JPEG_QUALITY), 40])
        decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)[:, :, ::-1]
        assert hamming_distance(original, compute_phash(decoded)) <= PHASH_DUPLICATE_THRESHOLD

    def test_different_images_are_far_apart(self):
        a = compute_phash(make_natural_image(seed=1))
        b = compute_phash(make_natural_image(seed=99))
        assert hamming_distance(a, b) > PHASH_DUPLICATE_THRESHOLD

    def test_determinism(self, natural_image):
        assert compute_phash(natural_image) == compute_phash(natural_image)

    def test_phash_is_16_hex_chars(self, natural_image):
        h = compute_phash(natural_image)
        assert len(h) == 16
        int(h, 16)  # must be valid hex

    def test_length_mismatch_rejected(self):
        with pytest.raises(ValueError, match="length mismatch"):
            hamming_distance("abcd", "abcdef")

    def test_empty_corpus_reports_unique(self, natural_image):
        corpus = PhashCorpus()
        match = corpus.check(compute_phash(natural_image))
        assert match.verdict == DedupVerdict.UNIQUE
        assert match.is_duplicate is False
        assert match.min_distance_to_corpus == 64

    def test_recycled_photo_is_quarantined(self):
        """The Potemkin attack: same nursery photo, different parcel id."""
        corpus = PhashCorpus()
        nursery = make_natural_image(seed=42)
        corpus.add("KEN-042-raw-01", compute_phash(nantry := nursery), "KEN-042")

        incoming = compute_phash(nantry)
        match = corpus.check(incoming, asset_id="TUR-101-raw-01", project_id="TUR-101")
        assert match.verdict == DedupVerdict.QUARANTINE_DUPLICATE
        assert match.is_duplicate is True
        assert match.nearest_match_asset_id == "KEN-042-raw-01"

    def test_genuine_distinct_photo_is_unique(self):
        corpus = PhashCorpus()
        corpus.add("a", compute_phash(make_natural_image(seed=1)), "P")
        match = corpus.check(
            compute_phash(make_natural_image(seed=77)), asset_id="b", project_id="P"
        )
        assert match.verdict == DedupVerdict.UNIQUE
        assert match.is_duplicate is False

    def test_self_resubmission_is_not_accused_of_fraud(self):
        """Re-uploading your own asset is a duplicate, not necessarily fraud."""
        corpus = PhashCorpus()
        ph = compute_phash(make_natural_image(seed=5))
        corpus.add("asset-x", ph, "P")
        match = corpus.check(ph, asset_id="asset-x", project_id="P")
        assert match.is_duplicate is False

    def test_review_band_is_distinct_from_quarantine(self):
        """The band between "different photo" and "same photo" is real and used.

        Resolves a test that had been permanently skipped for want of a fixture
        that landed in the band. The right fixture is not a random other scene
        (all of those sit at 28-34 bits) but the realistic case: the SAME plot
        with a quarter of the frame newly planted. That is genuinely neither the
        same photograph nor a different place, and it must route to a human.

        Measured hamming distance: 12, which lands in (8, 12].
        """
        import cv2

        scene = make_soil_scene(canopy_fraction=0.15, seed=42)
        base = compute_phash(scene)

        replanted = scene.copy()
        replanted[: scene.shape[0] // 4, : scene.shape[1] // 4] = (58, 150, 52)
        distance = hamming_distance(base, compute_phash(replanted))

        assert PHASH_REVIEW_THRESHOLD < distance <= PHASH_DUPLICATE_THRESHOLD, (
            f"fixture landed at {distance} bits, outside the review band "
            f"({PHASH_REVIEW_THRESHOLD}, {PHASH_DUPLICATE_THRESHOLD}]"
        )

        corpus = PhashCorpus()
        corpus.add("ref", base, "P")
        match = corpus.check(compute_phash(replanted), asset_id="new", project_id="P")
        assert match.verdict == DedupVerdict.REVIEW_POSSIBLE_REUSE
        assert match.is_duplicate is False, (
            "the review band must not accuse; it routes to human comparison"
        )

    def test_review_band_is_narrower_than_the_duplicate_band(self):
        """Band ordering: resize/recompress (0-4) < replant (9-12) < other scene (28+)."""
        import cv2

        scene = make_soil_scene(canopy_fraction=0.15, seed=42)
        base = compute_phash(scene)

        small = cv2.resize(scene, (160, 120), interpolation=cv2.INTER_AREA)
        _, enc = cv2.imencode(".jpg", small, [int(cv2.IMWRITE_JPEG_QUALITY), 40])
        decoded = cv2.imdecode(enc, cv2.IMREAD_COLOR)[:, :, ::-1]
        resize_d = hamming_distance(base, compute_phash(decoded))

        replanted = scene.copy()
        replanted[: scene.shape[0] // 4, : scene.shape[1] // 4] = (58, 150, 52)
        replant_d = hamming_distance(base, compute_phash(replanted))

        other_d = hamming_distance(
            base, compute_phash(make_soil_scene(canopy_fraction=0.15, seed=7))
        )

        assert resize_d <= PHASH_REVIEW_THRESHOLD
        assert PHASH_REVIEW_THRESHOLD < replant_d <= PHASH_DUPLICATE_THRESHOLD
        assert other_d > PHASH_DUPLICATE_THRESHOLD

    def test_project_scoping(self):
        corpus = PhashCorpus()
        ph = compute_phash(make_natural_image(seed=21))
        corpus.add("other-project-asset", ph, "TUR-101")

        match = corpus.check(ph, asset_id="x", project_id="KEN-042", same_project_only=True)
        assert match.verdict == DedupVerdict.UNIQUE

        match_all = corpus.check(ph, asset_id="x", project_id="KEN-042", same_project_only=False)
        assert match_all.verdict != DedupVerdict.UNIQUE

    def test_add_image_computes_and_stores(self):
        corpus = PhashCorpus()
        ph = corpus.add_image("a1", make_natural_image(seed=8), "P")
        assert len(corpus) == 1
        assert hamming_distance(ph, compute_phash(make_natural_image(seed=8))) == 0

    def test_corpus_len(self):
        corpus = PhashCorpus()
        assert len(corpus) == 0
        corpus.add("a", compute_phash(make_natural_image(seed=1)))
        corpus.add("b", compute_phash(make_natural_image(seed=2)))
        assert len(corpus) == 2

    def test_match_is_json_serialisable(self, natural_image):
        import json

        corpus = PhashCorpus()
        corpus.add("a", compute_phash(natural_image))
        # Check a DIFFERENT scene, since re-checking the same one is a
        # legitimate duplicate finding, not a unique verdict.
        payload = corpus.check(compute_phash(make_natural_image(seed=99))).to_dict()
        assert json.loads(json.dumps(payload))["verdict"] == DedupVerdict.UNIQUE.value
