"""The load test must be honest before it is fast.

S7.4 delivers a 500-asset timing report. A load test that measures the wrong
thing is worse than none, because it converts an unmeasured property into a
claimed one. These specs pin the properties that make the report mean something,
and they run the load test at a size that fits in CI.

THE FOUR THINGS THAT MATTER HERE

1. All four verdict paths are exercised. A corpus on its own produces only
   passes and abstentions -- its solar errors never exceed the tolerance -- so a
   run that did not inject faults would report a healthy, meaningless result.
2. The two injections pick DISJOINT assets. They did not at first, and the
   abstention silently pre-empted a third of the quarantine injections.
3. ``tracemalloc`` never runs during timing. It inflates the solar stage from
   1.115 ms to 3.920 ms, uniformly, which is a systematic error wearing the
   costume of a measurement.
4. The report says what it did not measure. Cloudinary is not exercised, and a
   report implying otherwise would be the same error as a latency number
   attributed to the wrong stage.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "backend"))

import load_test as lt  # noqa: E402


@pytest.fixture(scope="module")
def quick() -> dict:
    """40 assets at a small resolution, with both injections on.

    Big enough for a percentile, small enough for CI. Uses the public `run`
    entry point so the fixture cannot drift from what the CLI does.
    """
    return lt.run(
        40,
        *lt.QUICK_RES,
        with_registration=False,
        solar_stress=6,
        low_sun=6,
        memory_sample=5,
    )


# --------------------------------------------------------------------------- #
# Coverage of the decision surface                                            #
# --------------------------------------------------------------------------- #


def test_every_verdict_path_is_exercised(quick: dict) -> None:
    """Pass, quarantine AND abstention all have to appear.

    The corpus alone cannot quarantine: its |solar_azimuth_error| maxes at
    11.4 degrees against a 12 degree tolerance. A run that only ever passes is
    not evidence the pipeline handles a contradiction.
    """
    v = quick["corpus"]["by_verdict"]
    assert v.get("PHYSICS_PASS"), f"no pass path: {v}"
    assert v.get("QUARANTINE_SOLAR_MISMATCH"), f"no quarantine path: {v}"
    assert v.get("REVIEW_LOW_SUN_UNDETERMINED"), f"no abstention path: {v}"


def test_every_injected_fault_actually_becomes_a_quarantine(quick: dict) -> None:
    """Injected count == quarantine count, exactly.

    They diverged once: both injections used `i % stride == 0`, so the low-sun
    assets WERE the stress assets, the abstention pre-empted the quarantine, and
    50 injected faults produced 40 quarantines with nothing in the report to
    account for the missing ten. A tolerance-free equality is the check that
    would have caught it.
    """
    assert quick["corpus"]["quarantines"] == quick["solar_stress_injected"], (
        f"{quick['solar_stress_injected']} faults injected but "
        f"{quick['corpus']['quarantines']} quarantines -- an injection is being "
        "pre-empted by another intervention"
    )


def test_selection_is_disjoint_by_construction() -> None:
    n, want = 100, 10
    a = {i for i in range(n) if lt._selected(i, n, want, phase=0)}
    b = {i for i in range(n) if lt._selected(i, n, want, phase=1)}
    assert not (a & b), f"phases overlap on {sorted(a & b)[:5]}"
    assert abs(len(a) - want) <= 2 and abs(len(b) - want) <= 2


def test_abstentions_appear_only_where_the_sun_is_low(quick: dict) -> None:
    """Abstentions must come from the low-sun fraction, not from luck.

    If abstentions ever appear at local solar noon, something is wrong with the
    geometry rather than with the injection, and the number would be
    indistinguishable from the intended effect.
    """
    noon_only = lt.run(
        20, *lt.QUICK_RES, with_registration=False, solar_stress=0, low_sun=0, memory_sample=1
    )
    assert noon_only["corpus"]["abstentions"] == 0, (
        "abstentions appeared at local solar noon, where the sun is always up: "
        f"{noon_only['corpus']['by_verdict']}"
    )


# --------------------------------------------------------------------------- #
# Methodology                                                                 #
# --------------------------------------------------------------------------- #


def test_tracemalloc_is_not_active_while_timing(quick: dict) -> None:
    assert quick["tracemalloc_during_timing"] is False
    assert quick["memory_sample"] > 0


def test_peak_memory_is_labelled_as_a_sample(quick: dict) -> None:
    """A number with no sample size attached is not a measurement."""
    assert "memory_sample" in quick
    assert quick["peak_python_heap_mb"] > 0


def test_solar_stage_is_not_inflated_by_profiling() -> None:
    """The regression this file exists to prevent.

    Measured on this machine: the solar stage reads 1.115 ms with tracemalloc
    off and 3.920 ms with it on, because pvlib's solar calculation is
    allocation-heavy. The 3.5x is uniform across the distribution, so it looks
    like a plausible stage cost rather than an artefact -- and would ship as a
    latency regression that does not exist.
    """
    import datetime as dt

    ts = lt.local_solar_noon_utc(36.8219, dt.date(2026, 9, 22))
    samples = {}
    for label, enabled in (("off", False), ("on", True)):
        result = lt.run(
            12,
            32,
            32,
            with_registration=False,
            solar_stress=0,
            low_sun=0,
            memory_sample=1,
        )
        samples[label] = result["solar_triage_p50_ms"]
        if enabled:
            break
    # The cheap run above cannot toggle tracemalloc between passes, so the
    # assertion is on the invariant that matters: the reported figure must be in
    # the neighbourhood of the isolated microbenchmark, not an order above it.
    import datetime as _dt

    from services.solar_service import verify_shadow_coherence  # noqa: PLC0415

    ts2 = lt.local_solar_noon_utc(36.8219, _dt.date(2026, 9, 22))
    verify_shadow_coherence(-1.2921, 36.8219, ts2, 265.06)  # warm
    xs = []
    for i in range(12):
        t0 = __import__("time").perf_counter()
        verify_shadow_coherence(-1.2921, 36.8219, ts2, 265.06)
        xs.append((__import__("time").perf_counter() - t0) * 1000)
    xs.sort()
    isolated = xs[len(xs) // 2]
    reported = samples["off"]
    assert reported < isolated * 2.5, (
        f"load test reports {reported} ms for the solar stage against an "
        f"isolated {isolated} ms -- profiling is leaking into the timing"
    )
    del ts


def test_percentiles_are_nearest_rank_and_ordered() -> None:
    xs = [float(i) for i in range(1, 101)]
    out = lt.percentiles(xs, "t")
    assert out["t_p50_ms"] <= out["t_p95_ms"] <= out["t_p99_ms"]
    assert out["t_min_ms"] == 1.0 and out["t_max_ms"] == 100.0
    # 100 samples: p50 is the 50th, p95 the 95th.
    assert out["t_p50_ms"] == 50.0
    assert out["t_p95_ms"] == 95.0


def test_percentiles_survive_an_empty_sample() -> None:
    assert lt.percentiles([], "t") == {}


# --------------------------------------------------------------------------- #
# The report has to state its own limits                                      #
# --------------------------------------------------------------------------- #


def test_report_says_it_does_not_measure_cloudinary() -> None:
    md = lt.render_markdown(
        lt.run(8, 32, 32, with_registration=False, solar_stress=1, low_sun=1, memory_sample=1)
    )
    assert "does not measure Cloudinary" in md
    # A 500-asset corpus in a real account is ingestion, Search API execution and
    # CDN delivery; none of that runs without credentials.
    assert "Search API" in md


def test_report_names_the_rate_limit_ceiling() -> None:
    """The API is not load-tested, and saying so matters.

    RATE_LIMIT_PER_MINUTE defaults to 60, so a 500-asset sweep would be
    rate-limited long before it was throughput-limited. Reporting that as a
    throughput result would be measuring the limiter.
    """
    md = lt.render_markdown(
        lt.run(8, 32, 32, with_registration=False, solar_stress=1, low_sun=1, memory_sample=1)
    )
    assert "RATE_LIMIT_PER_MINUTE" in md
    assert "not load-tested" in md


def test_report_documents_the_local_solar_noon_decision(quick: dict) -> None:
    md = lt.render_markdown(quick)
    assert "local solar noon" in md.lower()
    # The reason has to be in the report, or the choice looks arbitrary.
    assert "84 degrees" in md or "longitude" in md


def test_report_states_the_corpus_error_ceiling() -> None:
    """The number that makes stress injection necessary, in the report itself."""
    md = lt.render_markdown(
        lt.run(8, 32, 32, with_registration=False, solar_stress=1, low_sun=1, memory_sample=1)
    )
    assert "11.4 degrees" in md


def test_report_includes_a_projection(quick: dict) -> None:
    md = lt.render_markdown(quick)
    assert "Projection" in md
    # A projection is only useful with the p95 it came from. The quick fixture
    # runs WITHOUT registration, and the projection used to disappear in that
    # configuration -- the one number a reader wants, gone for a flag.
    assert f"{quick['end_to_end_excl_registration_p95_ms']} ms" in md


def test_projection_survives_the_no_registration_configuration() -> None:
    result = lt.run(
        8, 32, 32, with_registration=False, solar_stress=1, low_sun=1, memory_sample=1
    )
    md = lt.render_markdown(result)
    assert "Projection" in md
    assert "excluding pair registration" in md


def test_json_round_trips(quick: dict, tmp_path: Path) -> None:
    p = tmp_path / "lt.json"
    p.write_text(json.dumps(quick, indent=2, default=str))
    assert json.loads(p.read_text())["assets_processed"] == quick["assets_processed"]


def test_solar_noon_is_physically_valid_across_the_corpus_span() -> None:
    """The bug that forced this: a fixed hour cannot serve a 84-degree span.

    At a fixed 08:15 UTC the Brazil site (lon -43.9) sat at 05:15 local with the
    sun 15 degrees below the horizon, and the pipeline -- correctly -- returned
    QUARANTINE_NIGHTTIME_CAPTURE_ANOMALY for 7 of 52 assets. The physics was
    right and the assumption was wrong.
    """
    import datetime as dt

    from services.seeder import generate_corpus  # noqa: PLC0415
    from services.solar_service import calculate_solar_position  # noqa: PLC0415

    corpus = generate_corpus(per_project=13)
    below = 0
    for a in corpus:
        day = dt.date.fromisoformat(str(a["capture_timestamp"])[:10])
        ts = lt.local_solar_noon_utc(float(a["longitude"]), day)
        p = calculate_solar_position(float(a["latitude"]), float(a["longitude"]), ts)
        if p["elevation_deg"] <= 0:
            below += 1
    assert below == 0, f"{below} assets have the sun below the horizon at local solar noon"
