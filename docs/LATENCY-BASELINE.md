# VERITAS dMRV — Measured Latency Baseline

**Generated:** 2026-09-28T03:45:17+00:00 · regenerate with `make bench`

> This file replaces the specification suite's unbaselined latency claims. Every
> number here was measured on a named machine, at a stated resolution, over
> 12 repetitions with the first discarded as warm-up (OpenCV's lazy
> dispatch makes run 1 unrepresentative).

## Machine

| | |
| :--- | :--- |
| Platform | `macOS-26.6.2-arm64-arm-64bit-Mach-O` |
| CPU | `Apple M3` |
| Logical cores | 8 |
| OpenCV threads | 8 |
| Python / OpenCV / NumPy | 3.13.9 / 4.10.0 / 2.1.1 |
| Resolution under test | **1920x1080** (2.07 MP) |

## Results

| Stage | Median | p95 | Min | Max | Spec claim | Verdict |
| :--- | --: | --: | --: | --: | :--- | :--- |
| Solar ephemeris + shadow coherence | 1.11 ms | 1.18 ms | 1.05 ms | 1.18 ms | < 150 ms | **MET** |
| SIFT + MAGSAC++ registration (wall) | 338.81 ms | 344.41 ms | 335.47 ms | 344.41 ms | < 800 ms | **MET** |
| GLI + Otsu canopy delta | 9.73 ms | 10.44 ms | 9.29 ms | 10.44 ms | — | — |
| **End to end (register + measure)** | **348.54 ms** | — | — | — | — | — |

### Registration stage breakdown

| Stage | Median | p95 |
| :--- | --: | --: |
| CLAHE + SIFT detection | 299.3 ms | 304.96 ms |
| FLANN match + Lowe ratio | 35.8 ms | 37.2 ms |
| USAC_MAGSAC++ homography | 0.4 ms | 0.5 ms |
| Perspective warp | 2.3 ms | 3.01 ms |

Registration quality on the benchmark pair: inlier ratio **0.935**
(ALIGNED_HOMOGRAPHY).

## Resolution sweep

The published target is a single number; the platform has to work across
resolutions a field team actually produces, from phone uploads to 4K drone
transects. SIFT detection cost scales with pixel area, so it is bounded by an
area budget rather than a fixed downscale factor.

| Resolution | Detection scale | Registration (median) | End to end | Inlier ratio | vs 800 ms target |
| :--- | --: | --: | --: | --: | :--- |
| 540p (960x540, 0.52 MP) | 1.00x | 115.24 ms | 125.32 ms | 0.922 | MET |
| 1080p (1920x1080, 2.07 MP) | 1.00x | 341.23 ms | 351.26 ms | 0.936 | MET |
| 4K (3840x2160, 8.29 MP) | 2.00x | 329.23 ms | 339.6 ms | 0.707 | MET |
| 8K (7680x4320, 33.18 MP) | 4.00x | 444.89 ms | 454.58 ms | 0.545 | MET |

**Reading this honestly.** Latency is bounded across the whole range, but match
quality is not free. At 8K the area budget's 4x downscale drops the inlier ratio
to about 0.54, below the 0.60 trust floor — the registration is *fast and not
trustworthy*, and the pipeline says so through ``inlier_ratio`` and a warning
rather than returning a confident answer built on a degraded keypoint set. The
correct operator response is to raise ``DETECTION_PIXEL_BUDGET`` and accept the
latency, or capture at a lower resolution. That trade is visible and
controllable; a silently degraded registration would not be.

## What this does and does not license

**Does:** on this machine at 1920x1080, the pipeline meets both
published targets with substantial headroom. The `< 150 ms` and `< 800 ms`
figures in `01-PRD` NFR-1 are achievable and now mean something specific.

**Does not:** a baseline on an M-series laptop says nothing about a 2 GHz field
laptop, and the trial-level server this would run on in production. Real drone
imagery is 4K, roughly 8× the pixels measured here, and SIFT cost scales with
image area — so the honest projection is that the registration figure is
resolution-bound, not compute-bound, and must be re-measured at 4K before being
quoted for 4K.

**Rule adopted:** any latency claim in `docs/` must cite a measured run from
this file. `scripts/verify_docs.py` enforces it. An unbaselined "< 800 ms" in a
spec is a defect, in the same class as an unverified coefficient.

---

## Frontend at 500 assets (measured 2026-09-29)

The table above is the **backend** pipeline. This is the browser, which had never
been measured at the scale the rubric names: the shipped fixture is 64 assets, on
purpose, so all 175 e2e specs exercised one-eighth the target. Measured by
`frontend/e2e/scale-500.spec.ts`, which mocks the live route with a real
500-asset payload.

| Metric | Value |
| :-- | --: |
| Wall clock to 500 cards rendered | **303 ms** |
| First contentful paint | 96 ms |
| DOMContentLoaded | 122 ms |
| **Longest main-thread task** | **52 ms** |
| **Cumulative layout shift** | **0** (exactly, as the criterion requires) |
| DOM nodes | 13,976 |
| JS heap | 22 MB |
| Filter click → DOM settled (500 rows) | **162 ms** |

Machine: the same as above (Apple M3, 8 threads, macOS 26.6.2).

**The 52 ms longest task is the number to watch.** It clears the 300 ms budget the
spec enforces, and it exceeds the 50 ms frame budget, so at 500 rows there is
already a dropped frame during the initial paint. It is not visible as a stutter
at this size; it would be at 2,000. The honest reading is that 500 is comfortable
and the next order of magnitude is not, and nothing here establishes where the
knee is.

**The fixture stays at 64.** Shipping 520 rows would bloat the bundle for a page
that displays a page of results. The scale is reached by mocking the live route
instead, which exercises the same code path production uses.
