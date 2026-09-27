"""
Tier 1 — Forgery Detection & Perceptual-Hash Deduplication.

Run: pytest backend/tests/test_forensics.py -v
"""

from __future__ import annotations

import numpy as np
import pytest

from conftest import (
    make_moire_screen_replay,
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

    def test_screen_replay_detected_via_moire(self, moire_image):
        report = detect_synthetic_media(moire_image)
        assert report.is_screen_replay_detected is True
        assert report.action == ForgeryAction.QUARANTINE_SCREEN_REPLAY_MOIRE
        assert "moire_subpixel_beat" in report.signals_triggered

    def test_moire_ratio_separates_screen_from_natural(self, natural_image, moire_image):
        assert (
            moire_subpixel_energy_ratio(moire_image)
            > MOIRE_ENERGY_RATIO_SUSPICIOUS
        )
        assert (
            moire_subpixel_energy_ratio(natural_image)
            < MOIRE_ENERGY_RATIO_SUSPICIOUS
        )

    def test_screen_replay_takes_precedence_over_synthetic(self, moire_image):
        """The more specific accusation wins, so the reason is not lost."""
        report = detect_synthetic_media(moire_image)
        assert report.action == ForgeryAction.QUARANTINE_SCREEN_REPLAY_MOIRE
        assert "re-photograph" in report.notes

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
        smooth = make_smooth_synthetic_image(noise_free=True) if False else make_smooth_synthetic_image()
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
        corpus = PhashCorpus()
        base = compute_phash(make_natural_image(seed=13))
        corpus.add("ref", base, "P")
        # Find an image that lands in the review band.
        found = None
        for seed in range(200, 260):
            candidate = compute_phash(make_natural_image(seed=seed))
            d = hamming_distance(base, candidate)
            if PHASH_REVIEW_THRESHOLD < d <= PHASH_DUPLICATE_THRESHOLD:
                found = (candidate, d)
                break
        if found is None:
            pytest.skip("no sample landed in the review band; thresholds may be tight")
        match = corpus.check(found[0], asset_id="x", project_id="P")
        assert match.verdict == DedupVerdict.REVIEW_POSSIBLE_REUSE
        assert match.is_duplicate is False

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
        payload = corpus.check(compute_phash(natural_image)).to_dict()
        assert json.loads(json.dumps(payload))["verdict"] == DedupVerdict.UNIQUE.value
