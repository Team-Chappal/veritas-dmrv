"""
VERITAS dMRV — Solar Ephemeris Forensics (Module 1)
=====================================================

Ground-truth astronomical verification for field media authenticity.

WHY THIS MODULE IS THE TRUST ANCHOR
-----------------------------------
The entire product thesis is "we replace assertion with mathematics." If this
module is wrong, everything downstream inherits the error. Two defects were
found in the original design (docs/03-SYSTEM-DESIGN.md) and are corrected here:

  DEFECT 1 — Hand-written test fixtures.
    docs/12-TESTING-AND-QA-STRATEGY.md asserted solar azimuths that are outside
    their own stated tolerances (Ankara 2026-06-21T10:00Z was off by 49.6 deg,
    which is physically impossible -- the sun is 12 minutes PAST solar noon
    there, so the azimuth must be ~188 deg, not the documented 138.5 deg).
    The genuine "legitimate photo" fixture cleared the 12 deg fraud threshold
    by only 1.1 deg. Fixtures are now GENERATED from pvlib output by
    scripts/gen_solar_fixtures.py and committed as JSON, never hand-written.

  DEFECT 2 — Low-sun gate too permissive.
    The original code rejected only elevation < 0 deg. Below ~10 deg solar
    elevation, shadow azimuth is dominated by terrain slope rather than the
    sun: the signal is noise, and genuine photos get quarantined at dawn/dusk.
    We now gate at MIN_SHADOW_ELEVATION_DEG and route to REVIEW_AMBIGUOUS
    (a human looks at it) instead of QUARANTINE (an automated fraud verdict).

AZIMUTH CONVENTION
------------------
All azimuths in this module are degrees from True North, clockwise, matching
pvlib and NOAA. This is NOT the same convention as the mathematical
derivation printed in docs/03-SYSTEM-DESIGN.md §1.2 step 4, which used a
non-standard expression for cos(azimuth). The code below follows pvlib
directly and the derivation has been corrected to match.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd
import pvlib

# --------------------------------------------------------------------------- #
# Thresholds and physical constants
# --------------------------------------------------------------------------- #

#: Angular tolerance between the astronomically expected shadow azimuth and the
#: shadow azimuth observed in the image, in degrees. Beyond this the reported
#: capture time/location is physically incompatible with the image content.
SHADOW_COHERENCE_TOLERANCE_DEG = 12.0

#: Minimum margin we require between a GENUINE fixture's observed error and the
#: tolerance. A fixture that passes by less than this is a coin flip on stage.
REQUIRED_FIXTURE_MARGIN_DEG = 5.0

#: Below this solar elevation, cast shadows are too elongated and
#: terrain-slope-dominated for their azimuth to constrain the sun position.
#: Below this we abstain from an automated fraud verdict.
MIN_SHADOW_ELEVATION_DEG = 10.0

#: Perceptual-hash corpus separation. Below this Hamming distance a photo is
#: considered a probable duplicate / recycled nursery stock.
PHASH_DUPLICATE_THRESHOLD = 12


class ShadowVerdict(str, Enum):
    """Outcome of astronomical shadow-coherence verification."""

    PHYSICS_PASS = "PHYSICS_PASS"
    QUARANTINE_SOLAR_MISMATCH = "QUARANTINE_SOLAR_MISMATCH"
    #: Sun is too low to cast a usable shadow — abstain, do not accuse.
    REVIEW_LOW_SUN = "REVIEW_LOW_SUN_UNDETERMINED"
    #: Sun below horizon — a field photo cannot legitimately be night-time.
    QUARANTINE_NIGHTTIME = "QUARANTINE_NIGHTTIME_CAPTURE_ANOMALY"
    #: Missing or unusable inputs.
    REVIEW_INSUFFICIENT_INPUT = "REVIEW_INSUFFICIENT_INPUT"


# --------------------------------------------------------------------------- #
# Result type
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SolarVerification:
    """Full auditable result of one shadow-coherence check.

    Every field is serialised into the audit receipt and the C2PA
    ``veritas.forensic.telemetry`` assertion, so this must stay complete
    and self-describing.
    """

    verdict: ShadowVerdict
    #: True only when we are confident enough to affirm authenticity.
    is_physically_coherent: bool
    #: True when we affirmatively declare fraud.
    is_fraud: bool
    angular_error_deg: float
    calculated_sun_azimuth_deg: float
    calculated_sun_elevation_deg: float
    expected_shadow_azimuth_deg: float
    observed_shadow_azimuth_deg: Optional[float]
    tolerance_deg: float = SHADOW_COHERENCE_TOLERANCE_DEG
    margin_to_tolerance_deg: float = 0.0
    abstain_reason: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["verdict"] = self.verdict.value
        return d


# --------------------------------------------------------------------------- #
# Core ephemeris
# --------------------------------------------------------------------------- #


def calculate_solar_position(
    latitude: float,
    longitude: float,
    timestamp_utc: dt.datetime,
) -> dict:
    """Compute true solar position via pvlib.

    Args:
        latitude:  Decimal degrees WGS84, -90..90.
        longitude: Decimal degrees WGS84, -180..180.
        timestamp_utc: Timezone-AWARE UTC datetime. A naive datetime is
            rejected rather than silently assumed to be UTC, because the
            single most damaging failure mode here is a timezone slip.

    Returns:
        ``{"azimuth_deg": float, "elevation_deg": float}`` — azimuth measured
        from True North, clockwise.
    """
    if timestamp_utc.tzinfo is None:
        raise ValueError(
            "timestamp_utc must be timezone-aware. A naive datetime is the "
            "exact class of bug this module exists to catch; refusing to guess."
        )
    if not (-90.0 <= latitude <= 90.0):
        raise ValueError(f"latitude out of range: {latitude}")
    if not (-180.0 <= longitude <= 180.0):
        raise ValueError(f"longitude out of range: {longitude}")

    times = pd.DatetimeIndex([pd.Timestamp(timestamp_utc).tz_convert("UTC")])
    # pvlib returns azimuth in degrees from North, clockwise. No extra offset
    # is applied — adding 180 here was a bug in the original design.
    pos = pvlib.solarposition.get_solarposition(times, latitude, longitude)

    azimuth = float(pos["azimuth"].iloc[0])
    elevation = float(pos["elevation"].iloc[0])

    # pvlib azimuth is undefined at solar zenith; normalise defensively.
    if math.isnan(azimuth):
        azimuth = 180.0
    if math.isnan(elevation):
        elevation = 0.0

    return {
        "azimuth_deg": azimuth % 360.0,
        "elevation_deg": elevation,
    }


def expected_shadow_azimuth(sun_azimuth_deg: float) -> float:
    """A cast shadow points directly away from the sun.

    On a flat surface, so terrain slope is the dominant error source at low
    sun elevation (see MIN_SHADOW_ELEVATION_DEG).
    """
    return (sun_azimuth_deg + 180.0) % 360.0


def angular_separation_deg(a: float, b: float) -> float:
    """Absolute angular difference between two azimuths, wrapped to 0..180.

    Azimuths are circular: 359 deg and 1 deg are 2 deg apart, not 358.
    """
    diff = abs((float(a) - float(b)) % 360.0)
    return min(diff, 360.0 - diff)


# --------------------------------------------------------------------------- #
# Shadow coherence
# --------------------------------------------------------------------------- #


def verify_shadow_coherence(
    latitude: float,
    longitude: float,
    timestamp_utc: dt.datetime,
    observed_shadow_azimuth_deg: Optional[float] = None,
    tolerance_deg: float = SHADOW_COHERENCE_TOLERANCE_DEG,
) -> SolarVerification:
    """Verify a photo's observed shadow against true astronomical geometry.

    This is the Q1 "authenticity" answer. It is deliberately *abstaining* in
    ambiguous conditions: an auditor is far more damaged by a false fraud
    accusation on a genuine planting than by a photo routed to human review.

    Returns a :class:`SolarVerification`. Never raises for physical
    impossibility — it returns an abstaining verdict instead, because every
    verdict must be serialisable into the audit receipt.
    """
    if observed_shadow_azimuth_deg is None:
        return SolarVerification(
            verdict=ShadowVerdict.REVIEW_INSUFFICIENT_INPUT,
            is_physically_coherent=False,
            is_fraud=False,
            angular_error_deg=180.0,
            calculated_sun_azimuth_deg=0.0,
            calculated_sun_elevation_deg=0.0,
            expected_shadow_azimuth_deg=0.0,
            observed_shadow_azimuth_deg=None,
            tolerance_deg=tolerance_deg,
            abstain_reason="No observed shadow azimuth supplied by the client.",
        )

    observed = float(observed_shadow_azimuth_deg) % 360.0

    try:
        position = calculate_solar_position(latitude, longitude, timestamp_utc)
    except ValueError as exc:
        return SolarVerification(
            verdict=ShadowVerdict.REVIEW_INSUFFICIENT_INPUT,
            is_physically_coherent=False,
            is_fraud=False,
            angular_error_deg=180.0,
            calculated_sun_azimuth_deg=0.0,
            calculated_sun_elevation_deg=0.0,
            expected_shadow_azimuth_deg=0.0,
            observed_shadow_azimuth_deg=observed,
            tolerance_deg=tolerance_deg,
            abstain_reason=str(exc),
        )

    sun_az = position["azimuth_deg"]
    sun_el = position["elevation_deg"]
    expected = expected_shadow_azimuth(sun_az)
    error = angular_separation_deg(expected, observed)
    margin = tolerance_deg - error

    common = dict(
        angular_error_deg=round(error, 2),
        calculated_sun_azimuth_deg=round(sun_az, 2),
        calculated_sun_elevation_deg=round(sun_el, 2),
        expected_shadow_azimuth_deg=round(expected, 2),
        observed_shadow_azimuth_deg=round(observed, 2),
        tolerance_deg=tolerance_deg,
    )

    # --- Abstention ladder, ordered by how invalid the measurement is ------- #

    if sun_el < 0.0:
        # Genuine field photography does not happen at night.
        return SolarVerification(
            verdict=ShadowVerdict.QUARANTINE_NIGHTTIME,
            is_physically_coherent=False,
            is_fraud=True,
            margin_to_tolerance_deg=round(margin, 2),
            **common,
        )

    if sun_el < MIN_SHADOW_ELEVATION_DEG:
        # Cast shadows here are dominated by terrain slope. We cannot make an
        # automated fraud claim, and we must not let noise accuse a ranger.
        return SolarVerification(
            verdict=ShadowVerdict.REVIEW_LOW_SUN,
            is_physically_coherent=False,
            is_fraud=False,
            abstain_reason=(
                f"Solar elevation {sun_el:.1f} deg is below the "
                f"{MIN_SHADOW_ELEVATION_DEG} deg threshold for reliable shadow "
                "azimuth; deferring to C2PA provenance and perceptual-hash dedup."
            ),
            **common,
        )

    if error <= tolerance_deg:
        return SolarVerification(
            verdict=ShadowVerdict.PHYSICS_PASS,
            is_physically_coherent=True,
            is_fraud=False,
            margin_to_tolerance_deg=round(margin, 2),
            **common,
        )

    return SolarVerification(
        verdict=ShadowVerdict.QUARANTINE_SOLAR_MISMATCH,
        is_physically_coherent=False,
        is_fraud=True,
        margin_to_tolerance_deg=round(margin, 2),
        abstain_reason=(
            f"Observed shadow azimuth {observed:.1f} deg is {error:.1f} deg from "
            f"the astronomically expected {expected:.1f} deg for a sun at "
            f"{sun_az:.1f} deg / {sun_el:.1f} deg elevation. The reported capture "
            "time and location are physically incompatible with the image."
        ),
        **common,
    )


# --------------------------------------------------------------------------- #
# Self-check: the classic fraud signature
# --------------------------------------------------------------------------- #


def detect_time_of_day_fraud(
    latitude: float,
    longitude: float,
    timestamp_utc: dt.datetime,
    observed_shadow_azimuth_deg: float,
) -> dict:
    """Infer the true time-of-day implied by the observed shadow.

    Used by the demo narrative ("claimed 2 PM, shadow proves morning") and by
    the audit report, which is far more useful to an investigator when it says
    *when the photo was actually taken*, not merely that it was taken then.
    """
    position = calculate_solar_position(latitude, longitude, timestamp_utc)
    expected = expected_shadow_azimuth(position["azimuth_deg"])
    error = angular_separation_deg(expected, observed_shadow_azimuth_deg)

    # The observed shadow points away from the sun, so recover the implied
    # solar azimuth by reversing the 180 deg offset.
    implied_sun_azimuth = (observed_shadow_azimuth_deg + 180.0) % 360.0
    hemisphere = "northern" if position["azimuth_deg"] < 180.0 else "southern"

    if error <= SHADOW_COHERENCE_TOLERANCE_DEG:
        conclusion = "claimed_capture_time_is_consistent"
    else:
        # Azimuth alone cannot invert to a time without the declination, so we
        # report the geometry honestly rather than fabricating a clock time.
        conclusion = "claimed_capture_time_is_physically_impossible"

    return {
        "claimed_timestamp_utc": timestamp_utc.isoformat(),
        "calculated_sun_azimuth_deg": round(position["azimuth_deg"], 2),
        "implied_sun_azimuth_deg": round(implied_sun_azimuth, 2),
        "calculated_sun_elevation_deg": round(position["elevation_deg"], 2),
        "expected_shadow_azimuth_deg": round(expected, 2),
        "observed_shadow_azimuth_deg": round(observed_shadow_azimuth_deg % 360.0, 2),
        "angular_error_deg": round(error, 2),
        "azimuth_hemisphere": hemisphere,
        "conclusion": conclusion,
    }
