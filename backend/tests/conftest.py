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
    """A plausible natural photograph: banded structure + sensor shot noise.

    High-frequency content comes from the Poisson-ish Gaussian noise, which is
    what a real CMOS sensor contributes and what a diffusion model lacks.
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)

    r = 90.0 + 40.0 * np.sin(xx / 37.0) * np.cos(yy / 53.0)
    g = 110.0 + 55.0 * np.sin((xx + yy) / 44.0)
    b = 75.0 + 30.0 * np.cos(yy / 29.0)

    img = np.stack([r, g, b], axis=2)
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
    blurred = cv2.GaussianBlur(base, (0, 0), sigmaX=3.0, sigmaY=3.0)
    return blurred


def make_moire_screen_replay(
    height: int = 480, width: int = 640, subpixel_pitch: float = 3.0
) -> np.ndarray:
    """A re-photographed display: content plus a periodic RGB subpixel grid.

    The interference between the display's physical grid and the camera
    sensor's sampling grid is what the Moiré detector keys on.
    """
    rng = np.random.default_rng(3)
    content = make_natural_image(height, width, seed=5, noise_sigma=4.0).astype(np.float32)

    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    phase = (xx + yy) / subpixel_pitch
    # A strong periodic ripple at the subpixel pitch, beating with the sensor.
    interference = 34.0 * np.cos(2.0 * np.pi * phase)

    out = content.copy()
    out[:, :, 0] += interference
    out[:, :, 1] += interference * 0.85
    out[:, :, 2] += interference * 0.70
    out += rng.normal(0.0, 2.0, out.shape)
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
