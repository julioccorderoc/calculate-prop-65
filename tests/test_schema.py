from __future__ import annotations

import pytest

from scripts import Formula, Ingredient, MADL_LEAD_UG_PER_DAY


# ---------------------------------------------------------------------------
# Formula.from_dict — validation
# ---------------------------------------------------------------------------


def test_from_dict_happy_path() -> None:
    formula = Formula.from_dict(
        {
            "capsules_per_day": 2,
            "madl_ug_per_day": 0.5,
            "ingredients": [
                {"name": "A", "lead_ppm": 0.5, "mg_per_capsule": 200},
                {"name": "B", "lead_ppm": 0.1, "mg_per_capsule": 100},
            ],
        }
    )
    assert formula.capsules_per_day == 2
    assert formula.madl_ug_per_day == 0.5
    assert len(formula.ingredients) == 2
    assert formula.ingredients[0].name == "A"


def test_from_dict_defaults_madl_when_absent() -> None:
    formula = Formula.from_dict(
        {"ingredients": [{"name": "A", "lead_ppm": 0.1, "mg_per_capsule": 100}]}
    )
    assert formula.madl_ug_per_day == MADL_LEAD_UG_PER_DAY
    assert formula.capsules_per_day is None


def test_from_dict_raises_when_ingredients_missing() -> None:
    with pytest.raises(ValueError, match="ingredients"):
        Formula.from_dict({"capsules_per_day": 2})


def test_from_dict_raises_when_ingredients_not_a_list() -> None:
    with pytest.raises(ValueError, match="ingredients"):
        Formula.from_dict({"ingredients": "nope"})


def test_from_dict_raises_when_ingredient_entry_missing_name() -> None:
    with pytest.raises(ValueError, match="name"):
        Formula.from_dict(
            {"ingredients": [{"lead_ppm": 0.1, "mg_per_capsule": 100}]}
        )


def test_from_dict_raises_when_ingredient_missing_lead_ppm_with_name_in_message() -> None:
    with pytest.raises(ValueError, match="Alpha") as excinfo:
        Formula.from_dict(
            {"ingredients": [{"name": "Alpha", "mg_per_capsule": 100}]}
        )
    assert "lead_ppm" in str(excinfo.value)


def test_from_dict_raises_on_non_numeric_lead_ppm_naming_ingredient() -> None:
    with pytest.raises(ValueError, match="Beta") as excinfo:
        Formula.from_dict(
            {
                "ingredients": [
                    {"name": "Beta", "lead_ppm": "not a number", "mg_per_capsule": 100}
                ]
            }
        )
    assert "lead_ppm" in str(excinfo.value)


def test_from_dict_raises_on_non_numeric_capsules_per_day() -> None:
    with pytest.raises(ValueError, match="capsules_per_day"):
        Formula.from_dict(
            {
                "capsules_per_day": "two",
                "ingredients": [
                    {"name": "A", "lead_ppm": 0.1, "mg_per_capsule": 100}
                ],
            }
        )


# ---------------------------------------------------------------------------
# Round-trip invariant: Formula.from_dict(f.to_dict()) == f
# ---------------------------------------------------------------------------


def test_round_trip_with_all_fields_set() -> None:
    f = Formula(
        ingredients=(
            Ingredient(name="A", lead_ppm=0.5, mg_per_capsule=200.0),
            Ingredient(name="B", lead_ppm=0.1, mg_per_capsule=100.0),
        ),
        capsules_per_day=2,
        madl_ug_per_day=0.5,
    )
    assert Formula.from_dict(f.to_dict()) == f


def test_round_trip_without_capsules_per_day() -> None:
    f = Formula(
        ingredients=(Ingredient(name="A", lead_ppm=0.1, mg_per_capsule=100.0),),
    )
    round_tripped = Formula.from_dict(f.to_dict())
    assert round_tripped == f
    assert round_tripped.capsules_per_day is None


def test_round_trip_with_non_default_madl() -> None:
    f = Formula(
        ingredients=(Ingredient(name="A", lead_ppm=0.1, mg_per_capsule=100.0),),
        capsules_per_day=1,
        madl_ug_per_day=1.5,
    )
    assert Formula.from_dict(f.to_dict()) == f


# ---------------------------------------------------------------------------
# overrides() — backwards-compat helper used by load_ingredients_file
# ---------------------------------------------------------------------------


def test_overrides_includes_capsules_per_day_when_set() -> None:
    f = Formula(
        ingredients=(Ingredient(name="A", lead_ppm=0.1, mg_per_capsule=100.0),),
        capsules_per_day=2,
    )
    assert f.overrides() == {"capsules_per_day": 2}


def test_overrides_excludes_madl_when_at_default() -> None:
    f = Formula(
        ingredients=(Ingredient(name="A", lead_ppm=0.1, mg_per_capsule=100.0),),
        capsules_per_day=2,
        madl_ug_per_day=MADL_LEAD_UG_PER_DAY,
    )
    assert "madl_ug_per_day" not in f.overrides()


def test_overrides_includes_madl_when_differs_from_default() -> None:
    f = Formula(
        ingredients=(Ingredient(name="A", lead_ppm=0.1, mg_per_capsule=100.0),),
        capsules_per_day=2,
        madl_ug_per_day=1.0,
    )
    assert f.overrides() == {"capsules_per_day": 2, "madl_ug_per_day": 1.0}


def test_overrides_empty_when_nothing_set() -> None:
    f = Formula(
        ingredients=(Ingredient(name="A", lead_ppm=0.1, mg_per_capsule=100.0),),
    )
    assert f.overrides() == {}
