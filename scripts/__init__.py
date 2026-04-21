"""Prop 65 lead-exposure calculator — modular package."""

from __future__ import annotations

from .calculator import calculate_lead_exposure
from .constants import MADL_LEAD_UG_PER_DAY
from .models import ExposureResult, Ingredient

__all__ = [
    "Ingredient",
    "ExposureResult",
    "calculate_lead_exposure",
    "MADL_LEAD_UG_PER_DAY",
]
