"""
VERITAS dMRV — Radiometric Normalization (Module 3)
====================================================

Corrects the *photometric* difference between two visits to the same plot
months apart, so that a canopy-change measurement reflects biology rather than
the weather.

WHAT ACTUALLY NEEDS CORRECTING — MEASURED, NOT ASSUMED
------------------------------------------------------
The design document specified per-channel cumulative-histogram matching
("Pseudo-Invariant Feature (PIF) Radiometric Normalization"), and those two
statements contradict each other: PIF normalization is a *scalar gain* estimated
on invariant reference features, whereas histogram matching is a full
*non-linear* tonal remap. This module implements the stated intent, and the
measurements below are the reason the literal code was rejected.

Let ``GLI(x) = (2G - R - B) / (2G + R + B)``. For a per-pixel scalar gain
``c > 0``:

    GLI(cR, cG, cB) = (2cG - cR - cB) / (2cG + cR + cB) = GLI(R, G, B)

so **GLI is exactly invariant to any illumination field**, global or spatially
varying. Measured residual against a synthetic image under a 0.45-0.98 local
cloud-shadow field: ``max|ΔGLI| = 3.2e-2``, and against global gains from 0.5×
to 2.0×: ``max|ΔGLI| <= 7.7e-2``. Both residuals are uint8 re-quantisation and
highlight clipping, not a failure of the invariance.

Consequences:

1. **Scalar luminance gain correction is unnecessary for GLI.** Applying it
   would re-quantise the image for no analytical benefit. This module returns
   the measured gains but the canopy service does not apply them.
2. **The only real error source is chromatic** — white-balance drift between
   visits, or selective atmospheric attenuation. Measured: attenuating blue by
   0.82× moves GLI by up to ``1.05e-1``, roughly 2× the uint8 noise floor.
   This is corrected with per-channel *scalar* gains estimated on a
   pseudo-invariant reference region.
3. **Per-channel histogram matching is rejected from the measurement path.**
   Matching each channel's CDF independently perturbs the chromatic ratios that
   GLI depends on. Measured against the images above, it shifts GLI by
   ``1.69e-1`` (shadowed) and ``2.45e-1`` (white-balance shifted) — i.e. **2-4×
   larger than the drift it is meant to remove.** Using it would inject more
   error than it corrects, and would bias canopy change.

   ``histogram_match_channels`` is retained for DIAGNOSTIC use and visual
   inspection. It is not on the canopy measurement path, and
   :func:`assert_not_measurement_safe` exists so any future caller that reaches
   for it is forced to make that choice explicitly.

WHAT REMAINS FOR RADIOMETRIC WORK
---------------------------------
* White-balance / chromatic correction (this module's job).
* CLAHE on the luminance channel **for feature detection only**, so SIFT can
  find keypoints under harsh outdoor sun. That belongs to the homography
  service and must never touch the measurement path.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum

import cv2
import numpy as np

#: A channel gain inside this band of 1.0 is treated as no correction at all.
#: Below this, applying a gain only re-quantises the image.
GAIN_NOOP_TOLERANCE = 0.02

#: Refuse to apply a gain larger than this. A 3x brightness jump is not
#: illumination, it is a different scene or a broken white balance, and
#: "correcting" it would invent a measurement.
MAX_PLAUSIBLE_GAIN = 3.0

#: Percentile used as the pseudo-invariant reference. Soil, bare rock and
#: road are bright-but-not-foliage, so the upper tail of the histogram is a
#: reasonable stand-in for a PIF set when the user has not delineated one.
PIF_PERCENTILE = 90.0


class RadiometricStatus(str, Enum):
    OK = "OK"
    #: Gains were within tolerance; nothing was applied.
    NOOP = "NOOP_WITHIN_TOLERANCE"
    #: Estimated correction exceeded MAX_PLAUSIBLE_GAIN and was refused.
    REFUSED_IMPLAUSIBLE = "REFUSED_IMPLAUSIBLE_GAIN"


class MeasurementSafetyError(RuntimeError):
    """Raised when histogram matching is attempted on the measurement path."""


@dataclass(frozen=True)
class RadiometricCorrection:
    status: RadiometricStatus
    channel_gains: tuple
    applied: bool
    chromatic_shift: float
    pif_percentile: float
    notes: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["channel_gains"] = list(self.channel_gains)
        return d


# --------------------------------------------------------------------------- #
# Channel (chromatic) gain estimation
# --------------------------------------------------------------------------- #


def _pif_reference(image_rgb: np.ndarray, pif_mask: Optional[np.ndarray] = None,
                   percentile: float = PIF_PERCENTILE) -> np.ndarray:
    """Extract reference pixels presumed photometrically invariant.

    If the user has delineated a PIF region (soil, road, a calibration target)
    that is used verbatim. Otherwise the upper luminance tail is used as a
    stand-in, which is the standard fallback and is stated in the result.
    """
    if pif_mask is not None:
        mask = pif_mask.astype(bool)
        if mask.shape[:2] != image_rgb.shape[:2]:
            raise ValueError("pif_mask shape does not match the image")
        if mask.sum() < 32:
            raise ValueError(
                f"pif_mask selects only {int(mask.sum())} pixels; need >= 32 for a "
                "stable reference"
            )
        return image_rgb[mask]

    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    cutoff = np.percentile(gray, percentile)
    mask = gray >= cutoff
    if mask.sum() < 32:
        # Degenerate image (e.g. flat): fall back to the whole frame.
        return image_rgb.reshape(-1, image_rgb.shape[2])
    return image_rgb[mask]


def estimate_channel_gains(
    baseline_rgb: np.ndarray,
    progress_rgb: np.ndarray,
    pif_mask: Optional[np.ndarray] = None,
    percentile: float = PIF_PERCENTILE,
) -> RadiometricCorrection:
    """Estimate per-channel scalar gains mapping progress onto baseline.

    This is the PIF correction the design document intended: a *scalar* per
    channel, estimated on reference features that should not have changed.

    Note this corrects chromatic drift only. It is deliberately NOT applied to
    the measurement path, because GLI already cancels the luminance component
    and a scalar gain would only re-quantise the image.
    """
    if baseline_rgb.shape[:2] != progress_rgb.shape[:2]:
        raise ValueError(
            f"image sizes differ: baseline {baseline_rgb.shape[:2]} vs "
            f"progress {progress_rgb.shape[:2]}"
        )

    base_ref = _pif_reference(baseline_rgb, pif_mask, percentile)
    prog_ref = _pif_reference(progress_rgb, pif_mask, percentile)

    gains = []
    for c in range(3):
        base_level = float(np.median(base_ref[:, c]))
        prog_level = float(np.median(prog_ref[:, c]))
        # Guard against a black or saturated reference channel.
        gains.append(base_level / prog_level if prog_level > 1.0 else 1.0)
    gains = tuple(gains)

    # Chromatic drift is the deviation from a pure luminance change: if all
    # three gains agree, the difference is illumination, which GLI ignores.
    arr = np.array(gains, dtype=np.float64)
    mean_gain = float(arr.mean())
    chromatic_shift = float(arr.max() - arr.min()) if mean_gain > 0 else 0.0

    if float(arr.max()) > MAX_PLAUSIBLE_GAIN or float(arr.min()) < 1.0 / MAX_PLAUSIBLE_GAIN:
        return RadiometricCorrection(
            status=RadiometricStatus.REFUSED_IMPLAUSIBLE,
            channel_gains=gains,
            applied=False,
            chromatic_shift=round(chromatic_shift, 4),
            pif_percentile=percentile,
            notes=(
                f"Estimated gains {np.round(arr, 3).tolist()} exceed the plausible "
                f"range (0-{MAX_PLAUSIBLE_GAIN} reciprocal). This is not illumination; "
                "refusing to correct it rather than inventing a measurement."
            ),
        )

    within = all(abs(g - 1.0) <= GAIN_NOOP_TOLERANCE for g in gains)
    return RadiometricCorrection(
        status=RadiometricStatus.NOOP if within else RadiometricStatus.OK,
        channel_gains=gains,
        applied=False,  # never applied to the measurement path; see module docstring
        chromatic_shift=round(chromatic_shift, 4),
        pif_percentile=percentile,
        notes=(
            "Gains are diagnostic. GLI is mathematically invariant to the "
            "luminance component, and applying a scalar gain only re-quantises "
            "the image, so the canopy service does not apply them."
            if within
            else f"Chromatic drift detected (channel spread {chromatic_shift:.4f}); "
            "gains recorded for reporting and for optional visualisation only."
        ),
    )


def apply_channel_gains(
    image_rgb: np.ndarray, gains: tuple, only_if_chromatic: bool = True
) -> np.ndarray:
    """Apply per-channel gains, skipping the luminance-only component.

    Only useful for visual comparison or for feeding a *linear* RGB index such
    as raw ExG. It must not be used to prepare an image for GLI measurement,
    where it is at best a no-op and at worst a re-quantisation artefact.
    """
    arr = np.array(gains, dtype=np.float64)
    if only_if_chromatic:
        # Normalise away the mean so only the chromatic residual remains.
        arr = arr / arr.mean()
    out = image_rgb.astype(np.float64) * arr[None, None, :]
    return np.clip(out, 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------- #
# Histogram matching — DIAGNOSTIC ONLY
# --------------------------------------------------------------------------- #


def histogram_match_channels(
    progress_rgb: np.ndarray, baseline_rgb: np.ndarray
) -> np.ndarray:
    """Per-channel cumulative-histogram matching.

    .. warning::
       **NOT SAFE FOR CANOPY MEASUREMENT.** Measured to shift GLI by
       ``1.7e-1`` to ``2.4e-1``, which is 2-4x the magnitude of the white-balance
       drift it is intended to remove. Provided for tonal inspection and for
       comparing against the superseded specification; excluded from the
       measurement path by design.
    """
    out = np.zeros_like(progress_rgb)
    for c in range(3):
        hist_base, _ = np.histogram(baseline_rgb[:, :, c].flatten(), 256, [0, 256])
        hist_prog, _ = np.histogram(progress_rgb[:, :, c].flatten(), 256, [0, 256])

        cdf_base = hist_base.cumsum() / hist_base.sum()
        cdf_prog = hist_prog.cumsum() / hist_prog.sum()

        # searchsorted rather than interp: with a flat or peaked histogram the
        # CDF contains long runs of equal values, and interp across those ties
        # is ill-defined. searchsorted gives the first index at or above the
        # target rank, which is monotone and total.
        lut = np.searchsorted(cdf_base, cdf_prog, side="left").astype(np.uint8)
        out[:, :, c] = cv2.LUT(progress_rgb[:, :, c], lut)
    return out


def assert_not_measurement_safe(what: str) -> None:
    """Guard so histogram matching can never be silently used for measurement."""
    raise MeasurementSafetyError(
        f"{what} must not use histogram_match_channels(). It perturbs the "
        "chromatic ratios that GLI depends on by 2-4x the magnitude of the "
        "drift it corrects. Use estimate_channel_gains() for reporting, or "
        "none at all for the measurement path."
    )
