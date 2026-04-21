#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "rich>=13.0",
# ]
# ///
"""
Prop 65 Lead Exposure Calculator
================================

A self-contained command-line tool that takes the lead level(s) reported on
one or more raw-material Certificates of Analysis (COAs) and computes whether
a finished capsule formulation sits above or below the California
Proposition 65 Maximum Allowable Dose Level (MADL) for lead.

Regulatory background
---------------------
California Prop 65 (Title 27 CCR § 25805) sets the MADL for lead at
**0.5 µg/day** for reproductive toxicity. Products exposing a consumer at or
above that level require a Prop 65 warning for California sales. Note that
Prop 65 is *10× stricter* than the USP <232> / ICH Q3D oral Permitted Daily
Exposure of 5 µg/day typically referenced as a raw-material COA spec — so
"passes the COA spec" does not mean "passes Prop 65".

The core math
-------------
On a COA, lead is reported in parts per million:

    1 ppm  ≡  1 mg / kg  ≡  1 µg / g

So for one capsule:

    lead_µg_per_capsule = Σ over ingredients of  (ppm_i × mg_per_capsule_i / 1000)

    lead_µg_per_day     = lead_µg_per_capsule × capsules_per_day

    exceeds_MADL?       = lead_µg_per_day  ≥  0.5 µg/day

The calculation is linear and deterministic — there is no "processing loss"
factor, because the extract itself *is* the active ingredient. A single
capsule can contain multiple raw materials, each with its own COA; their
lead contributions add.

Quick start (using uv)
----------------------
Single ingredient, 2 capsules per day::

    uv run prop65_lead_calculator.py \\
        --ingredient "Loquat Leaf 10:1" 0.3604 600 \\
        --capsules-per-day 2

Multiple raw materials in one capsule (e.g. Level Off-style formula)::

    uv run prop65_lead_calculator.py \\
        --ingredient "White Mulberry Leaf" 0.60 250 \\
        --ingredient "Cinnamon Cassia 12:1" 0.80 85 \\
        --ingredient "Veggie Blend"          0.40 180 \\
        --capsules-per-day 2

Read the formula from a JSON file (useful for complex or versioned specs)::

    uv run prop65_lead_calculator.py --ingredients-file level_off.json

Machine-readable JSON output (for piping or chaining tools)::

    uv run prop65_lead_calculator.py -i "Loquat" 0.36 600 -c 2 --json

--ingredient flag format
------------------------
    --ingredient NAME  PPM  MG_PER_CAPSULE
    -i           NAME  PPM  MG_PER_CAPSULE

    NAME            any string (quote it if it contains spaces or colons;
                    e.g. "Loquat Leaf 10:1")
    PPM             lead result from the COA, in ppm (= µg Pb / g extract)
    MG_PER_CAPSULE  milligrams of this raw material per *capsule*
                    (not per serving, not per day)

Repeat --ingredient once per raw material in the capsule.

--ingredients-file JSON schema
------------------------------
    {
      "capsules_per_day": 2,
      "madl_ug_per_day":  0.5,                   // optional; defaults to 0.5
      "ingredients": [
        {"name": "Loquat Leaf 10:1",
         "lead_ppm":       0.3604,
         "mg_per_capsule": 600}
      ]
    }

CLI values (--capsules-per-day, --madl) override values from the file.

Exit codes
----------
    0  Daily exposure is below the MADL — no Prop 65 warning required.
    1  Daily exposure is at or above the MADL — warning required.
    2  Usage or input error (argparse default).

Library usage
-------------
The script is importable; the pure function is ``calculate_lead_exposure``::

    from prop65_lead_calculator import Ingredient, calculate_lead_exposure

    result = calculate_lead_exposure(
        ingredients=[
            Ingredient(name="Loquat Leaf 10:1",
                       lead_ppm=0.3604,
                       mg_per_capsule=600),
        ],
        capsules_per_day=2,
    )
    print(result.lead_ug_per_day, result.exceeds_madl, result.risk_level)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


# ---------------------------------------------------------------------------
# Regulatory constants
# ---------------------------------------------------------------------------

#: California Prop 65 Maximum Allowable Dose Level for lead, in µg/day.
#: Source: Title 27 CCR § 25805, reproductive-toxicity endpoint.
MADL_LEAD_UG_PER_DAY: float = 0.5

#: Fraction of the MADL at which we classify exposure as "CAUTION".
#: Below this → SAFE. This threshold mirrors the 40%-of-MADL internal release
#: target already recommended for at-risk NCL products such as Level Off.
CAUTION_THRESHOLD_FRACTION: float = 0.40

#: Fraction of the MADL at which we classify exposure as "HIGH RISK".
#: Above 80% of MADL, ±10% ICP-MS analytical variability can push a future
#: lot over the limit, so the product must be treated as imminent-risk.
HIGH_RISK_THRESHOLD_FRACTION: float = 0.80


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

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

    # ---- aggregate computed properties ------------------------------------

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

    # ---- breakdown & serialisation ----------------------------------------

    def ingredient_breakdown(self) -> list[dict]:
        """Per-ingredient contribution rows, ordered by µg/day descending.

        Useful for identifying which raw material is the dominant lead source
        — often the leverage point for reformulation.
        """
        total_per_day = self.lead_ug_per_day or 1.0  # avoid div-by-zero
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


# ---------------------------------------------------------------------------
# Core calculation — the only function you need if using this as a library
# ---------------------------------------------------------------------------

def calculate_lead_exposure(
    ingredients: Sequence[Ingredient],
    capsules_per_day: int,
    madl_ug_per_day: float = MADL_LEAD_UG_PER_DAY,
) -> ExposureResult:
    """Compute the Prop 65 lead exposure for a capsule formulation.

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
        or any input value is negative.
    """
    if not ingredients:
        raise ValueError("At least one ingredient is required.")
    if capsules_per_day <= 0:
        raise ValueError("capsules_per_day must be a positive integer.")
    if madl_ug_per_day <= 0:
        raise ValueError("madl_ug_per_day must be positive.")

    for ingredient in ingredients:
        if ingredient.lead_ppm < 0:
            raise ValueError(
                f"Negative lead_ppm for ingredient '{ingredient.name}'."
            )
        if ingredient.mg_per_capsule < 0:
            raise ValueError(
                f"Negative mg_per_capsule for ingredient '{ingredient.name}'."
            )

    return ExposureResult(
        ingredients=tuple(ingredients),
        capsules_per_day=capsules_per_day,
        madl_ug_per_day=madl_ug_per_day,
    )


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

_RISK_STYLES: dict[str, str] = {
    "SAFE":       "bold green",
    "CAUTION":    "bold yellow",
    "HIGH RISK":  "bold dark_orange",
    "OVER LIMIT": "bold red",
}


def render_report_to_console(result: ExposureResult) -> None:
    """Pretty-print the result as a rich-formatted report to stdout."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    console = Console()
    style = _RISK_STYLES.get(result.risk_level, "bold")

    # Headline verdict
    headline = Text()
    headline.append(result.risk_level, style=style)
    headline.append(
        f"  —  {result.lead_ug_per_day:.4f} µg Pb/day  "
        f"({result.percent_of_madl:.1f}% of MADL "
        f"{result.madl_ug_per_day} µg/day)"
    )
    console.print(Panel(headline, title="Prop 65 Lead Exposure", title_align="left"))

    # Per-ingredient breakdown
    table = Table(title="Ingredient breakdown", title_justify="left")
    table.add_column("Ingredient", style="cyan")
    table.add_column("ppm Pb",         justify="right")
    table.add_column("mg / cap",       justify="right")
    table.add_column("µg Pb / cap",    justify="right")
    table.add_column("µg Pb / day",    justify="right")
    table.add_column("% of total",     justify="right")
    for row in result.ingredient_breakdown():
        table.add_row(
            str(row["name"]),
            f"{row['lead_ppm']:.4f}",
            f"{row['mg_per_capsule']:g}",
            f"{row['lead_ug_per_capsule']:.4f}",
            f"{row['lead_ug_per_day']:.4f}",
            f"{row['percent_of_total']:.1f}%",
        )
    console.print(table)

    # Totals
    totals = Table.grid(padding=(0, 2))
    totals.add_column(style="dim")
    totals.add_column()
    totals.add_row("Capsules per day:",  str(result.capsules_per_day))
    totals.add_row("Lead per capsule:",  f"{result.lead_ug_per_capsule:.4f} µg")
    totals.add_row("Lead per day:",      f"{result.lead_ug_per_day:.4f} µg")
    totals.add_row(
        "MADL reference:",
        f"{result.madl_ug_per_day} µg/day (Prop 65, 27 CCR § 25805)",
    )
    totals.add_row("Risk level:", Text(result.risk_level, style=style))
    console.print(totals)

    # Guidance line
    if result.exceeds_madl:
        guidance = (
            "[bold red]Prop 65 warning required[/] for California sales at this "
            "formulation. Reduce per-capsule extract mass, lower the max daily "
            "capsule count, or source a lower-lead raw material."
        )
    elif result.risk_level == "HIGH RISK":
        guidance = (
            "[bold dark_orange]Within MADL but with < 20% headroom.[/] "
            "Typical ICP-MS ±10% variability could push a future lot over."
        )
    elif result.risk_level == "CAUTION":
        guidance = (
            "[bold yellow]Within MADL but above the 40%-of-MADL internal threshold.[/] "
            "Consider tightening the incoming-raw-material spec and per-lot retesting."
        )
    else:
        guidance = "[bold green]Comfortable margin below the MADL.[/]"
    console.print(Panel(guidance, title="Guidance", title_align="left"))


def render_report_to_json(result: ExposureResult) -> str:
    """Return the result serialised as pretty-printed JSON."""
    return json.dumps(result.to_dict(), indent=2)


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------

def _parse_ingredient_triplet(triplet: Sequence[str]) -> Ingredient:
    """Convert a ``--ingredient NAME PPM MG`` CLI triplet into an Ingredient."""
    name, ppm_str, mg_str = triplet
    try:
        lead_ppm = float(ppm_str)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid ppm value '{ppm_str}' for ingredient '{name}'."
        ) from exc
    try:
        mg_per_capsule = float(mg_str)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid mg_per_capsule value '{mg_str}' for ingredient '{name}'."
        ) from exc
    return Ingredient(name=name, lead_ppm=lead_ppm, mg_per_capsule=mg_per_capsule)


def _load_ingredients_file(path: Path) -> tuple[list[Ingredient], dict]:
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


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prop65_lead_calculator",
        description=(
            "Calculate lead exposure from a supplement capsule and compare it "
            "to the California Prop 65 MADL (0.5 µg/day). Supports multiple "
            "raw materials per capsule."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  uv run %(prog)s.py -i 'Loquat Leaf 10:1' 0.3604 600 -c 2\n"
            "  uv run %(prog)s.py -i 'Mulberry' 0.6 250 -i 'Cinnamon' 0.8 85 -c 2\n"
            "  uv run %(prog)s.py --ingredients-file formula.json\n"
        ),
    )
    parser.add_argument(
        "-i", "--ingredient",
        action="append",
        nargs=3,
        metavar=("NAME", "PPM", "MG_PER_CAPSULE"),
        help=(
            "A raw material in the capsule. Repeat for multiple ingredients. "
            "NAME: any string (quote if it has spaces or colons). "
            "PPM: lead from the COA in ppm (= µg/g). "
            "MG_PER_CAPSULE: milligrams of this raw material per capsule."
        ),
    )
    parser.add_argument(
        "-f", "--ingredients-file",
        type=Path,
        help="Path to a JSON file with ingredients (schema in module docstring).",
    )
    parser.add_argument(
        "-c", "--capsules-per-day",
        type=int,
        help=(
            "Maximum capsules per day from the product label "
            "(e.g. '1 cap twice daily' → 2). Required unless supplied in "
            "--ingredients-file."
        ),
    )
    parser.add_argument(
        "--madl",
        type=float,
        default=MADL_LEAD_UG_PER_DAY,
        help=(
            f"Override the MADL (default: {MADL_LEAD_UG_PER_DAY} µg/day, "
            "Prop 65 lead). Change only for other metals or research scenarios."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON to stdout instead of a human-readable report.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns 0 (safe) or 1 (over MADL). argparse handles 2."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # -- Gather ingredients (CLI triplets + optional file) ------------------
    ingredients: list[Ingredient] = []
    file_overrides: dict = {}

    if args.ingredients_file:
        try:
            ingredients, file_overrides = _load_ingredients_file(args.ingredients_file)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            parser.error(f"Could not read ingredients file: {exc}")

    if args.ingredient:
        for triplet in args.ingredient:
            try:
                ingredients.append(_parse_ingredient_triplet(triplet))
            except argparse.ArgumentTypeError as exc:
                parser.error(str(exc))

    if not ingredients:
        parser.error("Provide at least one --ingredient or an --ingredients-file.")

    # -- Resolve remaining parameters (CLI takes precedence over file) -------
    capsules_per_day = args.capsules_per_day or file_overrides.get("capsules_per_day")
    if not capsules_per_day:
        parser.error(
            "--capsules-per-day is required (or set it in the ingredients file)."
        )

    # Only defer to the file's MADL if the user didn't override it on the CLI.
    madl = (
        args.madl
        if args.madl != MADL_LEAD_UG_PER_DAY
        else file_overrides.get("madl_ug_per_day", args.madl)
    )

    # -- Compute & render ----------------------------------------------------
    try:
        result = calculate_lead_exposure(
            ingredients=ingredients,
            capsules_per_day=capsules_per_day,
            madl_ug_per_day=madl,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if args.json:
        print(render_report_to_json(result))
    else:
        render_report_to_console(result)

    return 1 if result.exceeds_madl else 0


if __name__ == "__main__":
    sys.exit(main())
