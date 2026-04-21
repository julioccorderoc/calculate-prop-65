"""Serialisation schema: :class:`Formula` is the canonical input shape.

A :class:`Formula` bundles the three pieces of data needed to run a
calculation: the ingredient list, the daily capsule count, and the MADL
reference. It is symmetric — :meth:`Formula.from_dict` and
:meth:`Formula.to_dict` round-trip the ingredient-file JSON schema.

The richer report emitted by :meth:`ExposureResult.to_dict` wraps a
``Formula.to_dict()`` under its ``"inputs"`` key, so the input schema is
defined in exactly one place.

JSON schema (stable — changing it requires updating SKILL.md and fixtures)::

    {
      "capsules_per_day": <int, optional>,
      "madl_ug_per_day":  <float, optional>,
      "ingredients": [
        {"name": <str>, "lead_ppm": <float>, "mg_per_capsule": <float>},
        ...
      ]
    }
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .constants import MADL_LEAD_UG_PER_DAY
from .models import Ingredient


def _coerce_number(value: Any, field_name: str, ingredient_name: str) -> float:
    """Convert a JSON value to float or raise ValueError naming the field."""
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid {field_name} value '{value!r}' for ingredient "
            f"'{ingredient_name}'."
        ) from exc


def _ingredient_from_entry(entry: Mapping[str, Any], index: int) -> Ingredient:
    """Build an Ingredient from a single JSON ingredient entry.

    Raises ``ValueError`` with messages that name the offending field and
    ingredient, matching the original ``load_ingredients_file`` behaviour.
    """
    if not isinstance(entry, Mapping):
        raise ValueError(
            f"Ingredient entry at index {index} must be an object, got "
            f"{type(entry).__name__}."
        )
    # Provide a friendly default name so downstream error messages are
    # never empty (users occasionally omit ``name`` by mistake).
    name = entry.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError(
            f"Ingredient entry at index {index} is missing a string 'name'."
        )
    for required in ("lead_ppm", "mg_per_capsule"):
        if required not in entry:
            raise ValueError(
                f"Ingredient '{name}' is missing required field '{required}'."
            )
    lead_ppm = _coerce_number(entry["lead_ppm"], "lead_ppm", name)
    mg_per_capsule = _coerce_number(entry["mg_per_capsule"], "mg_per_capsule", name)
    return Ingredient(name=name, lead_ppm=lead_ppm, mg_per_capsule=mg_per_capsule)


@dataclass(frozen=True, slots=True)
class Formula:
    """Canonical input bundle for a Prop 65 lead calculation.

    ``capsules_per_day`` may be ``None`` when loaded from a file that does
    not set it — the CLI layer then requires the user to pass ``-c`` on the
    command line. ``madl_ug_per_day`` defaults to the Prop 65 lead MADL.
    """

    ingredients: tuple[Ingredient, ...]
    capsules_per_day: int | None = None
    madl_ug_per_day: float = MADL_LEAD_UG_PER_DAY

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Formula":
        """Parse the input-file JSON schema into a :class:`Formula`.

        Raises ``ValueError`` on malformed input with messages that name the
        offending field (and ingredient where applicable).
        """
        if not isinstance(data, Mapping):
            raise ValueError(
                f"Formula payload must be a JSON object, got {type(data).__name__}."
            )
        raw_ingredients = data.get("ingredients")
        if not isinstance(raw_ingredients, list):
            raise ValueError("ingredients file must contain an 'ingredients' list.")

        ingredients = tuple(
            _ingredient_from_entry(entry, index)
            for index, entry in enumerate(raw_ingredients)
        )

        capsules_per_day: int | None = None
        if "capsules_per_day" in data:
            raw = data["capsules_per_day"]
            try:
                capsules_per_day = int(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid capsules_per_day value '{raw!r}' (expected integer)."
                ) from exc

        madl_ug_per_day = MADL_LEAD_UG_PER_DAY
        if "madl_ug_per_day" in data:
            raw = data["madl_ug_per_day"]
            try:
                madl_ug_per_day = float(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid madl_ug_per_day value '{raw!r}' (expected number)."
                ) from exc

        return cls(
            ingredients=ingredients,
            capsules_per_day=capsules_per_day,
            madl_ug_per_day=madl_ug_per_day,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialise to the input-file JSON schema.

        Only includes ``capsules_per_day`` when it is set, so a
        round-tripped Formula built without that field does not acquire a
        synthesised ``None``.
        """
        payload: dict[str, Any] = {
            "madl_ug_per_day": self.madl_ug_per_day,
            "ingredients": [
                {
                    "name":           i.name,
                    "lead_ppm":       i.lead_ppm,
                    "mg_per_capsule": i.mg_per_capsule,
                }
                for i in self.ingredients
            ],
        }
        if self.capsules_per_day is not None:
            # Preserve key ordering so to_dict output reads top-down like
            # the hand-written reference fixtures.
            payload = {"capsules_per_day": self.capsules_per_day, **payload}
        return payload

    def overrides(self) -> dict[str, Any]:
        """Return a dict of the CLI-overrideable fields that are set.

        Used by the backwards-compatible ``load_ingredients_file`` wrapper
        which promised a ``(ingredients, overrides)`` return value.
        """
        out: dict[str, Any] = {}
        if self.capsules_per_day is not None:
            out["capsules_per_day"] = self.capsules_per_day
        # Only surface madl_ug_per_day if it differs from the default —
        # preserving the original behaviour where an omitted field yielded
        # an empty overrides dict.
        if self.madl_ug_per_day != MADL_LEAD_UG_PER_DAY:
            out["madl_ug_per_day"] = self.madl_ug_per_day
        return out


# Convenience helpers ---------------------------------------------------------


def ingredients_to_input_payload(
    ingredients: Sequence[Ingredient],
    capsules_per_day: int,
    madl_ug_per_day: float,
) -> dict[str, Any]:
    """Serialise inputs using the :class:`Formula` schema.

    Used by :meth:`ExposureResult.to_dict` so the ``"inputs"`` section of a
    full report always matches the input-file schema exactly.
    """
    return Formula(
        ingredients=tuple(ingredients),
        capsules_per_day=capsules_per_day,
        madl_ug_per_day=madl_ug_per_day,
    ).to_dict()
