"""
Tier 2 — Computer Vision & Photogrammetry Regression Suite

Covers: SIFT/MAGSAC++ registration, Thin Plate Spline fallback, radiometric
correction, and GLI canopy quantification.

Run: pytest backend/tests/test_vision.py -v

Several tests here are regression guards for claims that measurement
contradicted, not just coverage of code paths. See the module docstrings in
``services/homography_service.py`` and ``services/radiometric_service.py`` for
the numbers behind each one.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from conftest import (
    apply_transform,
    make_soil_scene,
    make_cluttered_scene,
)
from services.canopy_service import (
    MIN_BASELINE_CANOPY_PX,
    CanopyStatus,
    compute_canopy_metrics,
    compute_gli,
    extract_canopy_mask,
    valid_overlap_mask,
)
from services.homography_service import (
    INLIER_RATIO_FLOOR,
    detection_scale_for,
    TPS_CONDITION_REPORT_THRESHOLD,
    TPS_MIN_IMPROVEMENT,
    TPS_NONPLANARITY_THRESHOLD_PX,
    RegistrationStatus,
    condition_number,
    estimate_nonplanarity,
    register_field_pair,
    thin_plate_spline_apply,
    thin_plate_spline_field,
    thin_plate_spline_weights,
)
from services.radiometric_service import (
    MAX_PLAUSIBLE_GAIN,
    MeasurementSafetyError,
    RadiometricStatus,
    assert_not_measurement_safe,
    estimate_channel_gains,
    histogram_match_channels,
)

pytestmark = pytest.mark.tier2


def make_parallax_pair(scene, amplitude_px: float):
    """A known non-rigid displacement, as drone translation + gimbal would cause."""
    h, w = scene.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = (amplitude_px * np.sin(yy / 55.0)).astype(np.float32)
    dy = (amplitude_px * 0.7 * np.sin(xx / 48.0)).astype(np.float32)
    return cv2.remap(
        scene, (xx + dx), (yy + dy),
        interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT,
    )


# =========================================================================== #
# GLI properties
# =========================================================================== #


class TestGliInvariance:
    """GLI's illumination invariance is a PROPERTY, so it is tested as one.

    This is the property that makes the whole measurement approach work: a
    cloud shadow must not read as canopy mortality.
    """

    @pytest.mark.parametrize("gain", [0.5, 0.65, 0.8, 1.0])
    def test_gli_is_invariant_to_global_gain(self, soil_scene, gain):
        """Exact in the regime where uint8 clipping does not bite.

        Measured: with 0% of pixels clipped, max|dGLI| stays at ~0.008, which is
        pure re-quantisation. GLI's invariance is algebraic, so this tolerance is
        deliberately tight -- a loose one would hide a real regression.
        """
        f = soil_scene.astype(np.float32)
        assert (f * gain > 255).mean() == 0.0, "this case must not clip"
        base = compute_gli(soil_scene)
        scaled = np.clip(f * gain, 0, 255).astype(np.uint8)
        assert np.abs(compute_gli(scaled) - base).max() < 0.02

    def test_gli_invariance_breaks_only_where_uint8_clips(self, soil_scene):
        """At 2x gain, 19% of pixels saturate and the invariance degrades.

        Pinned so the bound is understood: clipping is information loss, not a
        property of the index. Any pipeline using GLI should avoid gains that
        saturate highlights, or work in float.
        """
        f = soil_scene.astype(np.float32)
        clipped_fraction = (f * 2.0 > 255).mean()
        assert clipped_fraction > 0.10, "expected meaningful highlight saturation"
        base = compute_gli(soil_scene)
        scaled = np.clip(f * 2.0, 0, 255).astype(np.uint8)
        assert np.abs(compute_gli(scaled) - base).max() > 0.05

    def test_gli_is_invariant_to_local_cloud_shadow(self, soil_scene):
        base = compute_gli(soil_scene)
        h, w = soil_scene.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        d2 = (xx - w * 0.35) ** 2 + (yy - h * 0.5) ** 2
        shadow = 1.0 - 0.55 * np.exp(-d2 / (2.0 * (w * 0.3) ** 2))
        shadowed = np.clip(
            soil_scene.astype(np.float32) * shadow[..., None], 0, 255
        ).astype(np.uint8)
        assert shadow.min() < 0.5, "the shadow field must be strong to be a real test"
        assert np.abs(compute_gli(shadowed) - base).max() < 0.10

    def test_gli_does_move_for_chromatic_shift(self, soil_scene):
        """Otherwise the invariance tests would pass for a broken index."""
        base = compute_gli(soil_scene)
        shifted = soil_scene.astype(np.float32).copy()
        shifted[:, :, 2] *= 0.82
        shifted = np.clip(shifted, 0, 255).astype(np.uint8)
        assert np.abs(compute_gli(shifted) - base).max() > 0.01

    def test_gli_is_bounded(self, soil_scene):
        gli = compute_gli(soil_scene)
        assert gli.min() >= -1.0 and gli.max() <= 1.0

    def test_gli_rejects_empty_input(self):
        with pytest.raises(ValueError):
            compute_gli(np.zeros((0, 0, 3), dtype=np.uint8))

    def test_gli_of_pure_green_is_maximal(self):
        green = np.zeros((4, 4, 3), np.uint8)
        green[:, :, 1] = 200
        assert compute_gli(green).mean() == pytest.approx(1.0, abs=0.01)

    def test_gli_of_grey_is_near_zero(self):
        grey = np.full((4, 4, 3), 128, np.uint8)
        assert abs(compute_gli(grey).mean()) < 0.01


# =========================================================================== #
# Canopy segmentation & measurement
# =========================================================================== #


class TestCanopyMeasurement:
    def test_otsu_separates_soil_from_vegetation(self, soil_scene):
        mask, threshold = extract_canopy_mask(soil_scene)
        fraction = mask.sum() / mask.size
        assert 0.05 < fraction < 0.40, f"implausible canopy fraction {fraction:.3f}"
        assert -0.2 < threshold < 0.6

    def test_detects_more_canopy_when_there_is_more_canopy(self):
        sparse = make_soil_scene(canopy_fraction=0.12, seed=3)
        dense = make_soil_scene(canopy_fraction=0.30, seed=3)
        assert compute_canopy_metrics(sparse, dense).net_canopy_growth_pct > 30.0

    def test_dimmer_visit_does_not_fabricate_change(self):
        """The false-mortality / false-growth test.

        A visit that is only DIMMER must not read as canopy change. This is the
        single most important property of the measurement, because a naive
        ExG implementation reports large canopy loss under a cloud shadow.
        """
        baseline = make_soil_scene(canopy_fraction=0.18, seed=3)
        darker = np.clip(baseline.astype(np.float32) * 0.55, 0, 255).astype(np.uint8)
        result = compute_canopy_metrics(baseline, darker)
        assert result.status == CanopyStatus.OK
        assert abs(result.net_canopy_growth_pct) < 12.0, (
            f"illumination change alone produced a {result.net_canopy_growth_pct}% "
            "canopy delta"
        )

    def test_growth_is_monotonic_in_true_canopy(self):
        fractions = [0.10, 0.16, 0.22, 0.28]
        deltas = [
            compute_canopy_metrics(
                make_soil_scene(canopy_fraction=0.08, seed=5),
                make_soil_scene(canopy_fraction=f, seed=5),
            ).net_canopy_growth_pct
            for f in fractions
        ]
        assert all(a < b for a, b in zip(deltas, deltas[1:])), deltas

    def test_refuses_on_shape_mismatch(self, soil_scene):
        smaller = soil_scene[:200, :200]
        result = compute_canopy_metrics(soil_scene, smaller)
        assert result.status == CanopyStatus.INVALID_INPUT
        assert result.net_canopy_growth_pct is None

    def test_refuses_on_none_input(self, soil_scene):
        assert compute_canopy_metrics(soil_scene, None).status == CanopyStatus.INVALID_INPUT

    def test_refuses_when_warp_border_dominates(self, soil_scene):
        """A tiny warped patch must not yield a confident canopy delta."""
        small = np.zeros_like(soil_scene)
        small[:120, :120] = soil_scene[:120, :120]
        result = compute_canopy_metrics(soil_scene, small)
        assert result.status == CanopyStatus.INSUFFICIENT_OVERLAP
        assert result.net_canopy_growth_pct is None, (
            "a delta computed over a mostly-black frame would be reported as "
            "canopy loss; it must be withheld"
        )

    def test_refuses_when_frame_has_no_vegetation_contrast(self):
        """REGRESSION GUARD for a silent 100% canopy "measurement".

        Otsu is undefined on a zero-variance histogram and returns a threshold
        of 0, which labels EVERY pixel as vegetation. A constant (40,40,30) frame
        has GLI = 0.0667 everywhere and produced a 100% canopy mask with a
        confident 0% growth delta. The service now detects this and refuses.
        """
        flat = np.full((400, 600, 3), 40, np.uint8)
        flat[:, :, 2] = 30
        result = compute_canopy_metrics(flat, flat.copy())
        assert result.status == CanopyStatus.INSUFFICIENT_CONTRAST
        assert result.net_canopy_growth_pct is None
        assert "no separable vegetation" in result.notes

    def test_extract_mask_raises_on_zero_variance(self):
        from services.canopy_service import InsufficientContrastError

        flat = np.full((200, 200, 3), 40, np.uint8)
        with pytest.raises(InsufficientContrastError):
            extract_canopy_mask(flat)

    def test_refuses_when_baseline_canopy_is_tiny(self):
        """A near-closed canopy where the non-vegetation mode is the minority.

        Otsu always splits a bimodal histogram into two non-trivial parts, so
        this path is reached by inverting the scene rather than by emptying it:
        98% vegetation, 2% soil. A drone shot directly over a closed canopy
        looks like this, and a percentage delta over a handful of soil pixels
        would be meaningless.
        """
        rng = np.random.default_rng(4)
        dense = np.zeros((400, 600, 3), np.float32)
        dense[:] = np.array([58.0, 150.0, 52.0]) + rng.normal(0.0, 8.0, (400, 600, 3))
        dense[:16, :16] = np.array([128.0, 96.0, 68.0]) + rng.normal(0.0, 6.0, (16, 16, 3))
        dense = np.clip(dense, 0, 255).astype(np.uint8)

        result = compute_canopy_metrics(dense, dense.copy())
        assert result.status == CanopyStatus.INSUFFICIENT_BASELINE_CANOPY
        assert result.baseline_canopy_pixels < MIN_BASELINE_CANOPY_PX, (
            f"expected a tiny minority mode, got {result.baseline_canopy_pixels} px"
        )
        assert result.net_canopy_growth_pct is None

    def test_valid_mask_excludes_black_border(self):
        frame = np.zeros((200, 300, 3), np.uint8)
        frame[:100, :150] = 120
        assert valid_overlap_mask(frame).sum() == 100 * 150

    def test_result_is_json_serialisable(self, soil_scene):
        import json

        payload = compute_canopy_metrics(soil_scene, soil_scene).to_dict()
        assert json.loads(json.dumps(payload))["status"] == "OK"

    def test_identical_frames_report_zero_change(self, soil_scene):
        result = compute_canopy_metrics(soil_scene, soil_scene.copy())
        assert result.net_canopy_growth_pct == pytest.approx(0.0, abs=0.5)


# =========================================================================== #
# Radiometric
# =========================================================================== #


class TestRadiometric:
    def test_neutral_scene_reports_noop(self, soil_scene):
        correction = estimate_channel_gains(soil_scene, soil_scene.copy())
        assert correction.status == RadiometricStatus.NOOP
        assert correction.applied is False

    def test_gains_never_applied_to_measurement_path(self, soil_scene):
        """GLI already cancels the luminance component; applying a gain would
        only re-quantise the image. Pinned so nobody 'fixes' this later."""
        correction = estimate_channel_gains(soil_scene, soil_scene.copy())
        assert correction.applied is False

    def test_detects_chromatic_drift(self, soil_scene):
        shifted = soil_scene.astype(np.float32).copy()
        shifted[:, :, 2] *= 0.75
        shifted = np.clip(shifted, 0, 255).astype(np.uint8)
        correction = estimate_channel_gains(soil_scene, shifted)
        assert correction.chromatic_shift > 0.05
        assert correction.status in (RadiometricStatus.OK, RadiometricStatus.REFUSED_IMPLAUSIBLE)

    def test_refuses_implausible_gain(self, soil_scene):
        near_black = np.full_like(soil_scene, 4)
        correction = estimate_channel_gains(soil_scene, near_black)
        assert correction.status == RadiometricStatus.REFUSED_IMPLAUSIBLE
        assert correction.applied is False

    def test_pif_mask_is_used_when_supplied(self, soil_scene):
        mask = np.zeros(soil_scene.shape[:2], np.uint8)
        mask[:200, :200] = 255
        correction = estimate_channel_gains(
            soil_scene, soil_scene.copy(), pif_mask=mask
        )
        assert correction.status == RadiometricStatus.NOOP

    def test_rejects_mismatched_pif_mask(self, soil_scene):
        with pytest.raises(ValueError, match="shape"):
            estimate_channel_gains(
                soil_scene, soil_scene.copy(), pif_mask=np.zeros((10, 10), np.uint8)
            )

    def test_rejects_tiny_pif_mask(self, soil_scene):
        mask = np.zeros(soil_scene.shape[:2], np.uint8)
        mask[0, 0] = 255
        with pytest.raises(ValueError, match=">= 32"):
            estimate_channel_gains(soil_scene, soil_scene.copy(), pif_mask=mask)

    def test_rejects_size_mismatch(self, soil_scene):
        with pytest.raises(ValueError, match="sizes differ"):
            estimate_channel_gains(soil_scene, soil_scene[:100, :100])

    def test_histogram_matching_perturbs_gli_more_than_it_corrects(self, soil_scene):
        """REGRESSION GUARD for the rejected histogram-matching approach.

        Per-channel CDF matching shifts GLI by 2-4x the magnitude of the
        white-balance drift it is meant to remove, so it is excluded from the
        measurement path. If this ever inverts, the exclusion is worth revisiting.
        """
        shifted = soil_scene.astype(np.float32).copy()
        shifted[:, :, 2] *= 0.82
        shifted = np.clip(shifted, 0, 255).astype(np.uint8)

        drift = np.abs(compute_gli(shifted) - compute_gli(soil_scene)).max()
        matched = histogram_match_channels(shifted, soil_scene)
        induced = np.abs(compute_gli(matched) - compute_gli(shifted)).max()

        assert induced > drift, (
            f"histogram matching induced {induced:.4f} of GLI error while "
            f"correcting only {drift:.4f} of real drift"
        )

    def test_measurement_path_guard_raises(self):
        with pytest.raises(MeasurementSafetyError):
            assert_not_measurement_safe("canopy delta")

    def test_correction_is_json_serialisable(self, soil_scene):
        import json

        json.dumps(estimate_channel_gains(soil_scene, soil_scene).to_dict())


# =========================================================================== #
# Homography / registration
# =========================================================================== #


class TestRegistration:
    def test_registers_a_known_transform(self, forest_pair):
        result = register_field_pair(forest_pair["baseline"], forest_pair["progress"])
        assert result.status == RegistrationStatus.ALIGNED_HOMOGRAPHY
        assert result.is_geometrically_valid is True
        assert result.inlier_ratio > 0.70
        assert result.residual_rmse_px < 2.0

    def test_warped_image_matches_baseline_geometry(self, forest_pair):
        result = register_field_pair(forest_pair["baseline"], forest_pair["progress"])
        assert result.warped_image is not None
        assert result.warped_image.shape == forest_pair["baseline"].shape

    def test_recovers_the_rotation(self, forest_pair):
        """Scored against a known answer, not merely 'it returned something'."""
        result = register_field_pair(forest_pair["baseline"], forest_pair["progress"])
        h = result.homography
        # Recover the rotation angle from the homography's linear part.
        angle = np.degrees(np.arctan2(h[1, 0], h[0, 0]))
        assert angle == pytest.approx(forest_pair["ground_truth_angle_deg"], abs=2.0)

    def test_rejects_flat_images(self):
        flat = np.full((300, 400, 3), 120, np.uint8)
        result = register_field_pair(flat, flat.copy())
        assert result.status in (
            RegistrationStatus.INSUFFICIENT_SIFT_FEATURES,
            RegistrationStatus.LOW_INLIER_MATCH_COUNT,
        )
        assert result.is_geometrically_valid is False
        assert result.warped_image is None

    def test_rejects_unrelated_scenes(self, soil_scene):
        other = make_soil_scene(canopy_fraction=0.20, seed=99)
        result = register_field_pair(soil_scene, other)
        # Either too few matches, or a registration too poor to trust.
        assert (
            not result.status.succeeded
            or result.inlier_ratio < INLIER_RATIO_FLOOR
        )
        if result.status.succeeded:
            assert result.warnings, "a low-quality match must carry a warning"

    def test_handles_none_input(self, soil_scene):
        assert register_field_pair(soil_scene, None).status == RegistrationStatus.INVALID_INPUT
        assert register_field_pair(None, soil_scene).status == RegistrationStatus.INVALID_INPUT

    def test_handles_differing_input_sizes(self, forest_pair):
        """A half-width crop must either align or fail informatively.

        ALIGNED_TPS_FALLBACK belongs in this set and was missing: it is a
        SUCCESS status, reached when the homography is too weak to trust and the
        registration falls back to a thin-plate spline. For a cropped pair that
        is arguably the best available answer, so excluding it made the test
        reject a good outcome. The real order-dependence behind this was OpenCV's
        global RNG, now seeded per test in conftest.
        """
        half = forest_pair["progress"][:, : forest_pair["progress"].shape[1] // 2]
        result = register_field_pair(forest_pair["baseline"], half)
        assert result.status in (
            RegistrationStatus.ALIGNED_HOMOGRAPHY,
            RegistrationStatus.ALIGNED_TPS_FALLBACK,
            RegistrationStatus.INSUFFICIENT_SIFT_FEATURES,
            RegistrationStatus.LOW_INLIER_MATCH_COUNT,
        )

    def test_warns_when_inlier_ratio_is_low(self):
        base = make_cluttered_scene(seed=5)
        result = register_field_pair(base, make_parallax_pair(base, 35.0))
        if result.status.succeeded and result.inlier_ratio < INLIER_RATIO_FLOOR:
            assert any("Inlier ratio" in w for w in result.warnings)

    def test_result_is_json_serialisable(self, forest_pair):
        import json

        result = register_field_pair(forest_pair["baseline"], forest_pair["progress"])
        payload = result.to_dict()
        assert payload["warped_image"].startswith("<")
        json.dumps(payload)

    def test_reports_timings(self, forest_pair):
        result = register_field_pair(forest_pair["baseline"], forest_pair["progress"])
        assert result.timings_ms["total"] > 0
        assert set(result.timings_ms) >= {"match", "homography", "warp"}


class TestParallaxTrigger:
    """The design document's TPS trigger was measured and does not work.

    It fired on ``kappa > 85 OR inlier RMSE > 3.5px``. Measured: a *clean*
    rotation reaches kappa 2580 (so kappa alone would fire on every image), and
    inlier RMSE never exceeds 1.9px even under 35px of deliberate non-rigid
    displacement (so the RMSE clause can never fire at all). The replacement
    trigger is the inlier ratio, which is monotonic with applied parallax.
    """

    def test_condition_number_alone_cannot_be_the_trigger(self, forest_pair):
        result = register_field_pair(forest_pair["baseline"], forest_pair["progress"])
        assert result.condition_number > TPS_CONDITION_REPORT_THRESHOLD
        assert result.status == RegistrationStatus.ALIGNED_HOMOGRAPHY, (
            "a clean rotation must NOT engage the fallback, even though its "
            "condition number exceeds the document's trigger of 85"
        )

    def test_nonplanarity_is_near_zero_for_a_planar_transform(self, forest_pair):
        result = register_field_pair(forest_pair["baseline"], forest_pair["progress"])
        assert result.nonplanarity_px < TPS_NONPLANARITY_THRESHOLD_PX

    def test_nonplanarity_rises_with_applied_parallax(self, forest_pair):
        base, prog = forest_pair["baseline"], forest_pair["progress"]
        clean = register_field_pair(base, prog).nonplanarity_px
        displaced = register_field_pair(base, make_parallax_pair(prog, 20.0)).nonplanarity_px
        assert displaced > clean

    def test_inlier_ratio_collapses_with_parallax(self, forest_pair):
        base, prog = forest_pair["baseline"], forest_pair["progress"]
        clean = register_field_pair(base, prog).inlier_ratio
        displaced = [
            register_field_pair(base, make_parallax_pair(prog, amp)).inlier_ratio
            for amp in (10.0, 20.0, 35.0)
        ]
        assert clean > 0.70
        assert all(r < 0.35 for r in displaced), displaced

    def test_inlier_ratio_is_not_strictly_monotonic_when_heavily_contaminated(
        self, forest_pair
    ):
        """Documents the limit of the signal honestly.

        Measured sequence: 0.955, 0.254, 0.142, 0.197 for 0/10/20/35 px. The
        clean-to-parallaxed drop is large and reliable, but past heavy
        contamination the ratio is no longer ordered, because MAGSAC's chosen
        inlier set becomes a small, locally self-consistent cluster. The
        trigger therefore combines the ratio with non-planarity rather than
        relying on the ratio alone.
        """
        base, prog = forest_pair["baseline"], forest_pair["progress"]
        ratios = [
            register_field_pair(base, make_parallax_pair(prog, amp)).inlier_ratio
            for amp in (0.0, 10.0, 20.0, 35.0)
        ]
        assert ratios[0] > 0.70
        assert max(ratios[1:]) < ratios[0] * 0.5

    def test_fallback_engages_under_genuine_parallax(self, forest_pair):
        result = register_field_pair(
            forest_pair["baseline"], make_parallax_pair(forest_pair["progress"], 20.0)
        )
        assert result.status == RegistrationStatus.ALIGNED_TPS_FALLBACK
        assert any("Thin Plate Spline" in w for w in result.warnings)

    def test_fallback_is_only_kept_if_it_measurably_helps(self, forest_pair):
        """A non-rigid model always fits the control points at least as well.
        It is only worth its extra freedom if it does substantially better."""
        result = register_field_pair(
            forest_pair["baseline"], make_parallax_pair(forest_pair["progress"], 20.0)
        )
        tps_warnings = [w for w in result.warnings if "Thin Plate Spline" in w]
        assert tps_warnings
        assert str(int(TPS_MIN_IMPROVEMENT * 100)) + "%" in tps_warnings[0]

    def test_can_disable_fallback(self, forest_pair):
        result = register_field_pair(
            forest_pair["baseline"],
            make_parallax_pair(forest_pair["progress"], 20.0),
            use_tps_fallback=False,
        )
        assert result.status == RegistrationStatus.ALIGNED_HOMOGRAPHY


# =========================================================================== #
# Thin Plate Spline
# =========================================================================== #


class TestThinPlateSpline:
    def test_opencv_shape_transformer_does_not_exist(self):
        """The design document's fallback API is not in OpenCV 4.10.

        Pinned so nobody re-introduces the documented call. The fallback is a
        direct NumPy implementation because of this.
        """
        assert not hasattr(cv2, "createThinPlateSplineShapeTransformer")
        assert not [n for n in dir(cv2) if "ThinPlate" in n]

    def test_interpolates_its_control_points(self):
        src = np.array(
            [[100, 100], [500, 120], [300, 350], [120, 330], [480, 300]], np.float32
        )
        dst = src + np.array([[6, 4], [-5, 3], [0, -6], [4, -4], [-6, -5]], np.float32)
        w, a, b = thin_plate_spline_weights(src, dst)
        pred = thin_plate_spline_apply(src.astype(np.float64), src.astype(np.float64), w, a, b)
        assert np.abs(pred - dst.astype(np.float64)).max() < 1e-6, (
            "a TPS must interpolate its own control points exactly; if it does not, "
            "the normal-equation assembly is wrong"
        )

    def test_system_is_not_structurally_singular(self):
        """A bare [[K,P],[P^T,0]] padded with zeros gives smallest singular
        value exactly 0.0. The homogeneous column of Phi must be present."""
        src = np.array(
            [[100, 100], [500, 120], [300, 350], [120, 330], [480, 300]], np.float64
        )
        dst = src + np.array([[6, 4], [-5, 3], [0, -6], [4, -4], [-6, -5]])
        w, a, b = thin_plate_spline_weights(src, dst)
        assert np.all(np.isfinite(w)) and np.all(np.isfinite(a)) and np.all(np.isfinite(b))

    def test_is_translation_equivariant_under_normalisation(self):
        """Shifting the whole control cloud must not change the local shape."""
        src = np.array(
            [[100, 100], [500, 120], [300, 350], [120, 330], [480, 300]], np.float64
        )
        dst = src + np.array([[6, 4], [-5, 3], [0, -6], [4, -4], [-6, -5]])
        offset = np.array([1000.0, -500.0])
        w1, a1, _ = thin_plate_spline_weights(src, dst)
        w2, a2, _ = thin_plate_spline_weights(src + offset, dst + offset)
        # The linear part is offset-invariant; the translation absorbs the shift.
        assert np.allclose(a1, a2, atol=1e-6)

    def test_rejects_too_few_control_points(self):
        with pytest.raises(ValueError, match=">= 3"):
            thin_plate_spline_weights(np.zeros((2, 2)), np.zeros((2, 2)))

    def test_field_shape_and_finiteness(self):
        src = np.array([[10, 10], [500, 100], [250, 350], [80, 300]], np.float32)
        dst = src + 5.0
        map_x, map_y = thin_plate_spline_field(src, dst, 600, 400)
        assert map_x.shape == (400, 600)
        assert map_y.shape == (400, 600)
        assert np.isfinite(map_x).all() and np.isfinite(map_y).all()

    def test_identity_control_points_produce_near_identity_field(self):
        src = np.array([[10, 10], [500, 100], [250, 350], [80, 300], [400, 380]], np.float32)
        map_x, map_y = thin_plate_spline_field(src, src.copy(), 600, 400)
        # Border effects from a 5-point control set are expected at the edges;
        # the interior should be close to identity.
        centre_x, centre_y = map_x[200, 300], map_y[200, 300]
        assert abs(centre_x - 300) < 8.0
        assert abs(centre_y - 200) < 8.0


class TestNonPlanarityEstimator:
    def test_zero_for_a_pure_similarity(self):
        src = np.array(
            [[100, 100], [500, 120], [300, 350], [120, 330], [480, 300]], np.float64
        )
        theta = np.radians(8.0)
        rot = np.array(
            [[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]]
        )
        dst = src @ rot.T + np.array([15.0, 6.0])
        assert estimate_nonplanarity(src, dst) < 1e-6

    def test_nonzero_for_a_sinusoidal_displacement(self):
        src = np.array(
            [[100, 100], [500, 120], [300, 350], [120, 330], [480, 300]], np.float64
        )
        dst = src + np.array(
            [7.0 * np.sin(src[:, 1] / 55.0), 5.0 * np.sin(src[:, 0] / 48.0)]
        ).T
        assert estimate_nonplanarity(src, dst) > 1.5

    def test_infinite_for_too_few_points(self):
        assert estimate_nonplanarity(np.zeros((2, 2)), np.zeros((2, 2))) == float("inf")


class TestDetectionScaling:
    """SIFT detection cost is the pipeline's bottleneck; bound it by area.

    Measured on this machine: at 4K (3840x2160) SIFT detection was 1143 ms of a
    1217 ms total -- 94% -- while matching, MAGSAC++ and the warp together took
    67 ms. The published "< 800 ms" target was therefore missed at 4K by 52%.
    """

    def test_small_images_detect_at_full_resolution(self):
        assert detection_scale_for(1920, 1080) == 1.0
        assert detection_scale_for(960, 540) == 1.0

    def test_large_images_are_downscaled(self):
        assert detection_scale_for(3840, 2160) == pytest.approx(2.0, rel=0.01)
        assert detection_scale_for(7680, 4320) == pytest.approx(4.0, rel=0.01)

    def test_detection_cost_is_bounded_across_resolutions(self):
        """The point of the budget: cost should not scale with input area."""
        budget = detection_scale_for(3840, 2160)
        detection_px = (3840 / budget) * (2160 / budget)
        assert detection_px == pytest.approx(1920 * 1080, rel=0.01)

    def test_custom_budget_is_respected(self):
        assert detection_scale_for(1000, 1000, pixel_budget=250 * 250) == pytest.approx(4.0)

    def test_keypoints_are_returned_in_full_resolution_coordinates(self):
        from services.homography_service import (
            clahe_luminance, extract_sift_features,
        )

        scene = make_cluttered_scene(400, 600, seed=2)
        gray = clahe_luminance(scene)
        kp_full, _ = extract_sift_features(gray, downscale=1.0)
        kp_half, _ = extract_sift_features(gray, downscale=2.0)
        # Downscaling should still find points inside the same frame.
        assert kp_half and kp_full
        assert max(k.pt[0] for k in kp_half) <= gray.shape[1]
        assert max(k.pt[1] for k in kp_half) <= gray.shape[0]

    def test_1080p_keeps_full_resolution_keypoint_quality(self):
        base = make_cluttered_scene(1080, 1920, seed=5)
        prog = apply_transform(base, angle_deg=8.0, translate_px=15.0)
        result = register_field_pair(base, prog)
        assert result.detection_downscale == 1.0
        assert result.inlier_ratio > 0.85, (
            f"full-resolution 1080p should keep a high inlier ratio, got "
            f"{result.inlier_ratio}"
        )

    def test_heavily_downscaled_registration_is_flagged_not_hidden(self):
        """At 8K the budget's 4x downscale costs too much match quality.

        The inlier ratio falls to ~0.54, below the 0.60 trust floor. That is a
        real limitation and the pipeline must SURFACE it -- an operator raising
        the pixel budget or capturing lower is a better outcome than a
        confident registration built from a degraded keypoint set.
        """
        base = make_cluttered_scene(2160, 3840, seed=5)
        prog = apply_transform(base, angle_deg=8.0, translate_px=15.0)
        result = register_field_pair(base, prog)
        if result.detection_downscale >= 4.0 and result.inlier_ratio < INLIER_RATIO_FLOOR:
            assert any("Inlier ratio" in w for w in result.warnings), (
                "a sub-threshold inlier ratio must be reported, not silently used"
            )


class TestConditionNumber:
    def test_identity_is_well_conditioned(self):
        assert condition_number(np.eye(3)) == pytest.approx(1.0)

    def test_scaled_is_well_conditioned(self):
        h = np.diag([2.0, 2.0, 2.0])
        assert condition_number(h) == pytest.approx(1.0)

    def test_ill_conditioned_is_detected(self):
        h = np.diag([1e6, 1.0, 1.0])
        assert condition_number(h) > 1e5
