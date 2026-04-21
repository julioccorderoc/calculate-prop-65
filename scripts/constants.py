"""Regulatory constants and shared styling for the Prop 65 lead calculator."""

from __future__ import annotations

#: California Prop 65 Maximum Allowable Dose Level for lead, in µg/day.
#: Source: Title 27 CCR § 25805, reproductive-toxicity endpoint. Products
#: exposing a consumer at or above this level require a Prop 65 warning for
#: California sales.
MADL_LEAD_UG_PER_DAY: float = 0.5

#: Fraction of the MADL at which we classify exposure as "CAUTION".
#: Below this → SAFE. This threshold mirrors the 40%-of-MADL internal release
#: target already recommended for at-risk NCL products such as Level Off.
CAUTION_THRESHOLD_FRACTION: float = 0.40

#: Fraction of the MADL at which we classify exposure as "HIGH RISK".
#: Above 80% of MADL, ±10% ICP-MS analytical variability can push a future
#: lot over the limit, so the product must be treated as imminent-risk.
HIGH_RISK_THRESHOLD_FRACTION: float = 0.80

#: Rich style strings applied to each qualitative risk level in the console
#: renderer. Kept next to the threshold constants so the whole risk taxonomy
#: lives in one module.
RISK_STYLES: dict[str, str] = {
    "SAFE":       "bold green",
    "CAUTION":    "bold yellow",
    "HIGH RISK":  "bold dark_orange",
    "OVER LIMIT": "bold red",
}
