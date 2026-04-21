from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from scripts import Ingredient, MADL_LEAD_UG_PER_DAY
from scripts.models import ExposureResult


@pytest.mark.parametrize(
    ("lead_ppm", "mg_per_capsule", "expected_ug"),
    [
        (0.0, 500.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1000.0, 1.0),
        (0.5, 200.0, 0.1),
        (0.3604, 600.0, 0.21624),
        (2.5, 500.0, 1.25),
    ],
)
def test_ingredient_lead_ug_per_capsule_computes_ppm_times_mg_over_1000(
    lead_ppm: float, mg_per_capsule: float, expected_ug: float
) -> None:
    ingredient = Ingredient(name="X", lead_ppm=lead_ppm, mg_per_capsule=mg_per_capsule)
    assert ingredient.lead_ug_per_capsule == pytest.approx(expected_ug)


def test_ingredient_is_frozen() -> None:
    ingredient = Ingredient(name="X", lead_ppm=0.1, mg_per_capsule=100.0)
    with pytest.raises((FrozenInstanceError, AttributeError)):
        ingredient.name = "Y"  # type: ignore[misc]


def test_exposure_result_lead_ug_per_capsule_sums_ingredient_contributions() -> None:
    ingredients = (
        Ingredient(name="A", lead_ppm=0.60, mg_per_capsule=250.0),
        Ingredient(name="B", lead_ppm=0.80, mg_per_capsule=85.0),
        Ingredient(name="C", lead_ppm=0.40, mg_per_capsule=180.0),
    )
    result = ExposureResult(ingredients=ingredients, capsules_per_day=2)
    # 0.150 + 0.068 + 0.072 = 0.290
    assert result.lead_ug_per_capsule == pytest.approx(0.290)


def test_exposure_result_lead_ug_per_day_is_per_capsule_times_capsules() -> None:
    ingredients = (Ingredient(name="A", lead_ppm=1.0, mg_per_capsule=100.0),)
    result = ExposureResult(ingredients=ingredients, capsules_per_day=3)
    assert result.lead_ug_per_day == pytest.approx(result.lead_ug_per_capsule * 3)
    assert result.lead_ug_per_day == pytest.approx(0.3)


def test_exposure_result_percent_of_madl_honors_non_default_madl() -> None:
    ingredients = (Ingredient(name="A", lead_ppm=1.0, mg_per_capsule=100.0),)
    # 0.1 ug/cap * 2 = 0.2 ug/day. With madl=1.0, that's 20%.
    result = ExposureResult(
        ingredients=ingredients, capsules_per_day=2, madl_ug_per_day=1.0
    )
    assert result.percent_of_madl == pytest.approx(20.0)


def test_exceeds_madl_is_true_at_exactly_madl() -> None:
    ingredients = (Ingredient(name="A", lead_ppm=5.0, mg_per_capsule=100.0),)
    # 5.0 * 0.1 = 0.5 ug/cap, * 1 cap = 0.5 ug/day exactly.
    result = ExposureResult(ingredients=ingredients, capsules_per_day=1)
    assert result.lead_ug_per_day == pytest.approx(MADL_LEAD_UG_PER_DAY)
    assert result.exceeds_madl is True


def test_exceeds_madl_is_false_strictly_below_madl() -> None:
    ingredients = (Ingredient(name="A", lead_ppm=4.9, mg_per_capsule=100.0),)
    result = ExposureResult(ingredients=ingredients, capsules_per_day=1)
    assert result.exceeds_madl is False


# Boundary behavior for risk_level matters for regulatory interpretation:
# the boundary between HIGH RISK and OVER LIMIT at exactly 100% matters
# because COA lots vary +/- 10%, so inclusive vs exclusive changes the call.
@pytest.mark.parametrize(
    ("lead_ug_per_day", "madl", "expected_level"),
    [
        (0.025, 0.5, "SAFE"),         # 5% of MADL
        (0.20, 0.5, "CAUTION"),         # exactly 40% boundary
        (0.30, 0.5, "CAUTION"),         # between 40 and 80
        (0.40, 0.5, "HIGH RISK"),       # exactly 80% boundary
        (0.45, 0.5, "HIGH RISK"),       # between 80 and 100
        (0.50, 0.5, "OVER LIMIT"),      # exactly 100%
        (1.00, 0.5, "OVER LIMIT"),      # well above
    ],
)
def test_risk_level_classifies_exposure_zones(
    lead_ug_per_day: float, madl: float, expected_level: str
) -> None:
    # Construct an ingredient that yields exactly lead_ug_per_day at 1 capsule/day.
    # lead_ug_per_cap = ppm * mg / 1000 → pick ppm=lead_ug_per_day, mg=1000.
    ingredient = Ingredient(
        name="synthetic", lead_ppm=lead_ug_per_day, mg_per_capsule=1000.0
    )
    result = ExposureResult(
        ingredients=(ingredient,),
        capsules_per_day=1,
        madl_ug_per_day=madl,
    )
    assert result.risk_level == expected_level


def test_ingredient_breakdown_is_sorted_by_lead_ug_per_day_descending() -> None:
    ingredients = (
        Ingredient(name="Low", lead_ppm=0.1, mg_per_capsule=50.0),
        Ingredient(name="High", lead_ppm=1.0, mg_per_capsule=500.0),
        Ingredient(name="Mid", lead_ppm=0.5, mg_per_capsule=100.0),
    )
    result = ExposureResult(ingredients=ingredients, capsules_per_day=1)
    rows = result.ingredient_breakdown()
    names_in_order = [r["name"] for r in rows]
    assert names_in_order == ["High", "Mid", "Low"]
    values = [r["lead_ug_per_day"] for r in rows]
    assert values == sorted(values, reverse=True)


def test_ingredient_breakdown_percent_of_total_sums_to_one_hundred() -> None:
    ingredients = (
        Ingredient(name="A", lead_ppm=0.60, mg_per_capsule=250.0),
        Ingredient(name="B", lead_ppm=0.80, mg_per_capsule=85.0),
        Ingredient(name="C", lead_ppm=0.40, mg_per_capsule=180.0),
    )
    result = ExposureResult(ingredients=ingredients, capsules_per_day=2)
    rows = result.ingredient_breakdown()
    total_pct = sum(r["percent_of_total"] for r in rows)
    assert total_pct == pytest.approx(100.0)


def test_ingredient_breakdown_handles_zero_exposure_without_dividing_by_zero() -> None:
    ingredients = (
        Ingredient(name="A", lead_ppm=0.0, mg_per_capsule=250.0),
        Ingredient(name="B", lead_ppm=0.0, mg_per_capsule=100.0),
    )
    result = ExposureResult(ingredients=ingredients, capsules_per_day=2)
    rows = result.ingredient_breakdown()
    assert len(rows) == 2
    for row in rows:
        assert row["percent_of_total"] == pytest.approx(0.0)


def test_to_dict_has_inputs_and_outputs_top_level_keys() -> None:
    ingredients = (Ingredient(name="A", lead_ppm=0.5, mg_per_capsule=200.0),)
    result = ExposureResult(ingredients=ingredients, capsules_per_day=2)
    payload = result.to_dict()
    assert set(payload.keys()) == {"inputs", "outputs"}
    assert payload["inputs"]["capsules_per_day"] == 2
    assert payload["outputs"]["risk_level"] in {"SAFE", "CAUTION", "HIGH RISK", "OVER LIMIT"}


def test_to_dict_is_json_serializable() -> None:
    import json

    ingredients = (Ingredient(name="A", lead_ppm=0.5, mg_per_capsule=200.0),)
    result = ExposureResult(ingredients=ingredients, capsules_per_day=2)
    serialized = json.dumps(result.to_dict())
    assert isinstance(serialized, str)
    round_tripped = json.loads(serialized)
    assert round_tripped["inputs"]["capsules_per_day"] == 2
