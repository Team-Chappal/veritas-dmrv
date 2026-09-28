"""
Shared pytest fixtures.

Everything here is generated deterministically. No test may depend on a
downloaded asset or a Cloudinary credential: a test that needs the network is
a test that will fail on stage.
"""

from __future__ import annotations

import os
from typing import Callable

# Rate limiting is configured at 60/min, which a suite making hundreds of
# requests would blow through -- and a global counter shared across tests would
# make unrelated tests fail by execution order. Raise the ceiling before any
# project import reads settings; enforcement is proven at a low limit in
# test_rate_limit.py instead.
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "100000")

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


def make_soil_scene(
    height: int = 480,
    width: int = 640,
    canopy_fraction: float = 0.15,
    seed: int = 1,
    brightness: float = 1.0,
) -> np.ndarray:
    """A soil background with elliptical green canopy patches.

    Built with genuine chromatic separation (brown soil, green foliage) rather
    than blended colours, because the whole point is to give GLI and Otsu a
    bimodal distribution to actually split.
    """
    import cv2 as _cv2

    rng = np.random.default_rng(seed)
    img = np.zeros((height, width, 3), dtype=np.float32)
    img[:] = np.array([128.0, 96.0, 68.0]) + rng.normal(0.0, 9.0, (height, width, 1))

    target = canopy_fraction * height * width
    drawn = 0.0
    guard = 0
    while drawn < target and guard < 4000:
        guard += 1
        cx, cy = int(rng.integers(0, width)), int(rng.integers(0, height))
        ax, ay = int(rng.integers(10, 34)), int(rng.integers(8, 28))
        angle = float(rng.uniform(0.0, 180.0))
        _cv2.ellipse(img, (cx, cy), (ax, ay), angle, 0, 360, (58.0, 150.0, 52.0), -1)
        drawn += np.pi * ax * ay

    img += rng.normal(0.0, 4.0, img.shape)
    img = np.clip(img, 0, 255)
    if brightness != 1.0:
        img = np.clip(img * brightness, 0, 255)
    return img.astype(np.uint8)


def make_cluttered_scene(
    height: int = 400, width: int = 600, seed: int = 5
) -> np.ndarray:
    """A textured scene with strong repeatable structure, for SIFT.

    Needs many distinct corners: SIFT is meaningless on a flat field, and the
    earlier green-circles fixture produced keypoints that only matched because
    the circles were drawn identically in both frames.
    """
    import cv2 as _cv2

    rng = np.random.default_rng(seed)
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = (120, 104, 88)

    for _ in range(220):
        cx, cy = int(rng.integers(0, width)), int(rng.integers(0, height))
        radius = int(rng.integers(4, 26))
        colour = tuple(int(v) for v in rng.integers(0, 255, 3))
        _cv2.circle(img, (cx, cy), radius, colour, -1)
    for _ in range(40):
        x0, y0 = int(rng.integers(0, width - 40)), int(rng.integers(0, height - 40))
        _cv2.rectangle(
            img, (x0, y0), (x0 + int(rng.integers(15, 70)), y0 + int(rng.integers(10, 45))),
            tuple(int(v) for v in rng.integers(0, 255, 3)), -1,
        )
    noisy = img.astype(np.int16) + rng.normal(0.0, 7.0, img.shape).astype(np.int16)
    return np.clip(noisy, 0, 255).astype(np.uint8)


def apply_transform(
    image: np.ndarray, angle_deg: float = 0.0, translate_px: float = 0.0,
    scale: float = 1.0, output_shape: tuple | None = None,
) -> np.ndarray:
    """Apply a known similarity transform, for ground-truth registration tests."""
    import cv2 as _cv2

    h, w = image.shape[:2]
    out_h, out_w = output_shape if output_shape else (h, w)
    m = _cv2.getRotationMatrix2D((w / 2, h / 2), angle_deg, scale)
    m[0, 2] += translate_px
    m[1, 2] += translate_px * 0.4
    return _cv2.warpAffine(image, m, (out_w, out_h), borderMode=_cv2.BORDER_REFLECT)


@pytest.fixture
def soil_scene():
    return make_soil_scene()


@pytest.fixture
def cluttered_scene():
    return make_cluttered_scene()


@pytest.fixture
def forest_pair():
    """A cluttered baseline and a known-transformed version of itself.

    Provides ground truth (angle, translation) so the SIFT pipeline can be
    scored against a known answer rather than merely "it returned something".
    """
    baseline = make_cluttered_scene(seed=5)
    angle, translate = 8.0, 15.0
    progress = apply_transform(baseline, angle_deg=angle, translate_px=translate)
    return {
        "baseline": baseline,
        "progress": progress,
        "ground_truth_angle_deg": angle,
        "ground_truth_translate_px": translate,
    }


@pytest.fixture
def canopy_growth_pair():
    """A dimmer visit with genuinely more canopy — the measurement case."""
    baseline = make_soil_scene(canopy_fraction=0.12, seed=3)
    progress = make_soil_scene(canopy_fraction=0.20, seed=3, brightness=0.65)
    return {"baseline": baseline, "progress": progress}


# --------------------------------------------------------------------------- #
# Authenticated test client (S5.8)
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def auth_headers() -> dict:
    """A real, verified triage token as default request headers.

    Deliberately a genuine token rather than a mock: the suite exercises the
    same verification path a field client would, so an auth regression fails
    here instead of on deployment. Tests that assert 401/403 behaviour build
    their own clients WITHOUT these headers.
    """
    from core.auth import issue_token
    from core.config import get_settings

    token = issue_token("triage", subject="pytest@veritas.local", settings=get_settings())
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def token_for() -> Callable[[str], dict]:
    """Build auth headers for a named role: ``token_for("vvb")``."""
    from core.auth import issue_token
    from core.config import get_settings

    def _make(role: str) -> dict:
        token = issue_token(role, subject=f"pytest-{role}@veritas.local", settings=get_settings())
        return {"Authorization": f"Bearer {token}"}

    return _make
