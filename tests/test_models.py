from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from scripts import (
    ExposureResult,
    Ingredient,
    MADL_LEAD_UG_PER_DAY,
    RiskZone,
    calculate_lead_exposure,
)


# ---------------------------------------------------------------------------
# Ingredient: field validation and arithmetic
# ---------------------------------------------------------------------------


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


def test_ingredient_rejects_negative_lead_ppm_with_name_in_message() -> None:
    with pytest.raises(ValueError, match="Bad Botanical"):
        Ingredient(name="Bad Botanical", lead_ppm=-0.1, mg_per_capsule=100.0)


def test_ingredient_rejects_negative_mg_per_capsule_with_name_in_message() -> None:
    with pytest.raises(ValueError, match="Odd Filler"):
        Ingredient(name="Odd Filler", lead_ppm=0.1, mg_per_capsule=-50.0)


# ---------------------------------------------------------------------------
# ExposureResult: arithmetic properties
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# ExposureResult: composite validation in __post_init__
# ---------------------------------------------------------------------------


def test_exposure_result_rejects_empty_ingredients_tuple() -> None:
    with pytest.raises(ValueError, match="ingredient"):
        ExposureResult(ingredients=(), capsules_per_day=2)


@pytest.mark.parametrize("capsules_per_day", [0, -1, -5])
def test_exposure_result_rejects_non_positive_capsules_per_day(
    capsules_per_day: int,
) -> None:
    ingredients = (Ingredient(name="A", lead_ppm=0.1, mg_per_capsule=100.0),)
    with pytest.raises(ValueError, match="capsules_per_day"):
        ExposureResult(ingredients=ingredients, capsules_per_day=capsules_per_day)


def test_exposure_result_rejects_zero_madl() -> None:
    ingredients = (Ingredient(name="A", lead_ppm=0.1, mg_per_capsule=100.0),)
    with pytest.raises(ValueError, match="madl"):
        ExposureResult(
            ingredients=ingredients, capsules_per_day=2, madl_ug_per_day=0.0
        )


# ---------------------------------------------------------------------------
# Risk zone classification — boundary semantics are load-bearing
# ---------------------------------------------------------------------------


# Boundary behavior for risk_level matters for regulatory interpretation:
# the boundary between HIGH RISK and OVER LIMIT at exactly 100% matters
# because COA lots vary +/- 10%, so inclusive vs exclusive changes the call.
@pytest.mark.parametrize(
    ("lead_ug_per_day", "madl", "expected_zone"),
    [
        (0.025, 0.5, RiskZone.SAFE),         # 5% of MADL
        (0.20, 0.5, RiskZone.CAUTION),       # exactly 40% boundary
        (0.30, 0.5, RiskZone.CAUTION),       # between 40 and 80
        (0.40, 0.5, RiskZone.HIGH_RISK),     # exactly 80% boundary
        (0.45, 0.5, RiskZone.HIGH_RISK),     # between 80 and 100
        (0.50, 0.5, RiskZone.OVER_LIMIT),    # exactly 100%
        (1.00, 0.5, RiskZone.OVER_LIMIT),    # well above
    ],
)
def test_risk_zone_classifies_exposure_zones(
    lead_ug_per_day: float, madl: float, expected_zone: RiskZone
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
    assert result.risk_zone is expected_zone
    # risk_level keeps returning the display-name string for JSON consumers.
    assert result.risk_level == expected_zone.display_name


def test_risk_level_display_names_are_preserved() -> None:
    # These strings are public-API surface: JSON consumers, SKILL.md, README.md
    # all rely on them. The enum member name may differ ("HIGH_RISK") but the
    # display string must be "HIGH RISK" with a space.
    assert RiskZone.SAFE.display_name == "SAFE"
    assert RiskZone.CAUTION.display_name == "CAUTION"
    assert RiskZone.HIGH_RISK.display_name == "HIGH RISK"
    assert RiskZone.OVER_LIMIT.display_name == "OVER LIMIT"


# ---------------------------------------------------------------------------
# ingredient_breakdown
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# to_dict — shape is public API, matches the Formula input schema
# ---------------------------------------------------------------------------


def test_to_dict_has_inputs_and_outputs_top_level_keys() -> None:
    ingredients = (Ingredient(name="A", lead_ppm=0.5, mg_per_capsule=200.0),)
    result = ExposureResult(ingredients=ingredients, capsules_per_day=2)
    payload = result.to_dict()
    assert set(payload.keys()) == {"inputs", "outputs"}
    assert payload["inputs"]["capsules_per_day"] == 2
    assert payload["outputs"]["risk_level"] in {
        "SAFE",
        "CAUTION",
        "HIGH RISK",
        "OVER LIMIT",
    }


def test_to_dict_is_json_serializable() -> None:
    import json

    ingredients = (Ingredient(name="A", lead_ppm=0.5, mg_per_capsule=200.0),)
    result = ExposureResult(ingredients=ingredients, capsules_per_day=2)
    serialized = json.dumps(result.to_dict())
    assert isinstance(serialized, str)
    round_tripped = json.loads(serialized)
    assert round_tripped["inputs"]["capsules_per_day"] == 2


def test_to_dict_inputs_section_matches_formula_schema() -> None:
    # ExposureResult.to_dict()["inputs"] is produced by Formula.to_dict() so
    # the input-file schema is defined in exactly one place.
    from scripts import Formula

    ingredients = (
        Ingredient(name="A", lead_ppm=0.5, mg_per_capsule=200.0),
        Ingredient(name="B", lead_ppm=0.1, mg_per_capsule=100.0),
    )
    result = ExposureResult(ingredients=ingredients, capsules_per_day=2)
    formula = Formula(
        ingredients=ingredients,
        capsules_per_day=2,
        madl_ug_per_day=result.madl_ug_per_day,
    )
    assert result.to_dict()["inputs"] == formula.to_dict()


# ---------------------------------------------------------------------------
# calculate_lead_exposure — the public entry-point function
# ---------------------------------------------------------------------------


def test_calculate_lead_exposure_happy_path_returns_expected_lead_ug_per_day() -> None:
    ingredients = [
        Ingredient(name="White Mulberry Leaf", lead_ppm=0.60, mg_per_capsule=250.0),
        Ingredient(name="Cinnamon Cassia 12:1", lead_ppm=0.80, mg_per_capsule=85.0),
        Ingredient(name="Veggie Blend", lead_ppm=0.40, mg_per_capsule=180.0),
    ]
    result = calculate_lead_exposure(ingredients=ingredients, capsules_per_day=2)
    assert isinstance(result, ExposureResult)
    # (0.60*250 + 0.80*85 + 0.40*180) / 1000 * 2 = 0.580
    assert result.lead_ug_per_day == pytest.approx(0.580)


def test_calculate_lead_exposure_empty_list_raises() -> None:
    with pytest.raises(ValueError, match="ingredient"):
        calculate_lead_exposure(ingredients=[], capsules_per_day=2)


@pytest.mark.parametrize("capsules_per_day", [0, -1, -5])
def test_calculate_lead_exposure_non_positive_capsules_raises(
    capsules_per_day: int,
) -> None:
    ingredient = Ingredient(name="A", lead_ppm=0.1, mg_per_capsule=100.0)
    with pytest.raises(ValueError, match="capsules_per_day"):
        calculate_lead_exposure(
            ingredients=[ingredient], capsules_per_day=capsules_per_day
        )


def test_calculate_lead_exposure_zero_madl_raises() -> None:
    ingredient = Ingredient(name="A", lead_ppm=0.1, mg_per_capsule=100.0)
    with pytest.raises(ValueError, match="madl"):
        calculate_lead_exposure(
            ingredients=[ingredient], capsules_per_day=2, madl_ug_per_day=0.0
        )


def test_calculate_lead_exposure_propagates_ingredient_validation() -> None:
    # Negative ppm/mg now raises at Ingredient construction time, so this
    # confirms the error reaches the caller with the ingredient name intact.
    with pytest.raises(ValueError, match="Bad Botanical"):
        calculate_lead_exposure(
            ingredients=[
                Ingredient(name="Bad Botanical", lead_ppm=-0.1, mg_per_capsule=100.0)
            ],
            capsules_per_day=2,
        )


def test_calculate_lead_exposure_default_madl_equals_prop65_lead_madl() -> None:
    ingredient = Ingredient(name="A", lead_ppm=0.1, mg_per_capsule=100.0)
    result = calculate_lead_exposure(ingredients=[ingredient], capsules_per_day=2)
    assert result.madl_ug_per_day == MADL_LEAD_UG_PER_DAY
    assert MADL_LEAD_UG_PER_DAY == 0.5
