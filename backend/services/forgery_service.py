"""
VERITAS dMRV — Synthetic Media & Screen-Replay Forgery Detection (Module 6)
===========================================================================

Three independent forensic signals, each targeting a different real-world
attack. They are combined here rather than in a single heuristic because each
one has a distinct false-positive profile.

  1. DIFFUSION-GENERATED FOLIAGE (Midjourney / SD / Flux)
     Natural foliage captured by a CMOS sensor carries Poisson-distributed
     photon shot noise across the whole high-frequency band. Diffusion models
     synthesise plausible foliage but their micro-noise is measurably smoother,
     because the denoiser has already consumed exactly the high-frequency
     content that makes a real photograph look real.
     Signal: low Laplacian variance.

  2. DIFFUSION UPSCALER CHECKERBOARD  [ADVISORY — NOT VALIDATED]
     Several open upscalers emit a faint periodic grid, which should appear as a
     dominant spectral peak in the 2D FFT magnitude spectrum once DC is masked.
     Measured on synthetic controls this signal does NOT separate: natural 1.30,
     over-smoothed 2.14, screen-replay 2.28, against a specified threshold of
     3.80. It never fires on any control we can construct. It is therefore
     reported but NEVER auto-quarantines.

  3. SCREEN RE-PHOTOGRAPHY  [ADVISORY — THE SPECIFIED METRIC DOES NOT WORK]
     The design document specified
     ``np.std(Sobel gradient magnitude) / np.mean(...) > 4.2``. That threshold
     was tested against genuine Moire beat patterns (two nearby spatial
     frequencies producing a spatially modulated beat, at pitches 2-4 px and
     amplitudes 60-110, with and without a slowly varying envelope). Measured
     coefficient of variation ranged 0.63-0.94.

     **The threshold is not achievable by the phenomenon it claims to detect,
     and the metric inverts.** A clean, well-exposed natural photograph scored
     2.49 — HIGHER than every genuine Moire construction we built, because the
     denominator (mean gradient) shrinks as an image gets smoother. Shipping
     this as specified would have produced false fraud accusations against
     exactly the high-quality, low-noise photographs a restoration programme is
     most careful to submit.

     We also tried a physically-motivated alternative: a subpixel R/B channel
     phase offset measured with `cv2.phaseCorrelate`, which is the direct
     signature of a subpixel RGB stripe array. On these images it returned
     nonsense (lag ~268 px on a 640 px frame, response 0.03), so it is not
     usable as-is either.

     Screen-replay detection is therefore **UNVALIDATED** and is carried as an
     advisory signal only. It routes to human review. It does not quarantine.
     Validating it properly requires a labelled corpus of genuine rephotographed
     displays, which this project does not have.

CALIBRATION STATUS — READ THIS BEFORE QUOTING A NUMBER
-----------------------------------------------------
Only signal 1 (Laplacian variance) currently separates its controls: natural
2897 vs over-smoothed 2.4, a 36x gap against a threshold of 80. That gap is
real, but it was measured on SYNTHETIC controls, not a labelled corpus of real
photographs and real diffusion outputs. It is a strong engineering prior, not a
calibrated classifier.

``confidence_score`` reflects detector agreement, NOT a calibrated posterior.
The statistically honest place for a calibrated probability is the JEV RLCD
decision layer, which consumes these features alongside others and owns the
confidence claim.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum

import cv2
import numpy as np

# --------------------------------------------------------------------------- #
# Thresholds — outdoor environmental photography
# --------------------------------------------------------------------------- #

#: Below this high-frequency Laplacian variance, micro-noise looks synthesised.
#: Natural outdoor scenes sit comfortably above it.
LAPLACIAN_VARIANCE_SUSPICIOUS = 80.0

#: Above this, the FFT magnitude spectrum shows a dominant periodic peak
#: consistent with an upscaler grid artefact.
FFT_PEAK_RATIO_SUSPICIOUS = 3.8

#: Above this, the Sobel gradient-magnitude coefficient of variation indicates
#: periodic subpixel beat interference (Moiré) from re-photographing a display.
MOIRE_ENERGY_RATIO_SUSPICIOUS = 4.2

#: Central FFT region to mask before measuring the high-frequency spectrum.
_FFT_CENTRE_MASK_PX = 20

#: Signals that have been measured to separate anything. Only these may trigger
#: an automated quarantine. Everything else is advisory and routes to a human.
VALIDATED_SIGNALS = frozenset({"low_laplacian_noise_variance"})

#: Advisory signals that are reported but must never auto-quarantine.
UNVALIDATED_SIGNALS = frozenset({"fft_checkerboard_peak", "moire_subpixel_beat"})


class ForgeryAction(str, Enum):
    NATURAL_SENSOR_CONFIRMED = "NATURAL_SENSOR_CONFIRMED"
    QUARANTINE_SYNTHETIC = "QUARANTINE_SYNTHETIC"
    #: Advisory only. The underlying signal is unvalidated and must not accuse.
    REVIEW_SCREEN_REPLAY_SUSPECTED = "REVIEW_SCREEN_REPLAY_SUSPECTED"
    REVIEW_INSUFFICIENT = "REVIEW_INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class ForgeryReport:
    action: ForgeryAction
    is_synthetic_ai_flagged: bool
    is_screen_replay_detected: bool
    laplacian_noise_variance: float
    fft_frequency_peak_ratio: float
    moire_subpixel_energy_ratio: float
    signals_triggered: tuple
    notes: str
    #: Always True. Screen-replay detection is unvalidated and must never be
    #: presented to an auditor as a confirmed finding.
    is_screen_replay_unvalidated: bool = True

    def to_dict(self) -> dict:
        d = asdict(self)
        d["action"] = self.action.value
        d["signals_triggered"] = list(self.signals_triggered)
        return d


# --------------------------------------------------------------------------- #
# Individual signals
# --------------------------------------------------------------------------- #


def _to_gray(image_rgb: np.ndarray) -> np.ndarray:
    if image_rgb is None or image_rgb.size == 0:
        raise ValueError("image_rgb is empty")
    if image_rgb.ndim == 2:
        return image_rgb.astype(np.uint8)
    if image_rgb.shape[2] == 4:
        image_rgb = cv2.cvtColor(image_rgb, cv2.COLOR_RGBA2RGB)
    return cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)


def laplacian_noise_variance(image_rgb: np.ndarray) -> float:
    """High-frequency energy. Low values indicate over-smoothed synthesis."""
    gray = _to_gray(image_rgb)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def fft_peak_ratio(image_rgb: np.ndarray) -> float:
    """Peak-to-average of the high-frequency 2D FFT magnitude spectrum.

    The DC centre is zeroed first, otherwise the mean is dominated by the
    image's overall brightness and the ratio collapses toward 1.
    """
    gray = _to_gray(image_rgb)
    spectrum = np.fft.fftshift(np.fft.fft2(gray))
    magnitude = 20.0 * np.log(np.abs(spectrum) + 1e-7)

    h, w = gray.shape[:2]
    cy, cx = h // 2, w // 2
    margin = _FFT_CENTRE_MASK_PX
    if h > 2 * margin and w > 2 * margin:
        magnitude[cy - margin : cy + margin, cx - margin : cx + margin] = 0.0

    peak = float(np.max(magnitude))
    mean = float(np.mean(magnitude))
    return peak / (mean + 1e-7)


def moire_subpixel_energy_ratio(image_rgb: np.ndarray) -> float:
    """Coefficient of variation of Sobel gradient magnitude.

    Moiré beat interference was expected to make the gradient-magnitude
    distribution heavy-tailed, so its standard deviation would jump relative to
    its mean.

    MEASURED BEHAVIOUR: this does not work as a detector. Genuine Moire beat
    patterns (two nearby spatial frequencies, pitches 2-4 px, amplitudes
    60-110, with and without a slowly varying envelope) yield 0.63-0.94, while
    the specified threshold is 4.2 and clean natural photographs reach 2.49.
    The metric correlates with image SMOOTHNESS, not with display re-photography.
    Retained as a diagnostic only.
    """
    gray = _to_gray(image_rgb).astype(np.float64)
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    magnitude = np.sqrt(gx**2 + gy**2)
    mean = float(np.mean(magnitude))
    if mean <= 0.0:
        return 0.0
    return float(np.std(magnitude) / mean)


# --------------------------------------------------------------------------- #
# Combined detector
# --------------------------------------------------------------------------- #


def detect_synthetic_media(image_rgb: np.ndarray) -> ForgeryReport:
    """Run all three forensic signals and combine them into one action."""
    try:
        if image_rgb is None or getattr(image_rgb, "size", 0) == 0:
            raise ValueError("empty image")
        lap_var = laplacian_noise_variance(image_rgb)
        peak_ratio = fft_peak_ratio(image_rgb)
        moire = moire_subpixel_energy_ratio(image_rgb)
    except Exception as exc:
        return ForgeryReport(
            action=ForgeryAction.REVIEW_INSUFFICIENT,
            is_synthetic_ai_flagged=False,
            is_screen_replay_detected=False,
            laplacian_noise_variance=0.0,
            fft_frequency_peak_ratio=0.0,
            moire_subpixel_energy_ratio=0.0,
            signals_triggered=(),
            notes=f"Could not analyse image: {exc}",
        )

    signals: list = []

    if lap_var < LAPLACIAN_VARIANCE_SUSPICIOUS:
        signals.append("low_laplacian_noise_variance")
    if peak_ratio > FFT_PEAK_RATIO_SUSPICIOUS:
        signals.append("fft_checkerboard_peak")
    if moire > MOIRE_ENERGY_RATIO_SUSPICIOUS:
        signals.append("moire_subpixel_beat")

    # Only validated signals may accuse. Advisory signals can only escalate to
    # human review.
    validated_hits = [s for s in signals if s in VALIDATED_SIGNALS]
    advisory_hits = [s for s in signals if s in UNVALIDATED_SIGNALS]

    is_synthetic = lap_var < LAPLACIAN_VARIANCE_SUSPICIOUS
    is_screen_replay_suspected = moire > MOIRE_ENERGY_RATIO_SUSPICIOUS

    if validated_hits:
        action = ForgeryAction.QUARANTINE_SYNTHETIC
        notes = (
            "High-frequency signature is inconsistent with a CMOS sensor: "
            "either diffusion-generated or heavily post-processed. Quarantine "
            "rests on the Laplacian-variance signal, which is the only one "
            "measured to separate its controls."
        )
    elif advisory_hits:
        action = ForgeryAction.REVIEW_SCREEN_REPLAY_SUSPECTED
        notes = (
            "Advisory signal(s) "
            f"{advisory_hits} fired. These are NOT validated against a labelled "
            "corpus, so the asset is routed to human review rather than "
            "quarantined. Note that the specified screen-replay threshold "
            "(gradient CV > 4.2) was measured as unachievable against genuine "
            "Moire patterns, which peaked at 0.94, and is exceeded by some "
            "clean natural photographs (2.49)."
        )
    else:
        action = ForgeryAction.NATURAL_SENSOR_CONFIRMED
        notes = "All forensic signals are within natural-sensor range."

    return ForgeryReport(
        action=action,
        is_synthetic_ai_flagged=bool(is_synthetic),
        is_screen_replay_detected=bool(is_screen_replay_suspected and not is_synthetic),
        is_screen_replay_unvalidated=True,
        laplacian_noise_variance=round(lap_var, 2),
        fft_frequency_peak_ratio=round(peak_ratio, 2),
        moire_subpixel_energy_ratio=round(moire, 2),
        signals_triggered=tuple(signals),
        notes=notes,
    )
