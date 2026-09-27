"""
Tier 1 — Physics & Forensics Unit Tests.

Covers: solar ephemeris shadow coherence, allometric carbon, VM0047
uncertainty, and synthetic/screen-replay detection.

Run: pytest backend/tests/test_physics.py -v
"""

from __future__ import annotations

import datetime as dt
import math

import pytest

from conftest import as_utc
from services.biomass_service import (
    CARBON_FRACTION,
    CHAVE_B1,
    CHAVE_PREFACTOR,
    CO2_PER_CARBON,
    VM0047_MAX_SAMPLING_ERROR_PCT,
    BiomassEstimate,
    ComplianceStatus,
    apply_vm0047_uncertainty_discount,
    calculate_allometric_carbon,
    sampling_error_pct,
)
from services.solar_service import (
    MIN_SHADOW_ELEVATION_DEG,
    REQUIRED_FIXTURE_MARGIN_DEG,
    SHADOW_COHERENCE_TOLERANCE_DEG,
    ShadowVerdict,
    angular_separation_deg,
    calculate_solar_position,
    detect_time_of_day_fraud,
    expected_shadow_azimuth,
    verify_shadow_coherence,
)


# =========================================================================== #
# 1. Ephemeris sanity
# =========================================================================== #


class TestEphemeris:
    def test_azimuth_within_valid_range(self, genuine_fixtures):
        for f in genuine_fixtures:
            pos = calculate_solar_position(
                f["latitude"], f["longitude"], as_utc(f["timestamp_utc"])
            )
            assert 0.0 <= pos["azimuth_deg"] <= 360.0, f["scenario_id"]
            assert -90.0 <= pos["elevation_deg"] <= 90.0, f["scenario_id"]

    def test_rejects_naive_datetime(self):
        """A naive datetime is the exact bug this module exists to catch."""
        with pytest.raises(ValueError, match="timezone-aware"):
            calculate_solar_position(-1.2921, 36.8219, dt.datetime(2026, 9, 22, 8, 15, 30))

    @pytest.mark.parametrize(
        "lat,lon",
        [(91.0, 0.0), (-91.0, 0.0), (0.0, 181.0), (0.0, -181.0)],
    )
    def test_rejects_out_of_range_coordinates(self, lat, lon):
        with pytest.raises(ValueError):
            calculate_solar_position(lat, lon, dt.datetime(2026, 9, 22, tzinfo=dt.timezone.utc))

    def test_solar_noon_azimuth_is_near_cardinal_directions(self):
        """At solar noon the sun is due south (N hemi) or due north (S hemi)."""
        # Ankara, summer solstice. Solar noon at 32.85E is ~09:47 UTC, so the sun
        # is due south (within 2 deg of 180) there.
        at_noon = calculate_solar_position(
            39.9207, 32.8541, dt.datetime(2026, 6, 21, 9, 47, tzinfo=dt.timezone.utc)
        )
        assert abs(at_noon["azimuth_deg"] - 180.0) < 3.0

        # 13 minutes later, pvlib gives 187.74 deg. The original fixture claimed
        # 138.5 deg, which is ~49 deg away and cannot occur at any time of day
        # at that longitude.
        later = calculate_solar_position(
            39.9207, 32.8541, dt.datetime(2026, 6, 21, 10, 0, tzinfo=dt.timezone.utc)
        )
        assert abs(later["azimuth_deg"] - 187.74) < 1.0
        assert abs(later["azimuth_deg"] - 138.5) > 45.0, (
            "the documented Ankara value is ~49 deg from the true azimuth"
        )

    def test_morning_sun_east_of_solar_noon(self):
        """Morning sun must have a SMALLER azimuth than the same-day noon sun."""
        lat, lon = -1.2921, 36.8219
        morning = calculate_solar_position(
            lat, lon, dt.datetime(2026, 9, 22, 5, 15, tzinfo=dt.timezone.utc)
        )
        noon = calculate_solar_position(
            lat, lon, dt.datetime(2026, 9, 22, 9, 32, tzinfo=dt.timezone.utc)
        )
        assert morning["azimuth_deg"] < noon["azimuth_deg"]

    def test_elevation_peaks_at_solar_noon(self):
        lat, lon = -1.2921, 36.8219
        before = calculate_solar_position(
            lat, lon, dt.datetime(2026, 9, 22, 7, 0, tzinfo=dt.timezone.utc)
        )
        noon = calculate_solar_position(
            lat, lon, dt.datetime(2026, 9, 22, 9, 32, tzinfo=dt.timezone.utc)
        )
        after = calculate_solar_position(
            lat, lon, dt.datetime(2026, 9, 22, 12, 0, tzinfo=dt.timezone.utc)
        )
        assert before["elevation_deg"] < noon["elevation_deg"]
        assert after["elevation_deg"] < noon["elevation_deg"]


# =========================================================================== #
# 2. Angular arithmetic
# =========================================================================== #


class TestAngularArithmetic:
    @pytest.mark.parametrize(
        "a,b,expected",
        [(0.0, 0.0, 0.0), (10.0, 370.0, 0.0), (359.0, 1.0, 2.0), (0.0, 180.0, 180.0)],
    )
    def test_wraps_around_the_circle(self, a, b, expected):
        assert angular_separation_deg(a, b) == pytest.approx(expected)

    def test_shadow_is_antipodal_to_sun(self):
        for sun_az in (0.0, 45.0, 94.2, 180.0, 271.4, 359.0):
            shadow = expected_shadow_azimuth(sun_az)
            assert angular_separation_deg(shadow, sun_az) == pytest.approx(180.0)


# =========================================================================== #
# 3. Shadow coherence — the fixture-driven core
# =========================================================================== #


class TestShadowCoherence:
    def test_every_genuine_fixture_passes(self, genuine_fixtures):
        for f in genuine_fixtures:
            result = verify_shadow_coherence(
                f["latitude"],
                f["longitude"],
                as_utc(f["timestamp_utc"]),
                f["observed_shadow_azimuth_deg"],
            )
            assert result.verdict == ShadowVerdict.PHYSICS_PASS, (
                f"{f['scenario_id']} expected PHYSICS_PASS, got {result.verdict.value}"
            )
            assert result.is_physically_coherent is True
            assert result.is_fraud is False

    def test_genuine_fixtures_keep_a_wide_demo_margin(self, genuine_fixtures):
        """The original fixture cleared the threshold by 1.1 deg — a coin flip.

        This is the regression guard that stops that coming back.
        """
        for f in genuine_fixtures:
            result = verify_shadow_coherence(
                f["latitude"],
                f["longitude"],
                as_utc(f["timestamp_utc"]),
                f["observed_shadow_azimuth_deg"],
            )
            assert result.margin_to_tolerance_deg >= REQUIRED_FIXTURE_MARGIN_DEG, (
                f"{f['scenario_id']} margin {result.margin_to_tolerance_deg} deg is "
                f"below the required {REQUIRED_FIXTURE_MARGIN_DEG} deg"
            )

    def test_every_fraud_fixture_is_quarantined(self, fraud_fixtures):
        for f in fraud_fixtures:
            result = verify_shadow_coherence(
                f["latitude"],
                f["longitude"],
                as_utc(f["timestamp_utc"]),
                f["observed_shadow_azimuth_deg"],
            )
            assert result.verdict == ShadowVerdict.QUARANTINE_SOLAR_MISMATCH, (
                f"{f['scenario_id']} expected quarantine, got {result.verdict.value}"
            )
            assert result.is_fraud is True
            # Attack-class-aware bar, mirroring the generator. A falsified CLOCK
            # inverts the sun by ~180 deg; a falsified LOCATION is bounded by the
            # divergence between the two sites' solar paths, which for Kilifi vs
            # Ankara maxes out at ~88.5 deg over an entire day.
            bar = f.get("fraud_min_error_deg", 90.0)
            assert result.angular_error_deg >= bar, (
                f"{f['scenario_id']} error {result.angular_error_deg} below bar {bar}"
            )
            assert result.angular_error_deg > SHADOW_COHERENCE_TOLERANCE_DEG * 3

    def test_abstention_fixtures(self, abstain_fixtures):
        for f in abstain_fixtures:
            result = verify_shadow_coherence(
                f["latitude"],
                f["longitude"],
                as_utc(f["timestamp_utc"]),
                f["observed_shadow_azimuth_deg"],
            )
            assert result.verdict.value == f["expected_verdict"], f["scenario_id"]

    def test_low_sun_abstains_rather_than_accusing(self, abstain_fixtures):
        """A sun too low to cast a usable shadow cannot support a fraud verdict.

        The timestamp comes from the generated fixture, which PROBES for a ~5 deg
        dawn. A hand-written 05:35 UTC was tried first and put the equatorial sun
        32 deg up, so the scenario tested nothing.
        """
        f = next(x for x in abstain_fixtures if x["expected_verdict"] == "REVIEW_LOW_SUN_UNDETERMINED")
        ts = as_utc(f["timestamp_utc"])
        pos = calculate_solar_position(f["latitude"], f["longitude"], ts)
        assert 0.0 <= pos["elevation_deg"] < MIN_SHADOW_ELEVATION_DEG, (
            f"probe landed at {pos['elevation_deg']} deg, not in the abstention band"
        )

        result = verify_shadow_coherence(
            f["latitude"], f["longitude"], ts, f["observed_shadow_azimuth_deg"]
        )
        assert result.verdict == ShadowVerdict.REVIEW_LOW_SUN
        assert result.is_fraud is False
        assert "elevation" in (result.abstain_reason or "").lower()

    def test_nighttime_capture_is_fraud(self):
        result = verify_shadow_coherence(
            -1.2921, 36.8219, dt.datetime(2026, 9, 22, 22, 0, tzinfo=dt.timezone.utc), 100.0
        )
        assert result.verdict == ShadowVerdict.QUARANTINE_NIGHTTIME
        assert result.is_fraud is True

    def test_missing_observation_is_not_fraud(self):
        """No observation is not evidence of fraud."""
        result = verify_shadow_coherence(-1.2921, 36.8219, dt.datetime(2026, 9, 22, 8, 15, tzinfo=dt.timezone.utc))
        assert result.verdict == ShadowVerdict.REVIEW_INSUFFICIENT_INPUT
        assert result.is_fraud is False

    def test_boundary_is_inclusive_at_tolerance(self):
        """Exactly at tolerance passes; a hair beyond fails."""
        lat, lon = -1.2921, 36.8219
        ts = dt.datetime(2026, 9, 22, 8, 15, 30, tzinfo=dt.timezone.utc)
        expected = expected_shadow_azimuth(calculate_solar_position(lat, lon, ts)["azimuth_deg"])

        at_limit = verify_shadow_coherence(
            lat, lon, ts, (expected + SHADOW_COHERENCE_TOLERANCE_DEG) % 360.0
        )
        beyond = verify_shadow_coherence(
            lat, lon, ts, (expected + SHADOW_COHERENCE_TOLERANCE_DEG + 0.5) % 360.0
        )
        assert at_limit.verdict == ShadowVerdict.PHYSICS_PASS
        assert beyond.verdict == ShadowVerdict.QUARANTINE_SOLAR_MISMATCH

    def test_headline_fraud_case_is_convincingly_impossible(self, fraud_fixtures):
        """The pitch moment: 'claimed 2:30 PM, shadow proves morning.'"""
        headline = next(
            f for f in fraud_fixtures
            if f["scenario_id"] == "FRAUD_01_AFTERNOON_CLAIM_MORNING_PHOTO"
        )
        result = verify_shadow_coherence(
            headline["latitude"],
            headline["longitude"],
            as_utc(headline["timestamp_utc"]),
            headline["observed_shadow_azimuth_deg"],
        )
        assert result.angular_error_deg > 150.0
        assert result.margin_to_tolerance_deg < -100.0

    def test_result_is_json_serialisable(self, genuine_fixtures):
        import json

        f = genuine_fixtures[0]
        payload = verify_shadow_coherence(
            f["latitude"], f["longitude"], as_utc(f["timestamp_utc"]), f["observed_shadow_azimuth_deg"]
        ).to_dict()
        assert json.loads(json.dumps(payload))["verdict"] == "PHYSICS_PASS"

    def test_time_of_day_fraud_report(self):
        report = detect_time_of_day_fraud(
            -2.8541, 38.4521,
            dt.datetime(2026, 9, 22, 11, 30, tzinfo=dt.timezone.utc),
            267.6,
        )
        assert report["conclusion"] == "claimed_capture_time_is_physically_impossible"
        assert report["angular_error_deg"] > 90.0


# =========================================================================== #
# 4. Allometric carbon — Chave et al. (2014) Eq. 4, coefficient verified
# =========================================================================== #


class TestAllometricCarbon:
    """Chave et al. (2014) Eq. 4: AGB = 0.0673 * (WD * H * D^2) ** 0.976.

    The prefactor was briefly "corrected" to exp(-0.533) and then reverted: the
    published coefficient IS 0.0673, per the R BIOMASS package reference
    implementation. These tests pin the verified form so the detour cannot recur.
    """

    def test_prefactor_matches_published_chave_2014_eq4(self):
        assert CHAVE_PREFACTOR == 0.0673
        assert CHAVE_B1 == 0.976

    def test_agb_matches_chave_formula_independently(self):
        """Recompute from the published equation, not from our own constant."""
        rho, dbh, height = 0.58, 21.0, 4.0
        area_m2 = (dbh / 2.1) ** 2

        result = calculate_allometric_carbon(
            canopy_area_m2=area_m2, mean_height_m=height, wood_density_g_cm3=rho
        )
        reference_agb = 0.0673 * ((rho * dbh**2 * height) ** 0.976)
        assert result.agb_kg == pytest.approx(reference_agb, rel=0.001)

    def test_result_is_plausible_against_stem_geometry(self):
        """Guards against a coefficient that is out by an order of magnitude.

        AGB cannot be wildly inconsistent with the stem's own wood volume. The
        perfect-cylinder model pi/4 * D^2 * H * rho is crude, but an allometric
        regression fitted to 4,004 harvested trees should land within a factor
        of a few of it. This is the test that would have caught the reverted
        exp(-0.533) change, which produced 6.7x the cylinder mass at every DBH.
        """
        rho, dbh, height = 0.45, 6.8, 3.9
        result = calculate_allometric_carbon(
            canopy_area_m2=11.29,
            mean_height_m=height,
            wood_density_g_cm3=rho,
            measured_dbh_cm=dbh,
        )
        cylinder_kg = (math.pi / 4) * (dbh / 100) ** 2 * height * rho * 1000
        ratio = result.agb_kg / cylinder_kg
        assert 0.2 < ratio < 5.0, (
            f"AGB/cylinder ratio {ratio:.2f} is implausible; the coefficient is "
            "probably wrong"
        )

    def test_worked_example_sapling(self):
        """A 3.9 m Rhizophora sapling: ~4.9 kg AGB, ~0.0085 tCO2e."""
        result = calculate_allometric_carbon(
            canopy_area_m2=11.29,
            mean_height_m=3.9,
            wood_density_g_cm3=0.45,
            species_name="Rhizophora mucronata",
            measured_dbh_cm=6.8,
        )
        assert result.estimated_dbh_cm == 6.8
        assert result.agb_kg == pytest.approx(4.91, rel=0.02)
        assert result.co2e_metric_tons == pytest.approx(0.00847, rel=0.02)

    def test_measured_dbh_bypasses_the_proxy(self):
        result = calculate_allometric_carbon(
            canopy_area_m2=100.0, mean_height_m=4.0, measured_dbh_cm=18.0
        )
        assert result.dbh_source == "field_measured_dbh_1.3m"
        assert result.estimated_dbh_cm == 18.0

    def test_proxy_path_is_labelled_as_a_proxy(self):
        """The dossier must not present a crown-area estimate as a survey."""
        result = calculate_allometric_carbon(canopy_area_m2=100.0, mean_height_m=4.0)
        assert "proxy" in result.dbh_source

    def test_per_hectare_scaling(self):
        per_stem = calculate_allometric_carbon(canopy_area_m2=25.0, mean_height_m=4.0)
        per_ha = calculate_allometric_carbon(
            canopy_area_m2=25.0, mean_height_m=4.0, stand_area_ha=1.0, stems_per_hectare=400
        )
        # co2e_metric_tons is rounded to 4 dp before return, so on a value
        # around 0.026 that is ~0.2% precision; scaling by 400 needs a
        # correspondingly looser tolerance than the un-rounded figure would.
        assert per_ha.co2e_metric_tons == pytest.approx(
            per_stem.co2e_metric_tons * 400, rel=0.01
        )

    def test_carbon_and_co2_factors(self):
        result = calculate_allometric_carbon(canopy_area_m2=100.0, mean_height_m=4.0)
        assert result.carbon_kg == pytest.approx(result.agb_kg * CARBON_FRACTION, rel=0.001)
        assert result.co2e_metric_tons == pytest.approx(
            result.carbon_kg * CO2_PER_CARBON / 1000.0, rel=0.001
        )

    def test_equation_is_recorded_in_the_estimate(self):
        result = calculate_allometric_carbon(canopy_area_m2=100.0, mean_height_m=4.0)
        assert "Chave" in result.equation
        assert "0.0673" in result.equation

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"canopy_area_m2": -1.0, "mean_height_m": 4.0},
            {"canopy_area_m2": 100.0, "mean_height_m": 0.0},
            {"canopy_area_m2": 100.0, "mean_height_m": 4.0, "wood_density_g_cm3": 0.0},
        ],
    )
    def test_rejects_impossible_inputs(self, kwargs):
        with pytest.raises(ValueError):
            calculate_allometric_carbon(**kwargs)

    def test_monotonic_in_area_and_height(self):
        small = calculate_allometric_carbon(canopy_area_m2=25.0, mean_height_m=3.0)
        large = calculate_allometric_carbon(canopy_area_m2=100.0, mean_height_m=3.0)
        tall = calculate_allometric_carbon(canopy_area_m2=25.0, mean_height_m=6.0)
        assert small.co2e_metric_tons < large.co2e_metric_tons
        assert small.co2e_metric_tons < tall.co2e_metric_tons


# =========================================================================== #
# 5. Verra VM0047 §8.4
# =========================================================================== #


class TestVM0047Uncertainty:
    def test_no_discount_below_threshold(self):
        result = apply_vm0047_uncertainty_discount(100.0, 9.4)
        assert result.discount_applied_pct == 0.0
        assert result.net_certified_tco2e == pytest.approx(100.0)
        assert result.compliance_status == ComplianceStatus.VM0047_CONSERVATIVE_CERTIFIED

    def test_no_discount_exactly_at_threshold(self):
        result = apply_vm0047_uncertainty_discount(100.0, VM0047_MAX_SAMPLING_ERROR_PCT)
        assert result.discount_applied_pct == 0.0

    def test_discount_above_threshold(self):
        # 18% sits between the 15% trigger and the 22.5% severe-precision line.
        result = apply_vm0047_uncertainty_discount(100.0, 18.0)
        assert result.discount_applied_pct == pytest.approx(3.0)
        assert result.net_certified_tco2e == pytest.approx(97.0)
        assert result.compliance_status == ComplianceStatus.DISCOUNT_APPLIED

    def test_discount_is_linear_above_threshold(self):
        for err, expected_discount in ((18.0, 3.0), (25.0, 10.0), (40.0, 25.0)):
            result = apply_vm0047_uncertainty_discount(100.0, err)
            assert result.discount_applied_pct == pytest.approx(expected_discount)

    def test_severe_imprecision_is_flagged(self):
        result = apply_vm0047_uncertainty_discount(100.0, 40.0)
        assert result.compliance_status == ComplianceStatus.INSUFFICIENT_PRECISION
        assert result.discount_applied_pct == pytest.approx(25.0)

    def test_sampling_error_formula(self):
        """E = (t_{0.95, n-1} * s) / (sqrt(n) * mean) * 100."""
        err = sampling_error_pct(sample_mean=100.0, sample_std=20.0, n=25)
        t = __import__("scipy.stats", fromlist=["stats"]).t.ppf(0.95, 24)
        assert err == pytest.approx((t * 20.0) / (5.0 * 100.0) * 100.0, rel=0.001)
        assert err > 0

    def test_sampling_error_falls_with_sample_size(self):
        small_n = sampling_error_pct(100.0, 20.0, n=5)
        large_n = sampling_error_pct(100.0, 20.0, n=100)
        assert large_n < small_n

    @pytest.mark.parametrize("kwargs", [{"sample_mean": 100.0, "sample_std": 20.0, "n": 1},
                                       {"sample_mean": 0.0, "sample_std": 20.0, "n": 10}])
    def test_rejects_degenerate_sampling_design(self, kwargs):
        with pytest.raises(ValueError):
            sampling_error_pct(**kwargs)

    def test_rejects_negative_sampling_error(self):
        with pytest.raises(ValueError):
            apply_vm0047_uncertainty_discount(100.0, -5.0)
