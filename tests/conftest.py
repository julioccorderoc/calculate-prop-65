from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

from scripts import Ingredient, calculate_lead_exposure
from scripts.models import ExposureResult


@pytest.fixture
def sample_ingredient() -> Ingredient:
    return Ingredient(name="Sample Botanical", lead_ppm=0.5, mg_per_capsule=200.0)


@pytest.fixture
def level_off_ingredients() -> list[Ingredient]:
    return [
        Ingredient(name="White Mulberry Leaf", lead_ppm=0.60, mg_per_capsule=250.0),
        Ingredient(name="Cinnamon Cassia 12:1", lead_ppm=0.80, mg_per_capsule=85.0),
        Ingredient(name="Veggie Blend", lead_ppm=0.40, mg_per_capsule=180.0),
    ]


@pytest.fixture
def level_off_result(level_off_ingredients: list[Ingredient]) -> ExposureResult:
    return calculate_lead_exposure(
        ingredients=level_off_ingredients,
        capsules_per_day=2,
    )


@pytest.fixture
def tmp_ingredients_file(tmp_path: Path) -> Callable[[dict | str], Path]:
    """Factory: write a dict (as JSON) or raw string to a temp file, return its Path."""

    counter = {"n": 0}

    def _write(payload: dict | str) -> Path:
        counter["n"] += 1
        file_path = tmp_path / f"ingredients_{counter['n']}.json"
        if isinstance(payload, str):
            file_path.write_text(payload, encoding="utf-8")
        else:
            file_path.write_text(json.dumps(payload), encoding="utf-8")
        return file_path

    return _write


@pytest.fixture
def reference_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "reference"
