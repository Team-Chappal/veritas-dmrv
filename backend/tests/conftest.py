"""
Shared pytest fixtures.

Everything here is generated deterministically. No test may depend on a
downloaded asset or a Cloudinary credential: a test that needs the network is
a test that will fail on stage.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

FIXTURE_PATH = BACKEND / "tests" / "fixtures" / "solar_vectors.json"


# --------------------------------------------------------------------------- #
# Solar fixtures
# --------------------------------------------------------------------------- #


def _load_solar_fixtures() -> list:
    if not FIXTURE_PATH.exists():
        pytest.exit(
            f"Solar fixtures missing at {FIXTURE_PATH}. "
            "Run: python scripts/gen_solar_fixtures.py",
            returncode=1,
        )
    return json.loads(FIXTURE_PATH.read_text())["fixtures"]


@pytest.fixture(scope="session")
def solar_fixtures() -> list:
    return _load_solar_fixtures()


@pytest.fixture(scope="session")
def genuine_fixtures(solar_fixtures) -> list:
    return [f for f in solar_fixtures if f["kind"] == "genuine"]


@pytest.fixture(scope="session")
def fraud_fixtures(solar_fixtures) -> list:
    return [f for f in solar_fixtures if f["kind"] == "fraud"]


@pytest.fixture(scope="session")
def abstain_fixtures(solar_fixtures) -> list:
    return [f for f in solar_fixtures if f["kind"] == "abstain"]


@pytest.fixture(scope="session")
def solar_meta(solar_fixtures) -> dict:
    return json.loads(FIXTURE_PATH.read_text())["_meta"]


def as_utc(iso: str) -> dt.datetime:
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))


# --------------------------------------------------------------------------- #
# Synthetic imagery
# --------------------------------------------------------------------------- #


def make_natural_image(
    height: int = 480, width: int = 640, seed: int = 7, noise_sigma: float = 18.0
) -> np.ndarray:
    """A plausible natural photograph: scene structure + sensor shot noise.

    The seed drives the SCENE STRUCTURE, not just the noise. An earlier version
    varied only the noise draw, which made every "different" image share the
    same deterministic sinusoid pattern — and pHash correctly returned a Hamming
    distance of 0 between them, because pHash is designed to ignore exactly that
    kind of difference. The test was wrong, not the detector.

    High-frequency content comes from the Poisson-ish Gaussian noise, which is
    what a real CMOS sensor contributes and what a diffusion model lacks.
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)

    # Structure parameters all vary with the seed, so two images from different
    # seeds depict genuinely different scenes.
    f1, f2, f3 = rng.uniform(18.0, 70.0, 3)
    p1, p2, p3 = rng.uniform(0.0, 2.0 * np.pi, 3)
    base = rng.uniform(60.0, 110.0, 3)
    amp = rng.uniform(25.0, 70.0, 3)

    img = np.stack(
        [
            base[0] + amp[0] * np.sin(xx / f1 + p1) * np.cos(yy / f2 + p2),
            base[1] + amp[1] * np.sin((xx + yy) / f3 + p3),
            base[2] + amp[2] * np.cos(yy / f1 + p3) * np.sin(xx / f3 + p1),
        ],
        axis=2,
    )

    # A few dark blobs so the scene has real object edges, not only gradients.
    for _ in range(12):
        cx, cy = int(rng.integers(0, width)), int(rng.integers(0, height))
        radius = int(rng.integers(12, 40))
        import cv2 as _cv2

        colour = tuple(int(v) for v in rng.integers(10, 140, 3))
        _cv2.circle(img, (cx, cy), radius, colour, -1)

    img += rng.normal(0.0, noise_sigma, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def make_smooth_synthetic_image(
    height: int = 480, width: int = 640, seed: int = 11
) -> np.ndarray:
    """Diffusion-like: smooth gradients, almost no high-frequency micro-noise.

    Constructed by heavy low-pass filtering of a natural image, which is
    exactly what a denoiser does to the sensor-noise band.
    """
    import cv2

    base = make_natural_image(height, width, seed=seed)
    return cv2.GaussianBlur(base, (0, 0), sigmaX=3.0, sigmaY=3.0)


def make_moire_screen_replay(
    height: int = 480, width: int = 640, subpixel_pitch: float = 2.0
) -> np.ndarray:
    """A re-photographed display, built to actually exhibit Moire.

    A first attempt added a low-amplitude sinusoid to a NOISY natural image.
    The sinusoid's gradient contribution was swamped by the noise, so the
    Sobel gradient-magnitude coefficient of variation came out at 0.55 against
    0.52 for the natural control — no separation at all. The fixture was not
    representative of the phenomenon it was meant to stand in for.

    A real display re-photograph has three properties, all of which this builds:
      1. low base noise (the panel emits a clean, quantised image),
      2. a fine, high-contrast periodic subpixel grid,
      3. hard-edged synthetic content (text, UI rectangles, flat colour fields).

    The dominant energy therefore sits in the grid, which is precisely what
    makes the gradient distribution heavy-tailed.
    """
    import cv2

    rng = np.random.default_rng(3)
    img = make_natural_image(height, width, seed=5, noise_sigma=1.0).astype(np.float32)

    # Flat, hard-edged content: quantised colour fields and rectangles.
    img = np.round(img / 48.0) * 48.0
    for _ in range(14):
        x0, y0 = int(rng.integers(0, width - 60)), int(rng.integers(0, height - 60))
        x1, y1 = x0 + int(rng.integers(20, 90)), y0 + int(rng.integers(12, 50))
        img[y0:y1, x0:x1] = rng.integers(0, 255, 3)

    # The subpixel grid: a high-contrast, sharply-quantised RGB stripe pattern
    # at a fine pitch, which is what a camera beats against to form Moiré.
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    stripe = np.floor((xx + yy) / subpixel_pitch).astype(np.int32) % 2
    grid = (stripe * 2.0 - 1.0) * 110.0

    out = img.copy()
    out[:, :, 0] += grid
    out[:, :, 1] += grid * 0.90
    out[:, :, 2] += grid * 0.75
    out += rng.normal(0.0, 1.5, out.shape)
    return np.clip(out, 0, 255).astype(np.uint8)


@pytest.fixture
def natural_image() -> np.ndarray:
    return make_natural_image()


@pytest.fixture
def smooth_synthetic_image() -> np.ndarray:
    return make_smooth_synthetic_image()


@pytest.fixture
def moire_image() -> np.ndarray:
    return make_moire_screen_replay()


# --------------------------------------------------------------------------- #
# Image pairs (for Stage 2 CV; declared here so fixtures stay in one place)
# --------------------------------------------------------------------------- #


@pytest.fixture
def forest_pair():
    """Baseline and a rigidly-transformed progress frame.

    Used to assert the SIFT pipeline recovers a known ground-truth
    transform. Available now so Stage 2 has a contract to build against.
    """
    import cv2

    h, w = 400, 600
    rng = np.random.default_rng(42)
    baseline = np.zeros((h, w, 3), dtype=np.uint8)
    for _ in range(90):
        cx = int(rng.integers(50, w - 50))
        cy = int(rng.integers(50, h - 50))
        radius = int(rng.integers(10, 25))
        colour = (int(rng.integers(0, 40)), int(rng.integers(140, 220)), int(rng.integers(20, 80)))
        cv2.circle(baseline, (cx, cy), radius, colour, -1)
    baseline += rng.normal(0.0, 6.0, baseline.shape)
    baseline = np.clip(baseline, 0, 255).astype(np.uint8)

    angle, translate = 8.0, 15.0
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    matrix[0, 2] += translate
    progress = cv2.warpAffine(baseline, matrix, (w, h))
    return {
        "baseline": baseline,
        "progress": progress,
        "ground_truth_angle_deg": angle,
        "ground_truth_translate_px": translate,
    }
