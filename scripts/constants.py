"""Regulatory constants for the Prop 65 lead calculator.

Risk-zone styling and guidance text live on :class:`scripts.risk.RiskZone`
so the full risk taxonomy (threshold, display name, rich style, guidance)
is defined in one place. Only the numeric thresholds remain here so they
stay easy to audit as standalone regulatory constants.
"""

from __future__ import annotations

#: California Prop 65 Maximum Allowable Dose Level for lead, in µg/day.
#: Source: Title 27 CCR § 25805, reproductive-toxicity endpoint. Products
#: exposing a consumer at or above this level require a Prop 65 warning for
#: California sales.
MADL_LEAD_UG_PER_DAY: float = 0.5

#: Fraction of the MADL at which we classify exposure as "CAUTION".
#: Below this → SAFE. This threshold mirrors a typical 40%-of-MADL internal
#: release target used by formulators for at-risk products.
CAUTION_THRESHOLD_FRACTION: float = 0.40

#: Fraction of the MADL at which we classify exposure as "HIGH RISK".
#: Above 80% of MADL, ±10% ICP-MS analytical variability can push a future
#: lot over the limit, so the product must be treated as imminent-risk.
HIGH_RISK_THRESHOLD_FRACTION: float = 0.80
