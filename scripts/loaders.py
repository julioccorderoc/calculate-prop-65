"""Input parsing: CLI ingredient triplets and JSON ingredients files.

This module is library code: it knows about :class:`Ingredient` and the
:class:`Formula` schema but it does not know about argparse or any other
CLI framework. Errors are surfaced as plain ``ValueError`` — CLI callers
catch these and translate them into ``argparse`` errors at their layer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from .models import Ingredient
from .schema import Formula


def _parse_float(value: str, field_name: str, ingredient_name: str) -> float:
    """Convert a CLI string to float or raise a clear ValueError.

    DRY helper: the original inlined nearly-identical try/except blocks for
    every numeric field on the --ingredient triplet.
    """
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid {field_name} value '{value}' for ingredient '{ingredient_name}'."
        ) from exc


def parse_ingredient_triplet(triplet: Sequence[str]) -> Ingredient:
    """Convert a ``--ingredient NAME PPM MG`` CLI triplet into an Ingredient.

    Raises ``ValueError`` on non-numeric ppm or mg values. Callers that want
    to convert these into argparse errors can catch ``ValueError`` and
    forward the message to ``parser.error``.
    """
    name, ppm_str, mg_str = triplet
    lead_ppm = _parse_float(ppm_str, "ppm", name)
    mg_per_capsule = _parse_float(mg_str, "mg_per_capsule", name)
    return Ingredient(name=name, lead_ppm=lead_ppm, mg_per_capsule=mg_per_capsule)


def load_formula_file(path: Path) -> Formula:
    """Load an ingredients-file JSON and return a :class:`Formula`.

    Raises ``ValueError`` on malformed input (missing keys, non-list
    ingredients, non-numeric values) with messages that name the offending
    field. Raises ``OSError`` on I/O failure and ``json.JSONDecodeError``
    (a ``ValueError`` subclass) on invalid JSON.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    return Formula.from_dict(data)


def load_ingredients_file(path: Path) -> tuple[list[Ingredient], dict]:
    """Backwards-compatible loader: returns ``(ingredients, overrides)``.

    Preserved for the CLI and any external callers that predate the
    :class:`Formula` type. Internally this just unpacks a
    :meth:`load_formula_file` result, so both entry points share their
    validation behaviour.
    """
    formula = load_formula_file(path)
    return list(formula.ingredients), formula.overrides()
