"""S7.4 — 500-asset scale load test with a timing report.

WHAT THIS MEASURES, AND WHAT IT DOES NOT

This exercises the LOCAL numerical pipeline over a realistic 500-asset corpus:
solar verification, forgery detection, canopy quantification, perceptual hashing,
and — optionally — full-resolution pair registration, which is the dominant cost.

It does NOT measure Cloudinary. A 500-asset corpus in a Cloudinary account is
ingestion, Search API execution and CDN delivery, and none of that runs here
without credentials and a real account. Any report that implied otherwise would
be the same class of error as a latency number attributed to the wrong stage, so
the scope is stated in the output rather than left to the reader.

The asset manifest comes from ``services.seeder.generate_corpus``, which is
already deterministic and already used to seed the live account -- so this
measures the same corpus shape production would have, rather than an array of
noise.

WHY p95 AND p99, AND WHY THE REPORT NAMES THE MACHINE

Per-asset latency is already baselined in docs/LATENCY-BASELINE.md. What a scale
test adds is throughput, tail behaviour under sustained load, and peak memory.
The p95 is what S5 gates on, so it is reported; p99 is reported because at 500
assets the tail is where a demo falls over, and a mean would hide it.

Numbers from an unnamed machine are not a baseline, so the report carries the
platform, CPU, core count and the OpenCV thread setting. OpenCV's thread count
is stated because it is the single biggest factor in the registration number and
it is not the default on every machine.

Usage:
    make load-test                     # 500 assets, full stages
    python scripts/load_test.py --quick        # 50 assets, for CI
    python scripts/load_test.py --no-registration
    python scripts/load_test.py --out docs/LOAD-TEST.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from services.seeder import generate_corpus  # noqa: E402

DEFAULT_ASSETS = 500
QUICK_ASSETS = 50

# Injected solar error for the stress fraction, in degrees. Well outside the
# 12 degree tolerance so the quarantine branch is actually entered.
STRESS_ERROR_DEG = 35.0

# Hours before local solar noon for the low-sun fraction. Four hours puts the sun
# near the horizon at mid latitudes, which is where the product's ABSTENTION
# lives -- and that abstention is the central claim of the whole interface, so
# it deserves to be exercised at scale rather than only in a unit test.
LOW_SUN_HOURS_BEFORE_NOON = 4.0

# Peak memory is measured over a smaller sample in its own pass. All 500 assets
# would triple the run time for a number that plateaus well before that, and the
# sample size is stated in the report rather than implied.
MEMORY_SAMPLE = 50

# Which resolution the pipeline runs at. 1920x1080 is the figure
# LATENCY-BASELINE.md was measured at, so these numbers are comparable to it.
# At 500 assets this is the difference between a two-minute test and a
# fifteen-minute one, so the choice is a flag rather than a constant.
FULL_RES = (1920, 1080)
QUICK_RES = (640, 360)


def percentiles(samples: list[float], prefix: str) -> dict:
    """p50 / p95 / p99, plus min and max.

    Nearest-rank rather than interpolated, because with 500 samples the
    interpolated p95 is a number between two real observations, and this report
    is meant to be quotable.
    """
    if not samples:
        return {}
    ordered = sorted(samples)

    def at(q: float) -> float:
        idx = min(len(ordered) - 1, max(0, int(round(q * len(ordered))) - 1))
        return ordered[idx]

    return {
        f"{prefix}_p50_ms": round(at(0.50), 3),
        f"{prefix}_p95_ms": round(at(0.95), 3),
        f"{prefix}_p99_ms": round(at(0.99), 3),
        f"{prefix}_min_ms": round(ordered[0], 3),
        f"{prefix}_max_ms": round(ordered[-1], 3),
    }


def machine_profile() -> dict:
    return {
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "machine": platform.machine(),
        "python": platform.python_version(),
        "opencv": cv2.__version__,
        "numpy": np.__version__,
        "cpu_count_logical": os.cpu_count(),
        "opencv_threads": cv2.getNumThreads(),
    }


def make_scene(h: int, w: int, seed: int) -> np.ndarray:
    """A deterministic, non-degenerate scene.

    Non-degenerate matters: SIFT needs texture to find keypoints, so a flat
    image returns almost none and the registration stage looks artificially
    fast. A load test that is fast because its input is empty is not a load test.
    """
    rng = np.random.default_rng(seed)
    base = rng.integers(40, 210, size=(h, w, 3), dtype=np.uint16)
    # Structure: a few soft blobs, so there is something to key on and something
    # for the homography to align.
    yy, xx = np.mgrid[0:h, 0:w]
    for _ in range(14):
        cy, cx = rng.integers(0, h), rng.integers(0, w)
        r = rng.integers(min(h, w) // 12 + 5, min(h, w) // 5 + 10)
        blob = np.exp(-(((yy - cy) ** 2 + (xx - cx) ** 2) / (2.0 * r * r)))
        base = np.clip(base + (blob[..., None] * rng.integers(40, 120)), 0, 255)
    grain = rng.integers(0, 26, size=(h, w, 3), dtype=np.uint16)
    return np.clip(base + grain, 0, 255).astype(np.uint8)


def warp(scene: np.ndarray, angle_deg: float, translate_px: float) -> np.ndarray:
    h, w = scene.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle_deg, 1.0)
    m[0, 2] += translate_px
    return cv2.warpAffine(scene, m, (w, h), borderMode=cv2.BORDER_REFLECT)


def _selected(i: int, n: int, want: int, phase: int) -> bool:
    """Whether asset ``i`` is one of roughly ``want`` evenly spaced assets.

    ``phase`` offsets the selection so two interventions pick DISJOINT sets. They
    did not at first: both used ``i % stride == 0``, so the low-sun assets were
    exactly the stress assets, the abstention pre-empted the quarantine, and 50
    injected faults produced only 40 quarantines with nothing in the report to
    explain the missing ten.
    """
    if want <= 0:
        return False
    stride = max(1, n // want)
    return i % stride == (phase * (stride // 2)) % stride


def measure_peak_memory(height: int, width: int, seed: int, sample: int = MEMORY_SAMPLE) -> float:
    """Peak Python heap over ``sample`` assets, in a pass of its own.

    Separate from the timed pass on purpose. tracemalloc instruments every
    allocation, and running it alongside the timings made the solar stage read
    3.920 ms instead of 1.115 ms -- uniform across the distribution, so it was a
    systematic error rather than a slow tail, and it would have shipped as a
    latency regression that did not exist.

    The number is a sample, not the whole run, and the report says so.
    """
    from services.canopy_service import compute_gli
    from services.dedup_service import compute_phash
    from services.forgery_service import detect_synthetic_media
    from services.homography_service import register_field_pair

    tracemalloc.start()
    for i in range(max(1, sample)):
        scene = make_scene(height, width, seed=seed + i)
        detect_synthetic_media(scene)
        compute_gli(scene)
        compute_phash(scene)
        register_field_pair(scene, warp(scene, 5.0, 10.0))
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return round(peak / 1e6, 1)


def local_solar_noon_utc(longitude: float, day: dt.date) -> dt.datetime:
    """The UTC instant of local solar noon at ``longitude``.

    NECESSARY, NOT COSMETIC. The corpus stores a capture DATE and no time, so
    any fixed hour of day is wrong for some sites. The corpus spans longitudes
    -43.9 to +39.9 — 84 degrees, about 5.6 hours of solar time — and at a fixed
    08:15 UTC the Brazil site sits at 05:15 local with the sun 15 degrees BELOW
    the horizon, which the pipeline correctly returned as
    QUARANTINE_NIGHTTIME_CAPTURE_ANOMALY for 7 of 52 assets. The physics was
    right; the assumption was wrong.

    Local solar noon is also the best-posed moment for shadow geometry: the sun
    is at its highest, so the shadow is shortest and its direction is best
    determined. The tolerance argument the product makes is strongest there.
    """
    return dt.datetime(
        day.year, day.month, day.day, tzinfo=dt.timezone.utc
    ) + dt.timedelta(hours=12.0 - longitude / 15.0)


def run(
    assets: int,
    width: int,
    height: int,
    with_registration: bool,
    seed: int = 20260922,
    solar_stress: int = 0,
    low_sun: int = 0,
    memory_sample: int = MEMORY_SAMPLE,
) -> dict:
    from services.canopy_service import compute_gli
    from services.dedup_service import compute_phash
    from services.forgery_service import detect_synthetic_media
    from services.solar_service import expected_shadow_azimuth, verify_shadow_coherence

    if with_registration:
        from services.homography_service import register_field_pair

    corpus = generate_corpus(per_project=max(1, -(-assets // 4)), seed=seed)[:assets]

    solar_ms: list[float] = []
    forgery_ms: list[float] = []
    canopy_ms: list[float] = []
    hash_ms: list[float] = []
    reg_wall_ms: list[float] = []

    decisions: dict[str, int] = {}
    abstentions = 0
    quarantines = 0
    injected = 0
    low_sun_applied = 0
    contradictions = 0

    # Warm-up: OpenCV dispatches lazily, so the first asset is not representative
    # and including it would make the p50 look worse than the pipeline really is.
    warm = make_scene(height, width, seed=1)
    warm_ts = local_solar_noon_utc(36.8219, dt.date(2026, 9, 22))
    verify_shadow_coherence(-1.2921, 36.8219, warm_ts, expected_shadow_azimuth(85.0))
    detect_synthetic_media(warm)
    compute_gli(warm)
    compute_phash(warm)
    if with_registration:
        register_field_pair(warm, warp(warm, 6.0, 10.0))

    # NOT tracemalloc. Profiling allocations and timing in the same pass
    # invalidates the timings: tracemalloc instrumented every allocation and
    # inflated the solar stage from 1.115 ms to 3.920 ms -- a 3.5x factor,
    # measured, uniform across the distribution, which is exactly the shape of a
    # systematic error rather than a tail. Every per-stage number in the first
    # report was inflated by roughly that factor. Peak memory is now measured in
    # a separate, smaller pass; see measure_peak_memory().
    started = time.perf_counter()

    for i, asset in enumerate(corpus):
        scene = make_scene(height, width, seed=seed + i)
        lat = float(asset.get("latitude", 0.0))
        lon = float(asset.get("longitude", 0.0))
        day = dt.date.fromisoformat(str(asset["capture_timestamp"])[:10])
        ts = local_solar_noon_utc(lon, day)

        # Low-sun fraction: pulled back towards the horizon so the abstention
        # branch is loaded. At local solar noon the sun is always up, so without
        # this the run would report zero abstentions -- which would be a true
        # observation of a configuration that cannot test the product's most
        # important behaviour.
        if low_sun and _selected(i, len(corpus), low_sun, phase=1):
            ts -= dt.timedelta(hours=LOW_SUN_HOURS_BEFORE_NOON)
            low_sun_applied += 1

        # --- 1. JEV System-1 triage: the solar + shadow argument ---------------
        # The corpus supplies the angular error, so the observed shadow is
        # DERIVED from the geometry rather than guessed. Calling
        # verify_shadow_coherence with no observed azimuth would return
        # REVIEW_INSUFFICIENT_INPUT for all 500 assets, which would time the
        # abstention path and report it as if it were the verdict path.
        #
        # STRESS INJECTION. The corpus's |solar_azimuth_error| maxes out at
        # 11.4 degrees against a 12 degree tolerance, so on its own this corpus
        # can NEVER quarantine: every asset passes or abstains, and the 47
        # QUARANTINE_FRAUD decisions it carries come from forgery and provenance
        # signals, not from solar geometry. A load test that therefore only ever
        # measures the pass path is a load test of the pass path, so a
        # configurable fraction gets a large injected error to load the
        # quarantine branch. Injected faults are counted separately and never
        # presented as corpus findings.
        error = abs(float(asset.get("solar_azimuth_error", 0.0)))
        if solar_stress and _selected(i, len(corpus), solar_stress, phase=0):
            error = STRESS_ERROR_DEG
            injected += 1

        # The caller's own ephemeris call, to derive the observed shadow, is
        # setup rather than pipeline work. Timing it alongside the verification
        # double-counted the ephemeris and made this stage read ~9 ms against the
        # 1.11 ms that LATENCY-BASELINE.md measures for the same function --
        # two numbers for one thing, neither usable.
        sun_az = _sun_azimuth(lat, lon, ts)
        observed = (expected_shadow_azimuth(sun_az) + error) % 360.0

        t = time.perf_counter()
        verdict = verify_shadow_coherence(lat, lon, ts, observed)
        solar_ms.append((time.perf_counter() - t) * 1000.0)

        name = getattr(verdict.verdict, "value", str(verdict.verdict))
        decisions[name] = decisions.get(name, 0) + 1
        if "UNDETERMINED" in name or "INSUFFICIENT" in name:
            abstentions += 1
        if "QUARANTINE" in name and "NIGHTTIME" not in name:
            quarantines += 1
            if asset.get("c2pa_provenance") == "C2PA_VERIFIED":
                contradictions += 1

        # --- 2. Forgery signals ------------------------------------------------
        t = time.perf_counter()
        detect_synthetic_media(scene)
        forgery_ms.append((time.perf_counter() - t) * 1000.0)

        # --- 3. Canopy quantification -----------------------------------------
        t = time.perf_counter()
        compute_gli(scene)
        canopy_ms.append((time.perf_counter() - t) * 1000.0)

        # --- 4. Perceptual hash -------------------------------------------------
        t = time.perf_counter()
        compute_phash(scene)
        hash_ms.append((time.perf_counter() - t) * 1000.0)

        # --- 5. Pairwise registration: the dominant cost ------------------------
        if with_registration:
            t = time.perf_counter()
            register_field_pair(scene, warp(scene, 5.0 + (i % 5), 8.0 + (i % 7)))
            reg_wall_ms.append((time.perf_counter() - t) * 1000.0)

    wall = time.perf_counter() - started

    out: dict = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "assets_processed": len(corpus),
        "resolution": f"{width}x{height}",
        "megapixels": round(width * height / 1e6, 2),
        "registration_enabled": with_registration,
        "wall_seconds": round(wall, 2),
        "assets_per_second": round(len(corpus) / wall, 2) if wall else 0.0,
        "peak_python_heap_mb": measure_peak_memory(height, width, seed, sample=memory_sample),
        "capture_time": "local solar noon, derived from longitude",
        "memory_sample": memory_sample,
        "tracemalloc_during_timing": False,
        "solar_stress_injected": injected,
        "low_sun_applied": low_sun_applied,
        "machine": machine_profile(),
        "corpus": {
            "projects": len({a["esg_project_id"] for a in corpus}),
            "epochs": len({a["milestone_phase"] for a in corpus}),
            "by_verdict": decisions,
            "abstentions": abstentions,
            "quarantines": quarantines,
            "quarantined_with_c2pa_verified": contradictions,
        },
    }
    out.update(percentiles(solar_ms, "solar_triage"))
    out.update(percentiles(forgery_ms, "forgery_detection"))
    out.update(percentiles(canopy_ms, "canopy"))
    out.update(percentiles(hash_ms, "perceptual_hash"))
    if reg_wall_ms:
        out.update(percentiles(reg_wall_ms, "registration_wall"))

    # The per-asset total is reported WHATEVER the configuration. It used to
    # require registration to be on, so `--no-registration` silently dropped the
    # projection -- the one number a reader actually wants, and the one that
    # answers "how long does 500 assets take".
    n_cheap = min(len(solar_ms), len(forgery_ms), len(canopy_ms), len(hash_ms))
    if n_cheap:
        out.update(
            percentiles(
                [
                    solar_ms[i] + forgery_ms[i] + canopy_ms[i] + hash_ms[i]
                    for i in range(n_cheap)
                ],
                "end_to_end_excl_registration",
            )
        )
    if reg_wall_ms and len(reg_wall_ms) == n_cheap:
        out.update(
            percentiles(
                [solar_ms[i] + forgery_ms[i] + canopy_ms[i] + hash_ms[i] + reg_wall_ms[i]
                 for i in range(n_cheap)],
                "end_to_end",
            )
        )
    return out


def _sun_azimuth(lat: float, lon: float, ts: dt.datetime) -> float:
    from services.solar_service import calculate_solar_position

    try:
        return float(calculate_solar_position(lat, lon, ts)["azimuth_deg"])
    except ValueError:
        # Out of range for the ephemeris, or pvlib unavailable. The triage call
        # below will abstain on its own, so there is nothing to recover here --
        # returning a fixed bearing keeps the loop going and the abstention is
        # counted rather than hidden.
        return 0.0


def render_markdown(r: dict) -> str:
    m = r["machine"]
    lines = [
        "# VERITAS dMRV — 500-Asset Scale Load Test",
        "",
        f"**Generated:** {r['generated_utc']} · regenerate with `make load-test`",
        "",
        "## What this measures, and what it does not",
        "",
        "This exercises the **local numerical pipeline** over a realistic asset",
        "corpus: solar verification, forgery detection, canopy quantification,",
        "perceptual hashing and pairwise registration.",
        "",
        "**It does not measure Cloudinary.** A 500-asset corpus in a Cloudinary",
        "account is ingestion, Search API execution and CDN delivery, and none of",
        "that runs here without credentials and a real account. `seeder` — the same",
        "module that seeds the live account — generated the manifest, so the corpus",
        "shape matches production; the transport does not.",
        "",
        "## Machine",
        "",
        "| | |",
        "| :--- | :--- |",
        f"| Platform | `{m['platform']}` |",
        f"| CPU | `{m['processor']}` |",
        f"| Logical cores | {m['cpu_count_logical']} |",
        f"| **OpenCV threads** | {m['opencv_threads']} |",
        f"| Python / OpenCV / NumPy | {m['python']} / {m['opencv']} / {m['numpy']} |",
        f"| Resolution under test | **{r['resolution']}** ({r['megapixels']} MP) |",
        "",
        "OpenCV's thread count is stated because it is the single largest factor in",
        "the registration figure and it is not the default on every machine.",
        "",
        "## Throughput",
        "",
        "| | |",
        "| :--- | ---: |",
        f"| Assets processed | {r['assets_processed']} |",
        f"| Registration enabled | {r['registration_enabled']} |",
        f"| Wall clock | {r['wall_seconds']} s |",
        f"| **Throughput** | **{r['assets_per_second']} assets/s** |",
        f"| Peak Python heap | {r['peak_python_heap_mb']} MB (over a {r['memory_sample']}-asset sample, measured in a separate pass) |",
        "",
        "## Per-asset latency",
        "",
        "| Stage | p50 | p95 | p99 | max |",
        "| :--- | --: | --: | --: | --: |",
    ]
    stages = [
        ("Solar triage", "solar_triage"),
        ("Forgery detection", "forgery_detection"),
        ("Canopy", "canopy"),
        ("Perceptual hash", "perceptual_hash"),
        ("Registration (wall)", "registration_wall"),
        ("End to end, ex-registration", "end_to_end_excl_registration"),
        ("**End to end**", "end_to_end"),
    ]
    for label, key in stages:
        if f"{key}_p50_ms" in r:
            lines.append(
                f"| {label} | {r[f'{key}_p50_ms']} ms | {r[f'{key}_p95_ms']} ms "
                f"| {r[f'{key}_p99_ms']} ms | {r[f'{key}_max_ms']} ms |"
            )

    c = r["corpus"]
    lines += [
        "",
        "## Corpus",
        "",
        "Generated by `services.seeder.generate_corpus` — the same module that",
        f"seeds the live account, deterministic, seed 20260922. **{c['projects']}",
        f"projects across {c['epochs']} epochs.**",
        "",
        f"**Capture time: {r['capture_time']}.** The corpus stores a capture DATE",
        "and no time, so a fixed hour of day is wrong for some sites: the corpus",
        "spans 84 degrees of longitude, and at a fixed 08:15 UTC the Brazil site",
        "sits at 05:15 local with the sun 15 degrees below the horizon. Local",
        "solar noon is both physically valid everywhere in the corpus and the",
        "best-posed moment for shadow geometry, since the sun is highest and the",
        "shadow shortest.",
        "",
        "| Verdict | Count |",
        "| :--- | ---: |",
    ]
    for k, v in sorted(c["by_verdict"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| `{k}` | {v} |")
    lines += [
        "",
        f"**Abstentions: {c['abstentions']}.** Assets where the physics declined to",
        "answer. Counted, because a corpus that produced only verdicts would mean",
        "the abstention path was never loaded.",
        "",
        f"**Quarantines: {c['quarantines']}**, of which {r['solar_stress_injected']}",
        "come from injected faults (see below) and",
        f"{c['quarantines'] - r['solar_stress_injected']} from the corpus itself.",
        "",
        f"**Low-sun captures: {r['low_sun_applied']}**",
        f"({LOW_SUN_HOURS_BEFORE_NOON:g} h before local solar noon), placed there",
        "specifically to load the abstention branch. At local solar noon the sun",
        "is always above the horizon, so a run without this would report **zero**",
        "abstentions — a true observation of a configuration that cannot test the",
        "product's most important behaviour.",
        "",
        f"**{c['quarantined_with_c2pa_verified']}** quarantined assets are flagged",
        "`C2PA_VERIFIED`, which is internally contradictory. Reported rather than",
        "hidden: a scale test whose own data is incoherent proves nothing.",
    ]
    if r["solar_stress_injected"]:
        lines += [
            "",
            "## Why stress faults are injected",
            "",
            f"The corpus's `|solar_azimuth_error|` **maxes out at 11.4 degrees**",
            "against a 12 degree tolerance, so on its own this corpus can never",
            "quarantine: every asset passes or abstains. Its 47 `QUARANTINE_FRAUD`",
            "decisions come from forgery and provenance signals, not from solar",
            "geometry — the solar path is one input to a composite decision, not the",
            "whole of it.",
            "",
            "A scale test that therefore only ever measures the pass path is a scale",
            "test of the pass path, so a configurable fraction gets a large injected",
            f"error ({STRESS_ERROR_DEG} degrees) to load the quarantine branch. Those",
            "assets are counted separately and never presented as corpus findings.",
        ]
    # The projection uses whichever per-asset total exists, so `--no-registration`
    # still answers "how long do 500 assets take" instead of omitting it.
    total_key = "end_to_end" if "end_to_end_p95_ms" in r else "end_to_end_excl_registration"
    if f"{total_key}_p95_ms" in r:
        p95 = r[f"{total_key}_p95_ms"]
        basis = "including pair registration" if total_key == "end_to_end" else "excluding pair registration"
        lines += [
            "",
            "## Projection",
            "",
            f"At **{p95} ms** p95 per asset ({basis}), 500 assets is",
            f"**{p95 * 500 / 1000.0:.0f} s** of wall clock on this machine, and the",
            f"measured rate was {r['assets_per_second']} assets/s.",
            "That is the number to argue with, not the mean: a demo that survives a",
            "median can still fall over on the tail.",
        ]
    lines += [
        "",
        "## Honest limits",
        "",
        "- **Single process, single machine.** No network, no CDN, no database.",
        "  Container-level and multi-process behaviour is unmeasured.",
        "- **Peak memory is a sample, not the full run**, measured in a separate",
        "  pass. It is a separate pass because `tracemalloc` instruments every",
        "  allocation, and running it alongside the timings inflated the solar",
        "  stage from 1.115 ms to 3.920 ms — a 3.5x factor, uniform across the",
        "  distribution, which is the shape of a systematic error rather than a",
        "  tail. Profiling and timing in one pass would have shipped a latency",
        "  regression that did not exist.",
        "- **The API is not load-tested here.** `mock_server` route latency under",
        "  concurrency is a separate question, and the default",
        "  `RATE_LIMIT_PER_MINUTE=60` means a 500-asset sweep would be rate-limited",
        "  long before it was throughput-limited. Reporting it as a throughput",
        "  result would be measuring the limiter, not the server.",
        "- **Scenes are synthetic.** Deterministic and textured enough for SIFT to",
        "  find keypoints, but not photographic. Registration cost on real imagery",
        "  is not established by this.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--assets", type=int, default=DEFAULT_ASSETS)
    ap.add_argument("--quick", action="store_true", help="50 assets at 640x360, for CI")
    ap.add_argument("--no-registration", action="store_true")
    ap.add_argument(
        "--low-sun",
        type=int,
        default=0,
        help="capture roughly this many assets near the horizon, so the "
        "ABSTENTION branch is loaded (local solar noon can never trigger it)",
    )
    ap.add_argument(
        "--solar-stress",
        type=int,
        default=0,
        help="inject a large solar error into roughly this many assets, so the "
        "quarantine branch is loaded rather than only the pass path",
    )
    ap.add_argument("--out", type=Path, default=REPO / "docs" / "LOAD-TEST.md")
    ap.add_argument("--json-out", type=Path, default=REPO / "docs" / "load-test.json")
    args = ap.parse_args()

    width, height = QUICK_RES if args.quick else FULL_RES
    n = QUICK_ASSETS if args.quick else args.assets

    print(
        f"load test: {n} assets at {width}x{height}, "
        f"registration={'off' if args.no_registration else 'on'}, "
        f"solar_stress={args.solar_stress}, low_sun={args.low_sun}",
        file=sys.stderr,
    )
    result = run(
        n,
        width,
        height,
        with_registration=not args.no_registration,
        solar_stress=args.solar_stress,
        low_sun=args.low_sun,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_markdown(result))
    args.json_out.write_text(json.dumps(result, indent=2, default=str))
    print(f"wrote {args.out} and {args.json_out}", file=sys.stderr)

    e2e_p95 = result.get("end_to_end_p95_ms")
    if e2e_p95:
        print(
            f"throughput {result['assets_per_second']} assets/s, "
            f"end-to-end p95 {e2e_p95} ms, "
            f"500 assets ~= {e2e_p95 * 500 / 1000:.0f} s",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
