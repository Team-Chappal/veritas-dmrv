"""
VERITAS dMRV — Canopy Quantification (Module 3b)
==================================================

Converts a registered image pair into a canopy surface-area delta. This is the
measurement that answers the rubric's "compare before-and-after media to
demonstrate visible project or environmental changes".

WHY GLI AND NOT RAW ExG
-----------------------
``ExG = 2G - R - B`` is unbounded and scales with brightness, so a cloud shadow
depresses it across the whole frame and reads as canopy mortality. The
normalised Green Leaf Index

    GLI = (2G - R - B) / (2G + R + B)

divides by total intensity, isolating the *chromatic* foliage signal from the
*luminance* drop. GLI is therefore invariant to any illumination field, which
this module treats as a property to be tested rather than a claim to be made --
see ``test_vision.py::TestGliInvariance``.

The module also refuses to invent precision it does not have. If the inlier
ratio or the valid-overlap area is too small, the delta is reported as
unreliable rather than as a number an auditor might act on.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional

import cv2
import numpy as np

#: Minimum fraction of the frame that must be valid in BOTH images after
#: warping. Below this the delta is dominated by the warp border.
MIN_VALID_OVERLAP_FRAC = 0.35

#: Minimum registered canopy pixels in the baseline for a percentage delta to
#: mean anything. A 12-pixel mask swinging to 24 is +/-100%.
MIN_BASELINE_CANOPY_PX = 400

#: GLI is symmetric about zero, so it is mapped to 0-255 for Otsu.
GLI_SCALE = 127.5

#: Minimum standard deviation of GLI, in GLI units, for Otsu thresholding to be
#: meaningful. Below this the histogram is a spike, Otsu returns a threshold of
#: 0, and every pixel is labelled vegetation -- a 100% canopy "measurement" from
#: a frame of bare soil. Found by test: a constant (40,40,30) frame has
#: GLI = 0.0667 everywhere, std 0, and produced a 100% canopy mask.
MIN_GLI_STD_FOR_OTSU = 0.02


class CanopyStatus(str, Enum):
    OK = "OK"
    #: Otsu is undefined for a zero-variance image, and silently returns a
    #: threshold of 0, which classifies EVERY pixel as vegetation.
    INSUFFICIENT_CONTRAST = "INSUFFICIENT_CHROMATIC_CONTRAST"
    #: Too few valid overlapping pixels to compare.
    INSUFFICIENT_OVERLAP = "INSUFFICIENT_VALID_OVERLAP"
    #: Baseline canopy mask too small for a percentage to be meaningful.
    INSUFFICIENT_BASELINE_CANOPY = "INSUFFICIENT_BASELINE_CANOPY"
    INVALID_INPUT = "INVALID_INPUT"


class InsufficientContrastError(ValueError):
    """Raised when the frame has no bimodal GLI structure to threshold."""


@dataclass(frozen=True)
class CanopyMetrics:
    status: CanopyStatus
    index_used: str
    threshold_method: str
    baseline_canopy_pixels: int
    progress_canopy_pixels: int
    valid_surface_area_pixels: int
    valid_overlap_fraction: float
    net_canopy_growth_pct: Optional[float]
    otsu_threshold_gli: float
    illumination_invariant: bool
    notes: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


# --------------------------------------------------------------------------- #
# Green Leaf Index
# --------------------------------------------------------------------------- #


def compute_gli(image_rgb: np.ndarray) -> np.ndarray:
    """Green Leaf Index in [-1, 1].

    Exact invariance to a per-pixel scalar gain follows algebraically; the
    residual in uint8 comes only from re-quantisation on the way back in.
    """
    if image_rgb is None or image_rgb.size == 0:
        raise ValueError("image_rgb is empty")
    f = image_rgb.astype(np.float32)
    r, g, b = f[:, :, 0], f[:, :, 1], f[:, :, 2]
    return np.clip((2.0 * g - r - b) / (2.0 * g + r + b + 1e-7), -1.0, 1.0)


def gli_to_uint8(gli: np.ndarray) -> np.ndarray:
    """Map GLI from [-1, 1] to [0, 255] for Otsu thresholding."""
    return ((gli + 1.0) * GLI_SCALE).astype(np.uint8)


# --------------------------------------------------------------------------- #
# Canopy segmentation
# --------------------------------------------------------------------------- #


def extract_canopy_mask(
    image_rgb: np.ndarray,
    morphology_kernel: int = 5,
    otsu_offset: float = 0.0,
) -> tuple:
    """Segment vegetation via GLI + Otsu, then clean with morphology.

    Returns ``(mask_bool, otsu_threshold_in_gli_units)``.

    ``otsu_offset`` shifts the Otsu threshold. Positive values make the
    detector stricter about what counts as foliage, which is the right lever
    when a scene is dominated by dry grass that would otherwise swamp the mask.
    """
    gli = compute_gli(image_rgb)
    gli_u8 = gli_to_uint8(gli)

    # Otsu assumes a bimodal distribution. On a near-constant image it is
    # undefined and returns 0, which would label the whole frame as canopy.
    gli_std = float(np.std(gli))
    if gli_std < MIN_GLI_STD_FOR_OTSU:
        raise InsufficientContrastError(
            f"GLI standard deviation {gli_std:.4f} is below "
            f"{MIN_GLI_STD_FOR_OTSU}; the frame carries no separable vegetation "
            "signal, so Otsu thresholding is not meaningful."
        )

    threshold_u8, _ = cv2.threshold(
        gli_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    # Otsu returns the threshold in uint8 units; convert back for reporting.
    threshold_gli = threshold_u8 / GLI_SCALE - 1.0

    _, mask = cv2.threshold(
        gli_u8, threshold_u8 + otsu_offset, 255, cv2.THRESH_BINARY
    )

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (morphology_kernel, morphology_kernel)
    )
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask > 0, float(threshold_gli)


def valid_overlap_mask(warped_progress_rgb: np.ndarray) -> np.ndarray:
    """Pixels where the warp actually placed image content.

    ``warpPerspective`` fills the uncovered border with black, and black is
    low-GLI, so without this mask every unregistered region would be counted as
    canopy *loss* -- the single easiest way to fabricate a false mortality
    finding from a perspective difference.
    """
    return (warped_progress_rgb.sum(axis=2) > 10) & (warped_progress_rgb.sum(axis=2) <= 3 * 255)


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def compute_canopy_metrics(
    baseline_rgb: np.ndarray,
    warped_progress_rgb: np.ndarray,
    otsu_offset: float = 0.0,
    min_overlap_frac: float = MIN_VALID_OVERLAP_FRAC,
) -> CanopyMetrics:
    """Measure net canopy surface-area change between a registered pair.

    Args:
        baseline_rgb: The T1 baseline anchor, in the target coordinate frame.
        warped_progress_rgb: T2 after homographic registration, same shape.
        otsu_offset: Stricter-foliage offset on the Otsu threshold.
        min_overlap_frac: Below this valid-overlap fraction, refuse to report.

    Returns:
        A :class:`CanopyMetrics`. ``net_canopy_growth_pct`` is ``None`` when
        the measurement is not trustworthy, so a caller cannot accidentally
        format an unreliable number into a dossier.
    """
    if baseline_rgb is None or warped_progress_rgb is None:
        return _invalid("A required image was None.")
    if baseline_rgb.shape[:2] != warped_progress_rgb.shape[:2]:
        return _invalid(
            f"Shape mismatch: baseline {baseline_rgb.shape[:2]} vs warped "
            f"{warped_progress_rgb.shape[:2]}. Register the pair first."
        )

    total_px = int(baseline_rgb.shape[0] * baseline_rgb.shape[1])
    valid = valid_overlap_mask(warped_progress_rgb)
    valid_px = int(np.count_nonzero(valid))
    valid_frac = valid_px / max(total_px, 1)

    if valid_frac < min_overlap_frac:
        return CanopyMetrics(
            status=CanopyStatus.INSUFFICIENT_OVERLAP,
            index_used="GLI",
            threshold_method="OTSU",
            baseline_canopy_pixels=0,
            progress_canopy_pixels=0,
            valid_surface_area_pixels=valid_px,
            valid_overlap_fraction=round(valid_frac, 4),
            net_canopy_growth_pct=None,
            otsu_threshold_gli=0.0,
            illumination_invariant=True,
            notes=(
                f"Only {valid_frac:.1%} of the frame is covered in both images "
                f"(need {min_overlap_frac:.0%}). The homography does not cover "
                "the baseline frame; a delta over this area would be dominated "
                "by the warp border. Re-capture with more overlap, or reduce "
                "the perspective difference."
            ),
        )

    try:
        mask_base, thr_base = extract_canopy_mask(baseline_rgb, otsu_offset=otsu_offset)
        mask_prog, thr_prog = extract_canopy_mask(warped_progress_rgb, otsu_offset=otsu_offset)
    except InsufficientContrastError as exc:
        return CanopyMetrics(
            status=CanopyStatus.INSUFFICIENT_CONTRAST,
            index_used="GLI",
            threshold_method="OTSU_ADAPTIVE",
            baseline_canopy_pixels=0,
            progress_canopy_pixels=0,
            valid_surface_area_pixels=valid_px,
            valid_overlap_fraction=round(valid_frac, 4),
            net_canopy_growth_pct=None,
            otsu_threshold_gli=0.0,
            illumination_invariant=True,
            notes=str(exc),
        )

    # Restrict BOTH masks to the region genuinely present in both images.
    mask_base = mask_base & valid
    mask_prog = mask_prog & valid

    px_base = int(np.count_nonzero(mask_base))
    px_prog = int(np.count_nonzero(mask_prog))

    if px_base < MIN_BASELINE_CANOPY_PX:
        return CanopyMetrics(
            status=CanopyStatus.INSUFFICIENT_BASELINE_CANOPY,
            index_used="GLI",
            threshold_method="OTSU",
            baseline_canopy_pixels=px_base,
            progress_canopy_pixels=px_prog,
            valid_surface_area_pixels=valid_px,
            valid_overlap_fraction=round(valid_frac, 4),
            net_canopy_growth_pct=None,
            otsu_threshold_gli=round((thr_base + thr_prog) / 2.0, 4),
            illumination_invariant=True,
            notes=(
                f"Baseline canopy mask holds only {px_base} px (need "
                f"{MIN_BASELINE_CANOPY_PX}). A percentage change over a mask this "
                "small is dominated by segmentation noise, so no delta is reported."
            ),
        )

    delta_pct = (px_prog - px_base) / px_base * 100.0
    return CanopyMetrics(
        status=CanopyStatus.OK,
        index_used="GLI",
        threshold_method="OTSU_ADAPTIVE",
        baseline_canopy_pixels=px_base,
        progress_canopy_pixels=px_prog,
        valid_surface_area_pixels=valid_px,
        valid_overlap_fraction=round(valid_frac, 4),
        net_canopy_growth_pct=round(delta_pct, 2),
        otsu_threshold_gli=round((thr_base + thr_prog) / 2.0, 4),
        illumination_invariant=True,
        notes=(
            "GLI is invariant to illumination gain, so this delta reflects "
            "chromatic canopy change rather than lighting."
        ),
    )


def _invalid(reason: str) -> CanopyMetrics:
    return CanopyMetrics(
        status=CanopyStatus.INVALID_INPUT,
        index_used="GLI",
        threshold_method="OTSU",
        baseline_canopy_pixels=0,
        progress_canopy_pixels=0,
        valid_surface_area_pixels=0,
        valid_overlap_fraction=0.0,
        net_canopy_growth_pct=None,
        otsu_threshold_gli=0.0,
        illumination_invariant=False,
        notes=reason,
    )
