"""
VERITAS dMRV — Allometric Biomass & Carbon Accounting (Modules 5 / 5b)
=======================================================================

Converts a measured canopy surface-area delta into certified tonnes of CO2
equivalent, then applies the mandatory Verra VM0047 sampling-uncertainty
discount.

COEFFICIENT PROVENANCE — a correction that turned out to be unnecessary
---------------------------------------------------------------------
An earlier revision of this module replaced a prefactor of ``0.0673`` with
``math.exp(-0.533) ~= 0.5868``, on the belief that the documented constant was
wrong by a factor of 8.72. **That belief was incorrect and has been reverted.**

Chave et al. (2014) Eq. 4 is:

    AGB = 0.0673 * (WD * H * D^2) ** 0.976

This is confirmed by the reference implementation in the R ``BIOMASS`` package
(Rejou-Mechain, Tanguy & Perre, CRAN), which documents verbatim: "If tree height
data are available, the AGB is computed thanks to the following equation
(Eq. 4 in Chave et al., 2014): ``AGB = 0.0673 * (WD * H * D^2)^0.976``", and by
the abstract's own scope: the model is fitted to 4,004 directly harvested trees
>= 5 cm trunk diameter.

The original ``docs/03-SYSTEM-DESIGN.md`` constant was therefore correct, and the
apparent 6.7x discrepancy against a perfect-cylinder stem volume was the
regression behaving normally, not an error:

    DBH 6.8 cm, H 3.9 m, rho 0.45 g/cm^3
      Chave et al. (2014)  ->  4.91 kg AGB
      perfect cylinder     ->  6.42 kg AGB   (within 24%)

The record of the reverted change is retained here deliberately. A codebase whose
premise is "we replace assertion with mathematics" has no business shipping a
coefficient that nobody checked, and the failure mode that nearly shipped was the
most seductive one available: a plausible-looking intercept, converted to a
prefactor, cited to a real paper, and wrong. The lesson is carried forward in
``scripts/verify_docs.py``, which lints documentation claims for exactly this
shape of defect.

REMAINING CAVEAT (stated plainly rather than hidden)
---------------------------------------------------
The DBH-from-canopy-area relation ``DBH = 2.1 * sqrt(canopy_area_m2)`` is a
crude crown-projection proxy, NOT a field dendrometer measurement. It is
adequate for demonstrating the accounting chain; it is not a substitute for
measured DBH at 1.3 m breast height. ``calculate_allometric_carbon`` accepts
``measured_dbh_cm`` so a real survey can bypass the proxy entirely, and the
audit dossier reports which path was used.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Chave et al. (2014) pantropical coefficients
# --------------------------------------------------------------------------- #

#: Chave et al. (2014) Eq. 4, the pantropical height-based AGB model:
#:     AGB = 0.0673 * (WD * H * D^2) ** 0.976
#: Verified against the R BIOMASS package reference implementation.
CHAVE_PREFACTOR = 0.0673

#: Exponent of the same regression.
CHAVE_B1 = 0.976

#: Carbon mass fraction of dry woody biomass (IPCC default for tropical
#: woody biomass; the plausible range is 0.45-0.50).
CARBON_FRACTION = 0.47

#: Molecular mass ratio CO2 : C.
CO2_PER_CARBON = 44.0 / 12.0

#: Verra VM0047 §8.4: sampling error above this percentage triggers a
#: mandatory discount on gross carbon estimates.
VM0047_MAX_SAMPLING_ERROR_PCT = 15.0


class ComplianceStatus(str, Enum):
    VM0047_CONSERVATIVE_CERTIFIED = "VM0047_CONSERVATIVE_CERTIFIED"
    DISCOUNT_APPLIED = "DISCOUNT_APPLIED"
    INSUFFICIENT_PRECISION = "INSUFFICIENT_PRECISION"


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class BiomassEstimate:
    species: str
    wood_density_g_cm3: float
    dbh_source: str
    estimated_dbh_cm: float
    mean_height_m: float
    canopy_area_m2: float
    agb_kg: float
    carbon_kg: float
    co2e_metric_tons: float
    equation: str = "Chave et al. (2014) Eq.4 pantropical: AGB = 0.0673*(WD*H*D^2)^0.976"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class UncertaintyDiscount:
    gross_tco2e: float
    sampling_error_pct: float
    discount_applied_pct: float
    net_certified_tco2e: float
    compliance_status: ComplianceStatus

    def to_dict(self) -> dict:
        d = asdict(self)
        d["compliance_status"] = self.compliance_status.value
        return d


# --------------------------------------------------------------------------- #
# Allometry
# --------------------------------------------------------------------------- #


def estimate_dbh_from_canopy(area_m2: float, wood_density_g_cm3: float = 0.58) -> float:
    """Crude crown-projection proxy for equivalent DBH, in centimetres.

    Flagged in the module docstring as a proxy. Prefer measured DBH.
    """
    return 2.1 * math.sqrt(max(area_m2, 0.0))


def calculate_allometric_carbon(
    canopy_area_m2: float,
    mean_height_m: float,
    wood_density_g_cm3: float = 0.58,
    species_name: str = "Acacia tortilis",
    measured_dbh_cm: Optional[float] = None,
    stand_area_ha: Optional[float] = None,
    stems_per_hectare: Optional[int] = None,
) -> BiomassEstimate:
    """Convert canopy geometry to tonnes of CO2 equivalent for one stem.

    Args:
        canopy_area_m2: Crown projection area, square metres.
        mean_height_m: Crown height, metres.
        wood_density_g_cm3: Species wood density. Pantropical mean 0.58.
        species_name: For the audit record.
        measured_dbh_cm: If a field survey measured DBH at 1.3 m, pass it and
            the crown-projection proxy is bypassed.
        stand_area_ha: If given with ``stems_per_hectare``, a per-hectare
            figure is computed and returned in ``co2e_metric_tons`` instead of
            the per-stem value.
        stems_per_hectare: Stem density from the sampling design.

    Returns:
        A :class:`BiomassEstimate`. ``co2e_metric_tons`` is per stem unless
        both ``stand_area_ha`` and ``stems_per_hectare`` are supplied, in which
        case it is per hectare.
    """
    if canopy_area_m2 < 0:
        raise ValueError(f"canopy_area_m2 must be >= 0, got {canopy_area_m2}")
    if mean_height_m <= 0:
        raise ValueError(f"mean_height_m must be > 0, got {mean_height_m}")
    if wood_density_g_cm3 <= 0:
        raise ValueError(f"wood_density_g_cm3 must be > 0, got {wood_density_g_cm3}")

    if measured_dbh_cm is not None:
        dbh_cm = float(measured_dbh_cm)
        dbh_source = "field_measured_dbh_1.3m"
        if dbh_cm <= 0:
            raise ValueError(f"measured_dbh_cm must be > 0, got {measured_dbh_cm}")
    else:
        dbh_cm = estimate_dbh_from_canopy(canopy_area_m2, wood_density_g_cm3)
        dbh_source = "crown_projection_proxy_2.1*sqrt(area_m2)"

    # Chave et al. (2014) Eq. 4: AGB[kg] = 0.0673 * (WD*H*D^2)^0.976
    db_term = wood_density_g_cm3 * (dbh_cm**2) * mean_height_m
    agb_kg = CHAVE_PREFACTOR * (db_term**CHAVE_B1)

    carbon_kg = agb_kg * CARBON_FRACTION
    co2e_kg = carbon_kg * CO2_PER_CARBON
    co2e_t = co2e_kg / 1000.0

    if stand_area_ha is not None and stems_per_hectare is not None:
        co2e_t = co2e_t * stems_per_hectare * stand_area_ha

    return BiomassEstimate(
        species=species_name,
        wood_density_g_cm3=round(wood_density_g_cm3, 4),
        dbh_source=dbh_source,
        estimated_dbh_cm=round(dbh_cm, 2),
        mean_height_m=round(mean_height_m, 2),
        canopy_area_m2=round(canopy_area_m2, 2),
        agb_kg=round(agb_kg, 2),
        carbon_kg=round(carbon_kg, 2),
        co2e_metric_tons=round(co2e_t, 4),
    )


# --------------------------------------------------------------------------- #
# Verra VM0047 §8.4 uncertainty
# --------------------------------------------------------------------------- #


def sampling_error_pct(sample_mean: float, sample_std: float, n: int) -> float:
    """Relative sampling error at the 90% confidence interval.

    ``E = (t_{0.90, n-1} * s) / (sqrt(n) * mean) * 100``

    The t-statistic is taken from a two-sided 90% Student-t table, i.e. the
    95th percentile, which is the convention Verra uses.
    """
    if n < 2:
        raise ValueError(f"need n >= 2 to estimate sampling error, got n={n}")
    if sample_mean == 0:
        raise ValueError("sample_mean is zero; relative error is undefined")
    t_stat = _student_t_95(n - 1)
    return (t_stat * sample_std) / (math.sqrt(n) * sample_mean) * 100.0


def _student_t_95(df: int) -> float:
    """Two-sided 95% Student-t critical value (the 90% CI convention).

    Exact via scipy when available, otherwise a Cornish-Fisher expansion
    against the normal quantile, which is accurate to well under 1% for
    df >= 5 and is the only reason this fallback exists.
    """
    try:
        from scipy import stats  # noqa: PLC0415

        return float(stats.t.ppf(0.95, df))
    except Exception:  # pragma: no cover - scipy is pinned, this is a guard
        return _student_t_95_cornish_fisher(df)


def _student_t_95_cornish_fisher(df: int) -> float:
    z = 1.6448536269514722  # Phi^-1(0.95)
    g1 = (z**3 + z) / 4.0
    g2 = (5.0 * z**5 + 16.0 * z**3 + 3.0 * z) / 96.0
    g3 = (3.0 * z**7 + 19.0 * z**5 + 17.0 * z**3 - 15.0 * z) / 384.0
    g4 = (
        79.0 * z**9 + 776.0 * z**7 + 1482.0 * z**5 - 1920.0 * z**3 - 945.0 * z
    ) / 92160.0
    return z + g1 / df + g2 / df**2 + g3 / df**3 + g4 / df**4


def apply_vm0047_uncertainty_discount(
    gross_tco2e: float,
    sampling_error_pct: float,
    max_sampling_error_pct: float = VM0047_MAX_SAMPLING_ERROR_PCT,
) -> UncertaintyDiscount:
    """Apply the mandatory VM0047 §8.4 discount for imprecise sampling.

    ``discount = max(0, (E_sampling - 15%) / 100%)``
    ``net = gross * (1 - discount)``
    """
    if sampling_error_pct < 0:
        raise ValueError(f"sampling_error_pct must be >= 0, got {sampling_error_pct}")

    discount_rate = max(0.0, (sampling_error_pct - max_sampling_error_pct) / 100.0)
    net = gross_tco2e * (1.0 - discount_rate)

    if sampling_error_pct > max_sampling_error_pct * 1.5:
        status = ComplianceStatus.INSUFFICIENT_PRECISION
    elif discount_rate > 0.0:
        status = ComplianceStatus.DISCOUNT_APPLIED
    else:
        status = ComplianceStatus.VM0047_CONSERVATIVE_CERTIFIED

    return UncertaintyDiscount(
        gross_tco2e=round(gross_tco2e, 4),
        sampling_error_pct=round(sampling_error_pct, 2),
        discount_applied_pct=round(discount_rate * 100.0, 2),
        net_certified_tco2e=round(net, 4),
        compliance_status=status,
    )
