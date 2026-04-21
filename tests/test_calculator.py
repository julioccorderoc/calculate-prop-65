from __future__ import annotations

import pytest

from scripts import Ingredient, MADL_LEAD_UG_PER_DAY, calculate_lead_exposure
from scripts.models import ExposureResult


def test_happy_path_returns_expected_lead_ug_per_day() -> None:
    ingredients = [
        Ingredient(name="White Mulberry Leaf", lead_ppm=0.60, mg_per_capsule=250.0),
        Ingredient(name="Cinnamon Cassia 12:1", lead_ppm=0.80, mg_per_capsule=85.0),
        Ingredient(name="Veggie Blend", lead_ppm=0.40, mg_per_capsule=180.0),
    ]
    result = calculate_lead_exposure(ingredients=ingredients, capsules_per_day=2)
    assert isinstance(result, ExposureResult)
    # (0.60*250 + 0.80*85 + 0.40*180) / 1000 * 2 = 0.580
    assert result.lead_ug_per_day == pytest.approx(0.580)


def test_empty_ingredient_list_raises() -> None:
    with pytest.raises(ValueError, match="ingredient"):
        calculate_lead_exposure(ingredients=[], capsules_per_day=2)


@pytest.mark.parametrize("capsules_per_day", [0, -1, -5])
def test_non_positive_capsules_per_day_raises(capsules_per_day: int) -> None:
    ingredient = Ingredient(name="A", lead_ppm=0.1, mg_per_capsule=100.0)
    with pytest.raises(ValueError, match="capsules_per_day"):
        calculate_lead_exposure(
            ingredients=[ingredient], capsules_per_day=capsules_per_day
        )


def test_zero_madl_raises() -> None:
    ingredient = Ingredient(name="A", lead_ppm=0.1, mg_per_capsule=100.0)
    with pytest.raises(ValueError, match="madl"):
        calculate_lead_exposure(
            ingredients=[ingredient], capsules_per_day=2, madl_ug_per_day=0.0
        )


def test_negative_lead_ppm_raises_with_ingredient_name_in_message() -> None:
    ingredient = Ingredient(name="Bad Botanical", lead_ppm=-0.1, mg_per_capsule=100.0)
    with pytest.raises(ValueError, match="Bad Botanical"):
        calculate_lead_exposure(ingredients=[ingredient], capsules_per_day=2)


def test_negative_mg_per_capsule_raises_with_ingredient_name_in_message() -> None:
    ingredient = Ingredient(name="Odd Filler", lead_ppm=0.1, mg_per_capsule=-50.0)
    with pytest.raises(ValueError, match="Odd Filler"):
        calculate_lead_exposure(ingredients=[ingredient], capsules_per_day=2)


def test_default_madl_equals_prop65_lead_madl() -> None:
    ingredient = Ingredient(name="A", lead_ppm=0.1, mg_per_capsule=100.0)
    result = calculate_lead_exposure(ingredients=[ingredient], capsules_per_day=2)
    assert result.madl_ug_per_day == MADL_LEAD_UG_PER_DAY
    assert MADL_LEAD_UG_PER_DAY == 0.5
