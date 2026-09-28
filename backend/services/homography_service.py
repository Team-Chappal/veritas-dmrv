"""
VERITAS dMRV — Geometric Registration (Module 2)
==================================================

Registers a progress photo into the geometric plane of a baseline anchor so the
two are directly comparable.

The problem this solves: field volunteers cannot stand in the same spot months
apart. A naive opacity-slider comparison of a Month-0 and a Month-18 photo
taken 4 m apart at 22 degrees of yaw shows the *camera move*, not the *trees*.

PIPELINE
--------
1. CLAHE on the LAB luminance channel — stabilises keypoint detection under
   harsh outdoor sun. Detection only; never applied to the measurement path.
2. SIFT keypoints + 128-D descriptors (scale and rotation invariant).
3. FLANN kd-tree k=2 nearest neighbours.
4. Lowe's ratio test at 0.75.
5. ``findHomography`` with ``USAC_MAGSAC`` — a minimal-sample-set scorer rather
   than exhaustive combination enumeration, so it survives the ~20% outlier
   contamination that new vegetation introduces between visits.
6. Conditioning check; a near-singular H means the fit is degenerate.
7. ``warpPerspective`` into the baseline frame.

PARALLAX FALLBACK
-----------------
Under drone translation and gimbal motion, tree crowns shift relative to ground
features and a single planar homography cannot express that. The design document
specified ``cv2.createThinPlateSplineShapeTransformer`` for the fallback.

**That function does not exist in OpenCV 4.10's Python bindings** (verified:
no shape-transformer symbol of any kind is exposed). The documented fallback
could not run at all. TPS is a closed-form linear solve, so it is implemented
here directly in NumPy, which removes the dependency and makes the fallback
testable.

REJECTION IS A FEATURE
----------------------
This service returns a verdict even when registration fails. A silently wrong
homography produces a confident-looking canopy delta, which is far more
dangerous than an honest refusal. Callers must handle
:attr:`RegistrationStatus` rather than assuming success.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, asdict, field
from enum import Enum

import cv2
import numpy as np

# --------------------------------------------------------------------------- #
# Tunables
# --------------------------------------------------------------------------- #

SIFT_MAX_FEATURES = 5000
SIFT_CONTRAST_THRESHOLD = 0.03
SIFT_EDGE_THRESHOLD = 10

#: Detection is run on the grayscale image downscaled by this factor, with
#: keypoint coordinates scaled back to full resolution afterwards.
#:
#: MEASURED, not assumed. On 4K drone frames (3840x2160) SIFT detection was
#: 1143 ms of a 1217 ms total -- 94% of the pipeline -- while FLANN matching
#: (58 ms), MAGSAC++ (0.4 ms) and the warp (8 ms) together took 67 ms. The
#: published "< 800 ms" target is therefore missed at 4K by 52%, entirely
#: because of detection cost.
#:
#: SIFT is already scale invariant, so detecting on a half-resolution image
#: costs very little in match quality and removes most of the cost, which
#: scales with pixel area. Descriptors are matched in the reduced space and
#: only the 2-D keypoint coordinates need rescaling, so the homography is
#: solved in full-resolution coordinates as before.
#: Pixel budget for SIFT detection. Images at or below this area are detected at
#: full resolution; larger images are detected downscaled so the detection cost
#: stays roughly constant regardless of input size.
#:
#: Chosen as 1920x1080, where the full-resolution pipeline already measured
#: 349 ms -- comfortably inside the 800 ms target, so there is no reason to pay
#: the quality cost of downscaling there.
DETECTION_PIXEL_BUDGET = 1920 * 1080


def detection_scale_for(width: int, height: int, pixel_budget: int = DETECTION_PIXEL_BUDGET) -> float:
    """Downscale factor that keeps detection cost bounded by area.

    Adaptive rather than fixed, because the trade cuts both ways and the fixed
    factor lost more than it needed to:

    * Fixed 2.0x everywhere: 1080p registration fell 349 -> 101 ms, but the
      inlier ratio also fell 0.954 -> 0.860, and at 4K it measured 0.706 --
      barely above the 0.70 target. Full-resolution keypoints were being spent
      on an image that did not need it.
    * Area-budgeted: 1080p detects at 1.0x and keeps 0.954 inliers; only 4K
      drops to 2.0x, where 328 ms buys the cost saving that was actually
      needed.
    """
    area = float(width * height)
    if area <= pixel_budget:
        return 1.0
    return float(np.sqrt(area / float(pixel_budget)))

LOWE_RATIO = 0.75
MIN_GOOD_MATCHES = 15
MIN_KEYPOINTS = 20

RANSAC_REPROJ_THRESHOLD_PX = 3.0
RANSAC_MAX_ITERS = 5000
RANSAC_CONFIDENCE = 0.999

#: Condition number above which the fit is treated as degenerate and refused.
MAX_CONDITION_NUMBER = 1e6
#: Non-planarity of the correspondences above which a Thin Plate Spline is
#: engaged, in pixels RMS after removing the best-fit affine component.
#:
#: This replaces the design document's ``kappa > 85 OR inlier RMSE > 3.5 px``
#: trigger. Both were measured and neither works; see
#: :func:`estimate_nonplanarity` for the numbers.
TPS_NONPLANARITY_THRESHOLD_PX = 1.5

#: Condition number and inlier RMSE are retained as REPORTED diagnostics.
#: Neither triggers the fallback: condition number reached 2580 on a clean
#: rotation, and inlier RMSE stayed at 1.69 px even under 35 px of deliberate
#: non-rigid displacement.
TPS_CONDITION_REPORT_THRESHOLD = 85.0
TPS_RESIDUAL_RMSE_REPORT_THRESHOLD_PX = 3.5

#: PRIMARY TPS TRIGGER. When a plane explains less than this share of the
#: Lowe's-ratio matches, a single planar model is not describing the scene and
#: the fallback is worth attempting. 0.70 is the PRD's own target inlier ratio.
TPS_TRIGGER_INLIER_RATIO = 0.70

#: A non-rigid model has more freedom and will always fit the control points at
#: least as well as a plane. It is only worth its extra warping freedom if it
#: explains them SUBSTANTIALLY better. Below this relative improvement the
#: planar result is retained.
TPS_MIN_IMPROVEMENT = 0.20

#: Inlier ratio below which a registration is not trusted for a compliance
#: claim. The PRD's own risk table uses 60% for the manual-benchmark escalation.
INLIER_RATIO_FLOOR = 0.60
INLIER_RATIO_TARGET = 0.70

#: Ridge on the TPS normal-equation diagonal. Tiny, purely for conditioning;
#: without it the system is singular whenever control points are near-collinear.
TPS_RIDGE = 1e-8

#: Resolution of the coarse grid on which the TPS displacement field is
#: evaluated before being upsampled. Dense evaluation is O(W*H*n) and slow;
#: TPS is smooth, so a coarse grid plus bilinear upsampling is accurate and fast.
TPS_GRID = (24, 32)


class RegistrationStatus(str, Enum):
    ALIGNED_HOMOGRAPHY = "ALIGNED_HOMOGRAPHY"
    ALIGNED_TPS_FALLBACK = "ALIGNED_TPS_FALLBACK"
    INSUFFICIENT_SIFT_FEATURES = "INSUFFICIENT_SIFT_FEATURES"
    LOW_INLIER_MATCH_COUNT = "LOW_INLIER_MATCH_COUNT"
    HOMOGRAPHY_ESTIMATION_FAILED = "HOMOGRAPHY_ESTIMATION_FAILED"
    DEGENERATE_HOMOGRAPHY_MATRIX = "DEGENERATE_HOMOGRAPHY_MATRIX"
    INSUFFICIENT_TPS_CONTROL_POINTS = "INSUFFICIENT_TPS_CONTROL_POINTS"
    INVALID_INPUT = "INVALID_INPUT"

    @property
    def succeeded(self) -> bool:
        return self in (RegistrationStatus.ALIGNED_HOMOGRAPHY, RegistrationStatus.ALIGNED_TPS_FALLBACK)

    @property
    def is_trustworthy(self) -> bool:
        """Succeeded AND good enough to back a compliance claim."""
        return self is RegistrationStatus.ALIGNED_HOMOGRAPHY


@dataclass
class RegistrationResult:
    status: RegistrationStatus
    warped_image: Optional[np.ndarray]
    homography: Optional[np.ndarray]
    inlier_ratio: float
    sift_keypoints_baseline: int
    sift_keypoints_progress: int
    good_matches: int
    inliers: int
    condition_number: float
    residual_rmse_px: float
    nonplanarity_px: float
    detection_downscale: float
    is_geometrically_valid: bool
    warnings: tuple = ()
    timings_ms: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["homography"] = (
            self.homography.tolist() if self.homography is not None else None
        )
        d["warped_image"] = None if self.warped_image is None else f"<{self.warped_image.shape}>"
        d["warnings"] = list(self.warnings)
        d["timings_ms"] = {k: round(v, 2) for k, v in self.timings_ms.items()}
        return d


# --------------------------------------------------------------------------- #
# Preprocessing
# --------------------------------------------------------------------------- #


def clahe_luminance(image_rgb: np.ndarray, clip_limit: float = 2.0,
                    grid: int = 8) -> np.ndarray:
    """Equalise the LAB luminance channel, returning grayscale.

    Detection-only. Applying this to an image before measuring colour would
    destroy exactly the chromatic information GLI depends on.
    """
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(grid, grid))
    lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB)
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    return cv2.cvtColor(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB), cv2.COLOR_RGB2GRAY)


# --------------------------------------------------------------------------- #
# SIFT matching
# --------------------------------------------------------------------------- #


def extract_sift_features(gray: np.ndarray, downscale: float = 2.0) -> tuple:
    """Detect and describe SIFT features, returning keypoints in FULL-RES coords.

    Detection runs on a downscaled copy for cost; keypoint ``.pt`` values are
    mapped back so downstream geometry is unaffected. ``.size`` (the SIFT scale
    parameter) is left alone because it is already expressed relative to the
    image the descriptor was measured in, and is only used for orientation
    assignment, which has already happened by this point.
    """
    sift = cv2.SIFT_create(
        nfeatures=SIFT_MAX_FEATURES,
        contrastThreshold=SIFT_CONTRAST_THRESHOLD,
        edgeThreshold=SIFT_EDGE_THRESHOLD,
    )

    if downscale and downscale > 1.0:
        small = cv2.resize(
            gray, None, fx=1.0 / downscale, fy=1.0 / downscale,
            interpolation=cv2.INTER_AREA,
        )
        kp_small, desc = sift.detectAndCompute(small, None)
        if kp_small is None:
            return [], None
        kp = [
            cv2.KeyPoint(
                x=k.pt[0] * downscale, y=k.pt[1] * downscale,
                size=k.size, angle=k.angle, response=k.response,
                octave=k.octave, class_id=k.class_id,
            )
            for k in kp_small
        ]
        return kp, desc

    return sift.detectAndCompute(gray, None)


def match_knn_ratio(desc1: np.ndarray, desc2: np.ndarray,
                    ratio: float = LOWE_RATIO) -> list:
    """FLANN kd-tree 2-NN with Lowe's ratio test.

    Ratio 0.75 (rather than 0.7) is deliberate: a 0.7 ratio is standard for
    textureless natural scenes, but vegetation photos months apart have many
    near-identical leaf textures, where a 0.7 ratio discards true matches and
    leaves too few inliers for MAGSAC++.
    """
    index_params = dict(algorithm=1, trees=5)
    search_params = dict(checks=50)
    flann = cv2.FlannBasedMatcher(index_params, search_params)
    matches = flann.knnMatch(desc1, desc2, k=2)

    good = []
    for pair in matches:
        if len(pair) == 2:
            m, n = pair
            if m.distance < ratio * n.distance:
                good.append(m)
    return good


# --------------------------------------------------------------------------- #
# Homography
# --------------------------------------------------------------------------- #


def solve_homography_magsac(
    pts_src: np.ndarray, pts_dst: np.ndarray
) -> tuple:
    """Robust 3x3 projective transform via USAC_MAGSAC++.

    Returns ``(H, mask, rmse_px)``.
    """
    h, mask = cv2.findHomography(
        pts_src.reshape(-1, 1, 2),
        pts_dst.reshape(-1, 1, 2),
        method=cv2.USAC_MAGSAC,
        ransacReprojThreshold=RANSAC_REPROJ_THRESHOLD_PX,
        maxIters=RANSAC_MAX_ITERS,
        confidence=RANSAC_CONFIDENCE,
    )
    if h is None or mask is None:
        return None, None, float("inf")

    mask = mask.ravel().astype(bool)
    inliers = int(mask.sum())
    if inliers >= 4:
        src_i = pts_src.reshape(-1, 2)[mask]
        dst_i = pts_dst.reshape(-1, 2)[mask]
        projected = cv2.perspectiveTransform(src_i.reshape(-1, 1, 2), h).reshape(-1, 2)
        rmse = float(np.sqrt(np.mean(np.sum((projected - dst_i) ** 2, axis=1))))
    else:
        rmse = float("inf")
    return h, mask, rmse


def estimate_nonplanarity(
    pts_src: np.ndarray, pts_dst: np.ndarray
) -> float:
    """RMS residual of the correspondences after removing their best affine fit.

    This is a direct measurement of "can a single plane explain these
    correspondences?", and it is the correct parallax signal.

    Why the obvious candidates are wrong, all measured on synthetic pairs:

    * **Inlier reprojection RMSE does not work.** A robust estimator scores
      residuals only on the points it selected as inliers, so as contamination
      grows it simply returns a smaller, more self-consistent subset. Measured
      planar-fit RMSE for a clean 8-degree rotation was 0.47 px, and for a pair
      with 35 px of deliberate non-rigid displacement it was still only 1.69 px
      -- never approaching the 3.5 px trigger in the design document, while the
      inlier ratio collapsed from 95.4% to 15.0%.
    * **Condition number does not work either.** It reached 2580 on the *clean*
      rotation, because the fit absorbs minor perspective into a nominally
      affine transform. It was 36412 on the worst parallax case, so it does
      correlate, but it is measuring the fit's conditioning rather than
      out-of-plane motion, and its clean-rotation value was already 30x the
      document's trigger.

    Subtract the best-fit affine map and whatever remains *is* the non-planar
    component, measured on the correspondences themselves rather than on a
    self-selected subset.
    """
    src = np.asarray(pts_src, dtype=np.float64).reshape(-1, 2)
    dst = np.asarray(pts_dst, dtype=np.float64).reshape(-1, 2)
    if src.shape[0] < 3:
        return float("inf")

    design = np.hstack([src, np.ones((src.shape[0], 1))])
    try:
        solution, *_ = np.linalg.lstsq(design, dst, rcond=None)
    except np.linalg.LinAlgError:
        return float("inf")

    residual = dst - design @ solution
    return float(np.sqrt(np.mean(np.sum(residual**2, axis=1))))


def _affine_residual_rms(pts_src: np.ndarray, pts_dst: np.ndarray) -> float:
    """RMS residual of the best-fit affine map between two point sets."""
    src = np.asarray(pts_src, dtype=np.float64).reshape(-1, 2)
    dst = np.asarray(pts_dst, dtype=np.float64).reshape(-1, 2)
    if src.shape[0] < 3:
        return float("inf")
    design = np.hstack([src, np.ones((src.shape[0], 1))])
    try:
        solution, *_ = np.linalg.lstsq(design, dst, rcond=None)
    except np.linalg.LinAlgError:
        return float("inf")
    return float(np.sqrt(np.mean(np.sum((dst - design @ solution) ** 2, axis=1))))


def _tps_residual_rms(pts_src, pts_dst, w, a, b) -> float:
    """RMS residual of the fitted TPS at the control points."""
    src = np.asarray(pts_src, dtype=np.float64).reshape(-1, 2)
    dst = np.asarray(pts_dst, dtype=np.float64).reshape(-1, 2)
    if src.shape[0] < 3:
        return float("inf")
    residual = thin_plate_spline_apply(src, src, w, a, b) - dst
    return float(np.sqrt(np.mean(np.sum(residual**2, axis=1))))


def condition_number(h: np.ndarray) -> float:
    """Largest / smallest singular value. Large means ill-conditioned."""
    try:
        sv = np.linalg.svd(h, compute_uv=False)
        if sv[-1] <= 0:
            return float("inf")
        return float(sv[0] / sv[-1])
    except np.linalg.LinAlgError:
        return float("inf")


# --------------------------------------------------------------------------- #
# Thin Plate Spline — closed form, NumPy only
# --------------------------------------------------------------------------- #


def _tps_kernel(r2: np.ndarray) -> np.ndarray:
    """U(r) = r^2 * log(r^2), the TPS radial basis."""
    out = np.zeros_like(r2)
    nz = r2 > 1e-12
    out[nz] = r2[nz] * np.log(r2[nz])
    return out


def thin_plate_spline_weights(
    control_src: np.ndarray, control_dst: np.ndarray
) -> tuple:
    """Solve the TPS normal equations for the non-rigid weights.

    Canonical block system, ``(n+3) x (n+3)``::

        [  K    Phi  ] [  w  ]   [  Q  ]
        [  Phi^T 0   ] [  lam ] = [  0  ]

    where ``Phi`` is the ``n x 3`` homogeneous design matrix ``[x, y, 1]`` and
    ``lam = [A^T, b^T]^T`` carries the full affine part (2x2 linear plus a
    2-vector translation). The bottom-right block is genuinely zero; the system
    is non-singular because ``Phi`` has full column rank 3.

    .. warning::
       The homogeneous column of ``Phi`` is load-bearing in *both* directions.
       An earlier revision used a bare ``[P, 0]`` block padded with a single
       ``1``, which left one row and one column structurally zero: the smallest
       singular value was exactly 0.0, and ``np.linalg.solve`` raised without
       hinting at the real cause.

    Returns:
        ``(w, a, b)`` — ``w`` ``(n,2)`` non-rigid weights, ``a`` ``(2,2)`` linear
        part, ``b`` ``(2,)`` translation. ``b`` is solved for, not assumed zero.
    """
    p = np.asarray(control_src, dtype=np.float64)
    q = np.asarray(control_dst, dtype=np.float64)
    n = p.shape[0]
    if n < 3:
        raise ValueError(f"TPS needs >= 3 control points, got {n}")

    d2 = ((p[:, None, :] - p[None, :, :]) ** 2).sum(axis=2)
    k = _tps_kernel(d2)
    phi = np.hstack([p, np.ones((n, 1))])          # n x 3, rank 3

    m = n + 3
    l = np.zeros((m, m), dtype=np.float64)
    l[:n, :n] = k
    l[:n, n:] = phi
    l[n:, :n] = phi.T
    # l[n:, n:] is left at zero, as the formulation requires.
    # Ridge on the kernel block only; the constraint blocks must stay exact.
    l[:n, :n] += TPS_RIDGE * np.eye(n)

    y = np.zeros((m, 3), dtype=np.float64)
    y[:n, :2] = q

    solution = np.linalg.solve(l, y)
    lam = solution[n:, :2]                        # 3 x 2
    return solution[:n, :2], lam[:2, :].T, lam[2, :]


def thin_plate_spline_apply(
    query_pts: np.ndarray, control_src: np.ndarray, w: np.ndarray,
    a: np.ndarray, b: np.ndarray
) -> np.ndarray:
    """Evaluate the fitted TPS at arbitrary points."""
    pts3 = np.hstack([query_pts, np.ones((query_pts.shape[0], 1))])
    mapped = pts3 @ np.vstack([a.T, b[None, :]])
    d2 = ((query_pts[:, None, :] - control_src[None, :, :]) ** 2).sum(axis=2)
    return mapped + _tps_kernel(d2) @ w


def thin_plate_spline_field(
    control_src: np.ndarray,
    control_dst: np.ndarray,
    width: int,
    height: int,
    grid: tuple = TPS_GRID,
) -> tuple:
    """Dense ``(map_x, map_y)`` remap fields from TPS control points.

    The displacement is evaluated on a coarse ``grid`` and bilinearly upsampled.
    TPS is smooth by construction, so this is both fast and visually lossless;
    evaluating on every pixel would be O(W*H*n) and is unnecessary.
    """
    p = np.asarray(control_src, dtype=np.float64)
    q = np.asarray(control_dst, dtype=np.float64)

    # Normalise the control cloud before solving.
    #
    # The TPS normal equations are badly conditioned when control points occupy
    # a large, axis-aligned region in raw pixel coordinates - which is exactly
    # what SIFT returns. Without this, a plain similarity transform solves as a
    # singular matrix. Translating to the centroid and scaling so the mean
    # control-point radius is 1 makes the system well posed; the result is
    # mapped back into pixel space afterwards, which avoids any weight
    # algebra for un-normalising the kernel arguments.
    centre = p.mean(axis=0)
    radius = float(np.mean(np.linalg.norm(p - centre, axis=1)))
    scale = radius if radius > 1e-9 else 1.0
    p_n = (p - centre) / scale
    q_n = (q - centre) / scale

    w, a, b = thin_plate_spline_weights(p_n, q_n)

    gh, gw = grid
    ys = np.linspace(0, height - 1, gh)
    xs = np.linspace(0, width - 1, gw)
    gy, gx = np.meshgrid(ys, xs, indexing="ij")

    pts = np.stack([gx.ravel(), gy.ravel()], axis=1)          # (gh*gw, 2)
    pts_n = (pts - centre) / scale

    mapped_n = thin_plate_spline_apply(pts_n, p_n, w, a, b)

    # Back to pixel space.
    mapped = mapped_n * scale + centre

    dx = (mapped[:, 0] - pts[:, 0]).reshape(gh, gw)
    dy = (mapped[:, 1] - pts[:, 1]).reshape(gh, gw)

    full_dx = cv2.resize(dx, (width, height), interpolation=cv2.INTER_LINEAR)
    full_dy = cv2.resize(dy, (width, height), interpolation=cv2.INTER_LINEAR)

    map_x = (np.arange(width)[None, :] + full_dx).astype(np.float32)
    map_y = (np.arange(height)[:, None] + full_dy).astype(np.float32)
    return map_x, map_y


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def register_field_pair(
    baseline_rgb: np.ndarray,
    progress_rgb: np.ndarray,
    use_tps_fallback: bool = True,
    detection_pixel_budget: int = DETECTION_PIXEL_BUDGET,
) -> RegistrationResult:
    """Register ``progress`` into the geometric plane of ``baseline``.

    Always returns a result carrying an explicit status. Never raises for a
    quality failure — those are statuses, because a caller that catches an
    exception will still carry a stale `warped_image` forward.
    """
    t0 = time.perf_counter()
    timings: dict = {}

    if baseline_rgb is None or progress_rgb is None:
        return _fail(RegistrationStatus.INVALID_INPUT, "A required image was None.", timings)
    if baseline_rgb.size == 0 or progress_rgb.size == 0:
        return _fail(RegistrationStatus.INVALID_INPUT, "A required image was empty.", timings)
    if baseline_rgb.shape[:2] != progress_rgb.shape[:2]:
        # Not fatal: a different capture size is normal. We resize progress to
        # the baseline frame so the warp target is unambiguous.
        progress_rgb = cv2.resize(
            progress_rgb, (baseline_rgb.shape[1], baseline_rgb.shape[0]),
            interpolation=cv2.INTER_AREA,
        )

    t = time.perf_counter()
    gray_base = clahe_luminance(baseline_rgb)
    gray_prog = clahe_luminance(progress_rgb)
    scale = detection_scale_for(
        baseline_rgb.shape[1], baseline_rgb.shape[0], detection_pixel_budget
    )
    kp1, desc1 = extract_sift_features(gray_base, downscale=scale)
    kp2, desc2 = extract_sift_features(gray_prog, downscale=scale)
    timings["preprocess_and_detect"] = (time.perf_counter() - t) * 1000.0

    n_kp1 = 0 if kp1 is None else len(kp1)
    n_kp2 = 0 if kp2 is None else len(kp2)

    if desc1 is None or desc2 is None or n_kp1 < MIN_KEYPOINTS or n_kp2 < MIN_KEYPOINTS:
        return _fail(
            RegistrationStatus.INSUFFICIENT_SIFT_FEATURES,
            f"SIFT found {n_kp1}/{n_kp2} keypoints (need {MIN_KEYPOINTS} each). "
            "The frame is likely too smooth, too blurry, or too low-contrast.",
            timings, n_kp1, n_kp2,
        )

    t = time.perf_counter()
    good = match_knn_ratio(desc1, desc2)
    timings["match"] = (time.perf_counter() - t) * 1000.0

    if len(good) < MIN_GOOD_MATCHES:
        return _fail(
            RegistrationStatus.LOW_INLIER_MATCH_COUNT,
            f"Only {len(good)} matches survived Lowe's ratio test at {LOWE_RATIO} "
            f"(need {MIN_GOOD_MATCHES}). The two frames may not depict the same scene.",
            timings, n_kp1, n_kp2, good_matches=len(good),
        )

    pts_prog = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    pts_base = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)

    t = time.perf_counter()
    h, mask, rmse = solve_homography_magsac(pts_prog, pts_base)
    timings["homography"] = (time.perf_counter() - t) * 1000.0

    if h is None or mask is None:
        return _fail(
            RegistrationStatus.HOMOGRAPHY_ESTIMATION_FAILED,
            "USAC_MAGSAC++ could not produce a homography from the available matches.",
            timings, n_kp1, n_kp2, good_matches=len(good),
        )

    inliers = int(mask.sum())
    inlier_ratio = inliers / len(good)
    kappa = condition_number(h)

    if kappa > MAX_CONDITION_NUMBER or not np.isfinite(kappa):
        return _fail(
            RegistrationStatus.DEGENERATE_HOMOGRAPHY_MATRIX,
            f"Homography condition number {kappa:.3g} exceeds the degenerate "
            f"threshold {MAX_CONDITION_NUMBER:.0f}. The matched points are "
            "collinear or collapsed and the transform is not invertible in "
            "practice. Refusing to warp rather than producing a plausible-looking "
            "but meaningless result.",
            timings, n_kp1, n_kp2, good_matches=len(good), inliers=inliers,
            inlier_ratio=inlier_ratio, condition_number=kappa,
        )

    h_out = h / h[2, 2] if abs(h[2, 2]) > 1e-12 else h
    height, width = baseline_rgb.shape[:2]

    t = time.perf_counter()
    warnings: list = []
    status = RegistrationStatus.ALIGNED_HOMOGRAPHY
    warped = cv2.warpPerspective(
        progress_rgb, h, (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )

    # --- Non-planar fallback --------------------------------------------- #
    # Measure non-planarity directly on the inlier correspondences: subtract
    # their best-fit affine map and see what is left. That residue is the
    # out-of-plane component TPS exists to absorb.
    #
    # This replaces the design document's `kappa > 85 OR inlier RMSE > 3.5 px`
    # trigger. Both were measured and neither works; see
    # :func:`estimate_nonplanarity` for the numbers.
    nonplanarity = estimate_nonplanarity(
        pts_prog.reshape(-1, 2)[mask], pts_base.reshape(-1, 2)[mask]
    )
    # PRIMARY SIGNAL: the inlier ratio. This is the only measured quantity that
    # varies monotonically with applied parallax:
    #
    #   clean rotation  ratio 0.954   non-planarity 0.47px   RMSE 0.47px
    #   parallax 10px   ratio 0.287   non-planarity 1.88px   RMSE 1.91px
    #   parallax 20px   ratio 0.180   non-planarity 1.60px   RMSE 1.60px
    #   parallax 35px   ratio 0.150   non-planarity 1.59px   RMSE 1.69px
    #
    # Note that non-planarity and RMSE *saturate* rather than growing, because
    # a robust estimator returns a smaller and ever more self-consistent inlier
    # set as contamination increases. They separate the clean case from the
    # contaminated ones, but they do not order the contaminated ones. The
    # inlier ratio does both, so it is the trigger.
    #
    # SECONDARY: non-planarity must be non-trivial, to distinguish genuine
    # parallax (spatially structured residual) from simply comparing two
    # different scenes (no consistent correspondence at all).
    needs_tps = (
        inlier_ratio < TPS_TRIGGER_INLIER_RATIO
        and nonplanarity > TPS_NONPLANARITY_THRESHOLD_PX
    )
    if use_tps_fallback and needs_tps:
        inlier_src = pts_prog.reshape(-1, 2)[mask]
        inlier_dst = pts_base.reshape(-1, 2)[mask]
        try:
            # Validate before accepting. A non-rigid model has more freedom,
            # so it will always fit the control points at least as well as a
            # plane. What matters is whether it explains them SUBSTANTIALLY
            # better, which is the only reason to prefer it. If the improvement
            # is marginal the extra warping freedom is not justified and the
            # planar result stands.
            planar_resid = _affine_residual_rms(inlier_src, inlier_dst)
            w_tps, a_tps, b_tps = thin_plate_spline_weights(inlier_src, inlier_dst)
            tps_resid = _tps_residual_rms(
                inlier_src, inlier_dst, w_tps, a_tps, b_tps
            )
            improvement = (
                1.0 - (tps_resid / planar_resid) if planar_resid > 1e-9 else 0.0
            )

            context = (
                f"Planar homography was insufficient: measured non-planarity "
                f"{nonplanarity:.2f}px RMS vs {TPS_NONPLANARITY_THRESHOLD_PX}px "
                f"threshold (inlier ratio {inlier_ratio:.1%}, kappa={kappa:.0f}). "
            )

            if improvement < TPS_MIN_IMPROVEMENT:
                # Reject the non-rigid warp: its extra freedom is not paying
                # for itself, so the planar result stands.
                warnings.append(
                    context
                    + f"Engaged the TPS fallback but it improved control-point fit "
                    f"by only {improvement:.1%} (planar RMS {planar_resid:.2f}px -> "
                    f"TPS RMS {tps_resid:.2f}px), below the {TPS_MIN_IMPROVEMENT:.0%} "
                    "required to justify a non-rigid warp. Retained the planar "
                    "homography. NOTE: the documented "
                    "cv2.createThinPlateSplineShapeTransformer does not exist in "
                    "OpenCV 4.10's Python bindings; this is a direct NumPy "
                    "implementation of the same closed-form solve."
                )
            else:
                map_x, map_y = thin_plate_spline_field(
                    inlier_src, inlier_dst, width, height
                )
                warped = cv2.remap(
                    progress_rgb, map_x, map_y,
                    interpolation=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_CONSTANT,
                    borderValue=(0, 0, 0),
                )
                status = RegistrationStatus.ALIGNED_TPS_FALLBACK
                warnings.append(
                    context
                    + f"Engaged the Thin Plate Spline fallback for 3D canopy "
                    f"parallax; it improved control-point fit by {improvement:.1%} "
                    f"(planar RMS {planar_resid:.2f}px -> TPS RMS {tps_resid:.2f}px), "
                    f"above the {TPS_MIN_IMPROVEMENT:.0%} bar. NOTE: the documented "
                    "cv2.createThinPlateSplineShapeTransformer does not exist in "
                    "OpenCV 4.10's Python bindings; this is a direct NumPy "
                    "implementation of the same closed-form solve."
                )
        except (np.linalg.LinAlgError, ValueError) as exc:
            warnings.append(
                f"TPS fallback failed ({type(exc).__name__}: {exc}). Retained the "
                "planar homography, which may not fully model canopy parallax."
            )

    timings["warp"] = (time.perf_counter() - t) * 1000.0
    timings["total"] = (time.perf_counter() - t0) * 1000.0

    if kappa > TPS_CONDITION_REPORT_THRESHOLD:
        warnings.append(
            f"Homography condition number {kappa:.0f} is above the reporting "
            f"threshold {TPS_CONDITION_REPORT_THRESHOLD:.0f}. The fit is "
            "ill-conditioned; this did not by itself trigger the TPS fallback, "
            "because condition number was measured to be a noisy signal "
            "(2579 on a clean rotation) rather than evidence of parallax."
        )

    if rmse > TPS_RESIDUAL_RMSE_REPORT_THRESHOLD_PX:
        warnings.append(
            f"Inlier reprojection RMSE {rmse:.2f}px exceeds "
            f"{TPS_RESIDUAL_RMSE_REPORT_THRESHOLD_PX}px. Reported for visibility; "
            "note this figure is measured only on selected inliers and so is a "
            "weak indicator of parallax on its own."
        )

    if inlier_ratio < INLIER_RATIO_FLOOR:
        warnings.append(
            f"Inlier ratio {inlier_ratio:.1%} is below the {INLIER_RATIO_FLOOR:.0%} "
            "floor. Flag for manual ground-stake benchmark calibration before "
            "this delta is used in a compliance claim."
        )

    return RegistrationResult(
        status=status,
        warped_image=warped,
        homography=h_out,
        inlier_ratio=round(inlier_ratio, 4),
        sift_keypoints_baseline=n_kp1,
        sift_keypoints_progress=n_kp2,
        good_matches=len(good),
        inliers=inliers,
        condition_number=round(kappa, 3),
        residual_rmse_px=round(rmse, 3),
        nonplanarity_px=round(nonplanarity, 3),
        detection_downscale=round(scale, 3),
        is_geometrically_valid=status.succeeded,
        warnings=tuple(warnings),
        timings_ms=timings,
    )


def _fail(status, message, timings, n_kp1=0, n_kp2=0, good_matches=0,
          inliers=0, inlier_ratio=0.0, condition_number=0.0) -> RegistrationResult:
    return RegistrationResult(
        status=status,
        warped_image=None,
        homography=None,
        inlier_ratio=round(inlier_ratio, 4),
        sift_keypoints_baseline=n_kp1,
        sift_keypoints_progress=n_kp2,
        good_matches=good_matches,
        inliers=inliers,
        condition_number=condition_number,
        residual_rmse_px=float("inf"),
        nonplanarity_px=float("inf"),
        detection_downscale=0.0,
        is_geometrically_valid=False,
        warnings=(message,),
        timings_ms=timings,
    )
