"""Domain model: Ingredient and ExposureResult dataclasses.

Input validation lives here rather than in a separate ``calculator`` wrapper
so that constructing an invalid object is impossible — the dataclasses
enforce their own contract via ``__post_init__``. Risk classification is
delegated to :class:`scripts.risk.RiskZone`, which owns the four-zone
taxonomy (threshold, display name, rich style, guidance text).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .constants import MADL_LEAD_UG_PER_DAY
from .risk import RiskZone


@dataclass(frozen=True, slots=True)
class Ingredient:
    """A single raw material (e.g. a botanical extract) inside a capsule.

    Attributes
    ----------
    name:
        Human-readable ingredient name. Used only for labelling output.
    lead_ppm:
        Lead result from the raw-material COA, in parts per million.
        By definition, ``1 ppm == 1 µg Pb / g raw material``.
    mg_per_capsule:
        Milligrams of *this* ingredient in one capsule. (Not per serving,
        not per day — *per capsule*.)

    Field-level invariants (``lead_ppm >= 0``, ``mg_per_capsule >= 0``) are
    enforced in ``__post_init__`` so malformed ingredients never reach the
    calculator. Error messages include the ingredient name to make batch
    validation failures actionable.
    """

    name: str
    lead_ppm: float
    mg_per_capsule: float

    def __post_init__(self) -> None:
        if self.lead_ppm < 0:
            raise ValueError(f"Negative lead_ppm for ingredient '{self.name}'.")
        if self.mg_per_capsule < 0:
            raise ValueError(
                f"Negative mg_per_capsule for ingredient '{self.name}'."
            )

    @property
    def lead_ug_per_capsule(self) -> float:
        """Micrograms of lead this ingredient contributes to one capsule.

        Derivation:  (µg Pb / g extract) × (g extract / capsule).
        The factor of 1 000 converts mg → g.
        """
        grams_per_capsule = self.mg_per_capsule / 1000.0
        return self.lead_ppm * grams_per_capsule


@dataclass(frozen=True, slots=True)
class ExposureResult:
    """Outcome of a Prop 65 lead-exposure calculation for a capsule formula.

    All derived values are computed lazily from the stored inputs so the
    object is self-describing and trivially serialisable.

    Composite invariants (non-empty ``ingredients``, positive
    ``capsules_per_day``, positive ``madl_ug_per_day``) are enforced in
    ``__post_init__``; constructing an invalid ``ExposureResult`` raises
    ``ValueError``. Individual :class:`Ingredient` instances validate their
    own fields, so negative ppm/mg values never reach this layer.
    """

    ingredients: tuple[Ingredient, ...]
    capsules_per_day: int
    madl_ug_per_day: float = MADL_LEAD_UG_PER_DAY

    def __post_init__(self) -> None:
        if not self.ingredients:
            raise ValueError("At least one ingredient is required.")
        if self.capsules_per_day <= 0:
            raise ValueError("capsules_per_day must be a positive integer.")
        if self.madl_ug_per_day <= 0:
            raise ValueError("madl_ug_per_day must be positive.")

    @property
    def lead_ug_per_capsule(self) -> float:
        """Total lead (µg) contributed by all ingredients to one capsule."""
        return sum(i.lead_ug_per_capsule for i in self.ingredients)

    @property
    def lead_ug_per_day(self) -> float:
        """Total lead (µg) ingested per day at the configured capsule count."""
        return self.lead_ug_per_capsule * self.capsules_per_day

    @property
    def percent_of_madl(self) -> float:
        """Daily exposure expressed as a percentage of the MADL (0–infinity)."""
        return (self.lead_ug_per_day / self.madl_ug_per_day) * 100.0

    @property
    def exceeds_madl(self) -> bool:
        """True iff the daily exposure meets or exceeds the MADL."""
        return self.lead_ug_per_day >= self.madl_ug_per_day

    @property
    def risk_zone(self) -> RiskZone:
        """Four-zone classification as the first-class :class:`RiskZone`.

        Renderers use this to pick rich styles and guidance text. Tests
        that care about identity (rather than display string) assert on
        enum members directly.
        """
        fraction = self.lead_ug_per_day / self.madl_ug_per_day
        return RiskZone.classify(fraction)

    @property
    def risk_level(self) -> str:
        """Display-name string for the risk zone (kept for backwards compat).

        Returns one of ``"SAFE"``, ``"CAUTION"``, ``"HIGH RISK"``,
        ``"OVER LIMIT"`` — the same strings the pre-refactor implementation
        returned and that JSON/CLI consumers depend on.
        """
        return self.risk_zone.display_name

    def ingredient_breakdown(self) -> list[dict]:
        """Per-ingredient contribution rows, ordered by µg/day descending.

        Useful for identifying which raw material is the dominant lead source
        — often the leverage point for reformulation.
        """
        # Guard against div-by-zero when every ingredient reports 0 ppm lead:
        # the percent-of-total column then reads 0% across the board rather
        # than raising ZeroDivisionError.
        total_per_day = self.lead_ug_per_day or 1.0
        rows = [
            {
                "name":                ingredient.name,
                "lead_ppm":            ingredient.lead_ppm,
                "mg_per_capsule":      ingredient.mg_per_capsule,
                "lead_ug_per_capsule": ingredient.lead_ug_per_capsule,
                "lead_ug_per_day":     ingredient.lead_ug_per_capsule * self.capsules_per_day,
                "percent_of_total":    (
                    ingredient.lead_ug_per_capsule * self.capsules_per_day / total_per_day
                ) * 100.0,
            }
            for ingredient in self.ingredients
        ]
        rows.sort(key=lambda r: r["lead_ug_per_day"], reverse=True)
        return rows

    def to_dict(self) -> dict:
        """JSON-friendly dict representation of inputs + outputs.

        The ``"inputs"`` section is produced by :mod:`scripts.schema` so the
        input-file schema lives in one place: the shape here matches what
        :meth:`Formula.to_dict` emits and what :meth:`Formula.from_dict`
        accepts.
        """
        # Local import avoids a circular dependency: schema.py imports
        # Ingredient from this module.
        from .schema import ingredients_to_input_payload

        return {
            "inputs": ingredients_to_input_payload(
                ingredients=self.ingredients,
                capsules_per_day=self.capsules_per_day,
                madl_ug_per_day=self.madl_ug_per_day,
            ),
            "outputs": {
                "lead_ug_per_capsule": self.lead_ug_per_capsule,
                "lead_ug_per_day":     self.lead_ug_per_day,
                "percent_of_madl":     self.percent_of_madl,
                "exceeds_madl":        self.exceeds_madl,
                "risk_level":          self.risk_level,
                "breakdown":           self.ingredient_breakdown(),
            },
        }


def calculate_lead_exposure(
    ingredients: Sequence[Ingredient],
    capsules_per_day: int,
    madl_ug_per_day: float = MADL_LEAD_UG_PER_DAY,
) -> ExposureResult:
    """Compute the Prop 65 lead exposure for a capsule formulation.

    Thin wrapper around :class:`ExposureResult` whose constructor enforces
    all input invariants. Kept as a named function — and re-exported from
    :mod:`scripts` — because it is the documented public entry point and
    reads more naturally at a call site than ``ExposureResult(...)``.

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
        ``madl_ug_per_day`` is not positive, or any ingredient has a
        negative ``lead_ppm`` / ``mg_per_capsule`` (the last raised at
        ``Ingredient`` construction time).
    """
    return ExposureResult(
        ingredients=tuple(ingredients),
        capsules_per_day=capsules_per_day,
        madl_ug_per_day=madl_ug_per_day,
    )
