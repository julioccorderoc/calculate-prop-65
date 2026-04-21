from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from scripts import Formula, Ingredient
from scripts.loaders import (
    load_formula_file,
    load_ingredients_file,
    parse_ingredient_triplet,
)


# ---------------------------------------------------------------------------
# parse_ingredient_triplet now raises plain ValueError (no argparse leak)
# ---------------------------------------------------------------------------


def test_parse_ingredient_triplet_returns_expected_ingredient() -> None:
    ingredient = parse_ingredient_triplet(["Mulberry Leaf", "0.5", "100"])
    assert ingredient == Ingredient(
        name="Mulberry Leaf", lead_ppm=0.5, mg_per_capsule=100.0
    )


def test_parse_ingredient_triplet_raises_value_error_on_non_numeric_ppm() -> None:
    with pytest.raises(ValueError, match="abc") as excinfo:
        parse_ingredient_triplet(["Mulberry", "abc", "100"])
    assert "Mulberry" in str(excinfo.value)


def test_parse_ingredient_triplet_raises_value_error_on_non_numeric_mg() -> None:
    with pytest.raises(ValueError, match="xyz") as excinfo:
        parse_ingredient_triplet(["Cinnamon", "0.5", "xyz"])
    assert "Cinnamon" in str(excinfo.value)


def test_parse_ingredient_triplet_propagates_negative_ppm_as_value_error() -> None:
    # Ingredient.__post_init__ raises ValueError on negative ppm; confirm
    # the loader propagates it (doesn't wrap in a different exception type).
    with pytest.raises(ValueError, match="Bad"):
        parse_ingredient_triplet(["Bad", "-1.0", "100"])


# ---------------------------------------------------------------------------
# load_ingredients_file — backwards-compatible (ingredients, overrides) API
# ---------------------------------------------------------------------------


def test_load_ingredients_file_returns_ingredients_and_overrides(
    tmp_ingredients_file: Callable[[dict | str], Path],
) -> None:
    path = tmp_ingredients_file(
        {
            "capsules_per_day": 3,
            "madl_ug_per_day": 0.5,
            "ingredients": [
                {"name": "Alpha", "lead_ppm": 0.2, "mg_per_capsule": 150},
                {"name": "Beta", "lead_ppm": 0.1, "mg_per_capsule": 100},
            ],
        }
    )
    ingredients, overrides = load_ingredients_file(path)
    assert ingredients == [
        Ingredient(name="Alpha", lead_ppm=0.2, mg_per_capsule=150.0),
        Ingredient(name="Beta", lead_ppm=0.1, mg_per_capsule=100.0),
    ]
    # madl_ug_per_day == 0.5 equals the default, so it does not surface as
    # an override — preserving the prior behaviour where the CLI only
    # needs to care about values that actually differ.
    assert overrides == {"capsules_per_day": 3}


def test_load_ingredients_file_returns_overrides_when_madl_differs_from_default(
    tmp_ingredients_file: Callable[[dict | str], Path],
) -> None:
    path = tmp_ingredients_file(
        {
            "capsules_per_day": 2,
            "madl_ug_per_day": 1.0,
            "ingredients": [{"name": "A", "lead_ppm": 0.1, "mg_per_capsule": 100}],
        }
    )
    _, overrides = load_ingredients_file(path)
    assert overrides["capsules_per_day"] == 2
    assert overrides["madl_ug_per_day"] == 1.0


def test_load_ingredients_file_returns_empty_overrides_when_absent(
    tmp_ingredients_file: Callable[[dict | str], Path],
) -> None:
    path = tmp_ingredients_file(
        {
            "ingredients": [{"name": "A", "lead_ppm": 0.1, "mg_per_capsule": 100}],
        }
    )
    _, overrides = load_ingredients_file(path)
    assert overrides == {}


def test_load_ingredients_file_raises_on_missing_ingredients_key(
    tmp_ingredients_file: Callable[[dict | str], Path],
) -> None:
    path = tmp_ingredients_file({"capsules_per_day": 2})
    with pytest.raises(ValueError, match="ingredients"):
        load_ingredients_file(path)


def test_load_ingredients_file_raises_when_ingredients_is_not_a_list(
    tmp_ingredients_file: Callable[[dict | str], Path],
) -> None:
    path = tmp_ingredients_file({"ingredients": "not a list"})
    with pytest.raises(ValueError, match="ingredients"):
        load_ingredients_file(path)


def test_load_ingredients_file_raises_on_malformed_json(
    tmp_ingredients_file: Callable[[dict | str], Path],
) -> None:
    path = tmp_ingredients_file("this is not { valid json")
    with pytest.raises(ValueError):
        load_ingredients_file(path)


def test_load_ingredients_file_on_multi_ingredient_reference(reference_dir: Path) -> None:
    ingredients, overrides = load_ingredients_file(reference_dir / "multi_ingredient.json")
    assert len(ingredients) == 3
    assert overrides["capsules_per_day"] == 2


# ---------------------------------------------------------------------------
# load_formula_file — the new Formula-returning entry point
# ---------------------------------------------------------------------------


def test_load_formula_file_returns_formula_instance(
    tmp_ingredients_file: Callable[[dict | str], Path],
) -> None:
    path = tmp_ingredients_file(
        {
            "capsules_per_day": 2,
            "ingredients": [{"name": "A", "lead_ppm": 0.1, "mg_per_capsule": 100}],
        }
    )
    formula = load_formula_file(path)
    assert isinstance(formula, Formula)
    assert formula.capsules_per_day == 2
    assert formula.ingredients == (
        Ingredient(name="A", lead_ppm=0.1, mg_per_capsule=100.0),
    )


def test_load_formula_file_on_reference_round_trips_via_to_dict(
    reference_dir: Path,
) -> None:
    formula = load_formula_file(reference_dir / "multi_ingredient.json")
    # Formula.from_dict(formula.to_dict()) == formula — reference fixture
    # survives a round-trip without data loss.
    assert Formula.from_dict(formula.to_dict()) == formula
