"""Input parsing: CLI ingredient triplets and JSON ingredients files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .models import Ingredient


def _parse_float(value: str, field_name: str, ingredient_name: str) -> float:
    """Convert a CLI string to float or raise a clear argparse error.

    DRY helper: the original inlined nearly-identical try/except blocks for
    every numeric field on the --ingredient triplet.
    """
    try:
        return float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid {field_name} value '{value}' for ingredient '{ingredient_name}'."
        ) from exc


def parse_ingredient_triplet(triplet: Sequence[str]) -> Ingredient:
    """Convert a ``--ingredient NAME PPM MG`` CLI triplet into an Ingredient."""
    name, ppm_str, mg_str = triplet
    lead_ppm = _parse_float(ppm_str, "ppm", name)
    mg_per_capsule = _parse_float(mg_str, "mg_per_capsule", name)
    return Ingredient(name=name, lead_ppm=lead_ppm, mg_per_capsule=mg_per_capsule)


def load_ingredients_file(path: Path) -> tuple[list[Ingredient], dict]:
    """Load an ``--ingredients-file`` JSON and return (ingredients, overrides).

    Overrides is a dict with any of ``capsules_per_day`` or ``madl_ug_per_day``
    that were set in the file. Raises on malformed input.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if "ingredients" not in data or not isinstance(data["ingredients"], list):
        raise ValueError("ingredients file must contain an 'ingredients' list.")
    ingredients = [
        Ingredient(
            name=entry["name"],
            lead_ppm=float(entry["lead_ppm"]),
            mg_per_capsule=float(entry["mg_per_capsule"]),
        )
        for entry in data["ingredients"]
    ]
    overrides = {
        key: data[key]
        for key in ("capsules_per_day", "madl_ug_per_day")
        if key in data
    }
    return ingredients, overrides
