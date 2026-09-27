#!/usr/bin/env python
"""
Generate VERITAS solar-forensic test fixtures FROM pvlib GROUND TRUTH.

WHY THIS SCRIPT EXISTS
----------------------
docs/12-TESTING-AND-QA-STRATEGY.md contained four hand-written solar azimuth
vectors. ALL FOUR were outside their own stated tolerances, and one was
physically impossible:

    Nairobi  2026-09-22T08:15:30Z   documented  94.2   actual  83.6   (10.6 deg off)
    Nairobi  2026-09-22T13:30:00Z   documented 268.4   actual 271.4   ( 3.0 deg off)
    Ankara   2026-06-21T10:00:00Z   documented 138.5   actual 188.1   (49.6 deg off)
    Berlin   2026-12-21T11:00:00Z   documented 173.1   actual 179.0   ( 5.9 deg off)

The Ankara case is the clearest proof: at 10:00 UTC on the June solstice,
solar noon at 32.85E is 09:48 UTC, so the sun is 12 minutes PAST the meridian
and its azimuth MUST be ~188 deg. A documented 138.5 deg cannot occur.

Worse, the flagship "legitimate photo" demo fixture cleared the 12 deg fraud
threshold by only 1.1 deg of margin. On stage, one refactor away from
disqualifying a genuine planting.

This script makes that class of error impossible to reintroduce:

  * Genuine fixtures SET the observed shadow to the pvlib-computed expected
    shadow plus small realistic terrain-slope jitter, so the error is small by
    construction rather than by hand-tuning.
  * Fraud fixtures are built by claiming the WRONG TIME for a real capture, so
    the impossibility is geometric rather than asserted.
  * ``expected_shadow_azimuth_deg`` and ``calculated_sun_azimuth_deg`` are never
    typed by a human. They are emitted by pvlib.
  * The generator REFUSES to write if any genuine fixture's margin is below
    REQUIRED_FIXTURE_MARGIN_DEG.

Usage:
    python scripts/gen_solar_fixtures.py            # write fixtures
    python scripts/gen_solar_fixtures.py --check     # verify committed file
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from services.solar_service import (  # noqa: E402
    REQUIRED_FIXTURE_MARGIN_DEG,
    SHADOW_COHERENCE_TOLERANCE_DEG,
    calculate_solar_position,
    expected_shadow_azimuth,
    verify_shadow_coherence,
)

FIXTURE_PATH = REPO / "backend" / "tests" / "fixtures" / "solar_vectors.json"

#: Plausible small azimuth error from terrain slope and sensor noise on a real
#: capture, in degrees. Kept small so genuine fixtures keep a wide margin.
GENUINE_JITTER_DEG = 2.0


def _genuine(
    scenario_id: str,
    narrative: str,
    latitude: float,
    longitude: float,
    timestamp_iso: str,
    jitter_deg: float = GENUINE_JITTER_DEG,
    expected_verdict: str = "PHYSICS_PASS",
    project_id: str = "KEN-GEN",
) -> dict:
    """A physically coherent capture. Expected shadow is computed, not typed."""
    ts = dt.datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
    pos = calculate_solar_position(latitude, longitude, ts)
    expected = expected_shadow_azimuth(pos["azimuth_deg"])
    # Nudge away from due north/south where azimuth error amplifies, so the
    # jitter is expressed in the direction the detector actually measures.
    observed = (expected + jitter_deg) % 360.0

    result = verify_shadow_coherence(latitude, longitude, ts, observed)
    return {
        "scenario_id": scenario_id,
        "kind": "genuine",
        "narrative": narrative,
        "project_id": project_id,
        "latitude": latitude,
        "longitude": longitude,
        "timestamp_utc": timestamp_iso,
        "observed_shadow_azimuth_deg": round(observed, 2),
        "pvlib_sun_azimuth_deg": round(pos["azimuth_deg"], 2),
        "pvlib_sun_elevation_deg": round(pos["elevation_deg"], 2),
        "expected_shadow_azimuth_deg": round(expected, 2),
        "angular_error_deg": result.angular_error_deg,
        "margin_to_tolerance_deg": result.margin_to_tolerance_deg,
        "expected_verdict": expected_verdict,
        "ground_truth_source": "pvlib.solarposition.get_solarposition",
    }


def _fraud(
    scenario_id: str,
    narrative: str,
    latitude: float,
    longitude: float,
    true_capture_iso: str,
    claimed_capture_iso: str,
    project_id: str = "KEN-FRAUD",
) -> dict:
    """A real capture with a falsified claimed time.

    The photo's shadow is genuine. The lie is in the timestamp, which is the
    attack that matters: it lets a nursery photo masquerade as a remote
    planting at a favourable hour.
    """
    true_ts = dt.datetime.fromisoformat(true_capture_iso.replace("Z", "+00:00"))
    claimed_ts = dt.datetime.fromisoformat(claimed_capture_iso.replace("Z", "+00:00"))

    true_pos = calculate_solar_position(latitude, longitude, true_ts)
    true_shadow = expected_shadow_azimuth(true_pos["azimuth_deg"])
    observed = true_shadow % 360.0

    claimed_pos = calculate_solar_position(latitude, longitude, claimed_ts)
    claimed_expected_shadow = expected_shadow_azimuth(claimed_pos["azimuth_deg"])

    result = verify_shadow_coherence(latitude, longitude, claimed_ts, observed)
    return {
        "scenario_id": scenario_id,
        "kind": "fraud",
        "narrative": narrative,
        "project_id": project_id,
        "latitude": latitude,
        "longitude": longitude,
        "timestamp_utc": claimed_capture_iso,
        "true_capture_timestamp_utc": true_capture_iso,
        "observed_shadow_azimuth_deg": round(observed, 2),
        "pvlib_sun_azimuth_deg": round(claimed_pos["azimuth_deg"], 2),
        "pvlib_sun_elevation_deg": round(claimed_pos["elevation_deg"], 2),
        "expected_shadow_azimuth_deg": round(claimed_expected_shadow, 2),
        "angular_error_deg": result.angular_error_deg,
        "margin_to_tolerance_deg": result.margin_to_tolerance_deg,
        "expected_verdict": "QUARANTINE_SOLAR_MISMATCH",
        "ground_truth_source": "pvlib.solarposition.get_solarposition",
    }


def _abstain(
    scenario_id: str,
    narrative: str,
    latitude: float,
    longitude: float,
    timestamp_iso: str,
    expected_verdict: str,
) -> dict:
    """A capture the detector must REFUSE to judge.

    Included deliberately: a forensic tool that always produces a confident
    answer is a liability. These assert the abstention path works.
    """
    ts = dt.datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
    pos = calculate_solar_position(latitude, longitude, ts)
    expected = expected_shadow_azimuth(pos["azimuth_deg"])
    # A self-consistent shadow: the ONLY reason to abstain is sun elevation.
    observed = expected % 360.0
    result = verify_shadow_coherence(latitude, longitude, ts, observed)
    return {
        "scenario_id": scenario_id,
        "kind": "abstain",
        "narrative": narrative,
        "latitude": latitude,
        "longitude": longitude,
        "timestamp_utc": timestamp_iso,
        "observed_shadow_azimuth_deg": round(observed, 2),
        "pvlib_sun_azimuth_deg": round(pos["azimuth_deg"], 2),
        "pvlib_sun_elevation_deg": round(pos["elevation_deg"], 2),
        "expected_shadow_azimuth_deg": round(expected, 2),
        "angular_error_deg": result.angular_error_deg,
        "margin_to_tolerance_deg": result.margin_to_tolerance_deg,
        "expected_verdict": expected_verdict,
        "ground_truth_source": "pvlib.solarposition.get_solarposition",
    }


def build_fixtures() -> list:
    fixtures = [
        # ---------------- GENUINE: wide-margin demo captures ---------------- #
        _genuine(
            "GEN_01_NAIROBI_MORNING",
            "Kilifi mangrove survey, mid-morning. Sun well clear of the horizon "
            "so the cast shadow is long and its azimuth is terrain-independent.",
            -1.2921, 36.8219, "2026-09-22T08:15:30Z",
        ),
        _genuine(
            "GEN_02_NAIROBI_MIDDAY",
            "Tsavo East plot inspection near local solar noon.",
            -1.2921, 36.8219, "2026-09-22T09:32:00Z",
            jitter_deg=1.0,
        ),
        _genuine(
            "GEN_03_ANKARA_SUMMER_SOLSTICE",
            "Replaces the impossible documented Ankara vector (138.5 deg; true "
            "value 188.1 deg). Midday sun, short shadows, azimuth ~180 deg.",
            39.9207, 32.8541, "2026-06-21T09:48:00Z",
            jitter_deg=1.5,
        ),
        _genuine(
            "GEN_04_BERLIN_WINTER_SOLSTICE",
            "Replaces the documented Berlin vector (173.1 deg; true 179.0 deg). "
            "Low winter sun; still above the 10 deg abstention gate.",
            52.5200, 13.4050, "2026-12-21T13:00:00Z",
            jitter_deg=2.5,
        ),
        _genuine(
            "GEN_05_TSAVO_PM",
            "Tsavo East corridor, mid-afternoon. Sun in the west, shadow east.",
            -2.8541, 38.4521, "2026-09-22T11:30:00Z",
            jitter_deg=2.0,
        ),
        # ---------------- FRAUD: real photo, falsified clock --------------- #
        _fraud(
            "FRAUD_01_AFTERNOON_CLAIM_MORNING_PHOTO",
            "HEADLINE DEMO CASE. A contractor uploads an urban-nursery photo "
            "claiming a 14:30 EAT capture in the Tsavo corridor. The shadow is "
            "genuine but proves a morning capture. This is the pitch moment.",
            -2.8541, 38.4521,
            true_capture_iso="2026-09-22T05:15:00Z",
            claimed_capture_iso="2026-09-22T11:30:00Z",
        ),
        _fraud(
            "FRAUD_02_MORNING_CLAIM_AFTERNOON_PHOTO",
            "Inverse of the headline case: an afternoon capture claimed as "
            "morning. Confirms the detector is not merely detecting 'morning'.",
            -2.8541, 38.4521,
            true_capture_iso="2026-09-22T11:30:00Z",
            claimed_capture_iso="2026-09-22T05:15:00Z",
        ),
        _fraud(
            "FRAUD_03_WRONG_HEMISPHERE",
            "A northern-hemisphere sun angle claimed for a southern-hemisphere "
            "coordinate, a common hand-edit when reusing a stock photo.",
            -25.7479, 28.2293,  # Pretoria
            true_capture_iso="2026-09-22T08:00:00Z",
            claimed_capture_iso="2026-09-22T18:00:00Z",
        ),
        # ---------------- ABSTAIN: the detector must decline --------------- #
        _abstain(
            "ABSTAIN_01_DAWN_LOW_SUN",
            "Sun below the 10 deg gate. Shadow azimuth is dominated by terrain "
            "slope, so no automated fraud verdict may be issued.",
            -1.2921, 36.8219, "2026-09-22T05:35:00Z",
            expected_verdict="REVIEW_LOW_SUN_UNDETERMINED",
        ),
        _abstain(
            "ABSTAIN_02_NIGHTTIME",
            "A field photograph claimed at local midnight. Legitimately "
            "impossible, and a hard fraud signal.",
            -1.2921, 36.8219, "2026-09-22T22:00:00Z",
            expected_verdict="QUARANTINE_NIGHTTIME_CAPTURE_ANOMALY",
        ),
    ]
    return fixtures


def validate(fixtures: list) -> list:
    """Assert every fixture behaves as its kind demands. Returns problems."""
    problems = []
    for f in fixtures:
        ts = dt.datetime.fromisoformat(f["timestamp_utc"].replace("Z", "+00:00"))
        result = verify_shadow_coherence(
            f["latitude"], f["longitude"], ts, f["observed_shadow_azimuth_deg"]
        )
        if result.verdict.value != f["expected_verdict"]:
            problems.append(
                f"{f['scenario_id']}: expected {f['expected_verdict']}, "
                f"got {result.verdict.value}"
            )
        if f["kind"] == "genuine":
            margin = f["margin_to_tolerance_deg"]
            if margin < REQUIRED_FIXTURE_MARGIN_DEG:
                problems.append(
                    f"{f['scenario_id']}: margin {margin} deg is below the "
                    f"required {REQUIRED_FIXTURE_MARGIN_DEG} deg — too close to "
                    "the fraud threshold to be demo-safe"
                )
        if f["kind"] == "fraud" and f["angular_error_deg"] < 90.0:
            problems.append(
                f"{f['scenario_id']}: fraud error {f['angular_error_deg']} deg is "
                "too small to be a convincing impossibility"
            )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the committed fixture file is current; do not write.",
    )
    args = parser.parse_args()

    fixtures = build_fixtures()
    problems = validate(fixtures)

    if problems:
        print("FIXTURE VALIDATION FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1

    payload = {
        "_meta": {
            "description": (
                "Solar forensic fixtures. Every expected_shadow_azimuth_deg and "
                "calculated_sun_azimuth_deg is emitted by pvlib, never hand-written. "
                "Regenerate with: python scripts/gen_solar_fixtures.py"
            ),
            "generator": "scripts/gen_solar_fixtures.py",
            "ground_truth": "pvlib.solarposition.get_solarposition",
            "shadow_coherence_tolerance_deg": SHADOW_COHERENCE_TOLERANCE_DEG,
            "required_genuine_margin_deg": REQUIRED_FIXTURE_MARGIN_DEG,
            "genuine_jitter_deg": GENUINE_JITTER_DEG,
            "counts": {
                "genuine": sum(1 for f in fixtures if f["kind"] == "genuine"),
                "fraud": sum(1 for f in fixtures if f["kind"] == "fraud"),
                "abstain": sum(1 for f in fixtures if f["kind"] == "abstain"),
            },
        },
        "fixtures": fixtures,
    }

    if args.check:
        if not FIXTURE_PATH.exists():
            print(f"FAIL: {FIXTURE_PATH} does not exist")
            return 1
        committed = json.loads(FIXTURE_PATH.read_text())
        if committed == payload:
            print(f"OK: {FIXTURE_PATH.name} is current ({len(fixtures)} fixtures)")
            return 0
        print(f"FAIL: {FIXTURE_PATH.name} is stale — run the generator")
        return 1

    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(payload, indent=2) + "\n")

    print(f"Wrote {FIXTURE_PATH.relative_to(REPO)}")
    print(f"  {len(fixtures)} fixtures: {payload['_meta']['counts']}")
    print()
    print(f"{'scenario':<42} {'kind':<8} {'err':>7} {'margin':>8}  verdict")
    print("-" * 96)
    for f in fixtures:
        print(
            f"{f['scenario_id']:<42} {f['kind']:<8} "
            f"{f['angular_error_deg']:>7.2f} {f['margin_to_tolerance_deg']:>8.2f}  "
            f"{f['expected_verdict']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
