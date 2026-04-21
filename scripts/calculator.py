"""Pure calculation core — the only function a library consumer needs."""

from __future__ import annotations

from typing import Sequence

from .constants import MADL_LEAD_UG_PER_DAY
from .models import ExposureResult, Ingredient


def _validate_inputs(
    ingredients: Sequence[Ingredient],
    capsules_per_day: int,
    madl_ug_per_day: float,
) -> None:
    """Raise ``ValueError`` if any input violates the calculator's contract."""
    if not ingredients:
        raise ValueError("At least one ingredient is required.")
    if capsules_per_day <= 0:
        raise ValueError("capsules_per_day must be a positive integer.")
    if madl_ug_per_day <= 0:
        raise ValueError("madl_ug_per_day must be positive.")

    for ingredient in ingredients:
        if ingredient.lead_ppm < 0:
            raise ValueError(
                f"Negative lead_ppm for ingredient '{ingredient.name}'."
            )
        if ingredient.mg_per_capsule < 0:
            raise ValueError(
                f"Negative mg_per_capsule for ingredient '{ingredient.name}'."
            )


def calculate_lead_exposure(
    ingredients: Sequence[Ingredient],
    capsules_per_day: int,
    madl_ug_per_day: float = MADL_LEAD_UG_PER_DAY,
) -> ExposureResult:
    """Compute the Prop 65 lead exposure for a capsule formulation.

    Parameters
    ----------
    ingredients:
        One or more raw materials in the capsule. Each ingredient contributes
        ``lead_ppm × (mg_per_capsule / 1000)`` µg of lead to one capsule.
    capsules_per_day:
        Maximum daily capsule count per the product label
        (e.g. "Take 1 capsule twice daily" → 2).
    madl_ug_per_day:
        Reference limit in µg/day. Defaults to the Prop 65 lead MADL (0.5).
        Override only for other heavy metals or research scenarios.

    Returns
    -------
    ExposureResult
        Structured result exposing per-capsule / per-day / percent-of-MADL
        values, a qualitative risk level, and a per-ingredient breakdown.

    Raises
    ------
    ValueError
        If ``ingredients`` is empty, ``capsules_per_day`` is not positive,
        or any input value is negative.
    """
    _validate_inputs(ingredients, capsules_per_day, madl_ug_per_day)

    return ExposureResult(
        ingredients=tuple(ingredients),
        capsules_per_day=capsules_per_day,
        madl_ug_per_day=madl_ug_per_day,
    )
