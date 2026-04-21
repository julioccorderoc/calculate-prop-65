"""Domain model: Ingredient and ExposureResult dataclasses."""

from __future__ import annotations

from dataclasses import dataclass

from .constants import (
    CAUTION_THRESHOLD_FRACTION,
    HIGH_RISK_THRESHOLD_FRACTION,
    MADL_LEAD_UG_PER_DAY,
)


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
    """

    name: str
    lead_ppm: float
    mg_per_capsule: float

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
    """

    ingredients: tuple[Ingredient, ...]
    capsules_per_day: int
    madl_ug_per_day: float = MADL_LEAD_UG_PER_DAY

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
    def risk_level(self) -> str:
        """Four-zone qualitative classification of the daily exposure."""
        fraction = self.lead_ug_per_day / self.madl_ug_per_day
        if fraction >= 1.0:
            return "OVER LIMIT"
        if fraction >= HIGH_RISK_THRESHOLD_FRACTION:
            return "HIGH RISK"
        if fraction >= CAUTION_THRESHOLD_FRACTION:
            return "CAUTION"
        return "SAFE"

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
        """JSON-friendly dict representation of inputs + outputs."""
        return {
            "inputs": {
                "capsules_per_day": self.capsules_per_day,
                "madl_ug_per_day":  self.madl_ug_per_day,
                "ingredients": [
                    {
                        "name":           i.name,
                        "lead_ppm":       i.lead_ppm,
                        "mg_per_capsule": i.mg_per_capsule,
                    }
                    for i in self.ingredients
                ],
            },
            "outputs": {
                "lead_ug_per_capsule": self.lead_ug_per_capsule,
                "lead_ug_per_day":     self.lead_ug_per_day,
                "percent_of_madl":     self.percent_of_madl,
                "exceeds_madl":        self.exceeds_madl,
                "risk_level":          self.risk_level,
                "breakdown":           self.ingredient_breakdown(),
            },
        }
