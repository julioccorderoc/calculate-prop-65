"""Prop 65 lead-exposure calculator — modular package."""

from __future__ import annotations

from .constants import MADL_LEAD_UG_PER_DAY
from .models import ExposureResult, Ingredient, calculate_lead_exposure
from .risk import RiskZone
from .schema import Formula

__all__ = [
    "Ingredient",
    "ExposureResult",
    "calculate_lead_exposure",
    "MADL_LEAD_UG_PER_DAY",
    "RiskZone",
    "Formula",
]
