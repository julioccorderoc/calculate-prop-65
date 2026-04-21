#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "rich>=13.0",
# ]
# ///
"""CLI entry point for the Prop 65 lead-exposure calculator.

Thin orchestration layer: parse args → gather ingredients via loaders →
resolve CLI/file precedence → call the calculator → render via renderers.
All domain logic lives in the sibling modules so this file stays focused
on wiring.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

# Support both `python -m scripts.calculate ...` (relative) and running the
# file directly via `uv run scripts/calculate.py ...` (no package context).
# Go through the package-level namespace for the core domain names so this
# file is robust to internal module reshuffles in the sibling modules.
try:
    from . import Ingredient, MADL_LEAD_UG_PER_DAY, calculate_lead_exposure
    from .loaders import load_ingredients_file, parse_ingredient_triplet
    from .renderers import render_report_to_console, render_report_to_json
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts import Ingredient, MADL_LEAD_UG_PER_DAY, calculate_lead_exposure
    from scripts.loaders import load_ingredients_file, parse_ingredient_triplet
    from scripts.renderers import render_report_to_console, render_report_to_json


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser for the calculator CLI."""
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


def resolve_run_config(
    cli_capsules_per_day: int | None,
    cli_madl: float,
    cli_madl_default: float,
    file_overrides: dict,
) -> tuple[int, float]:
    """Merge CLI args + ingredients-file overrides into a final (capsules_per_day, madl) pair.

    Precedence (load-bearing regulatory logic; do NOT simplify):
      - capsules_per_day: CLI wins if provided; else file; else raise ValueError.
      - madl: CLI wins only if CLI value != cli_madl_default (otherwise defer
        to file; else the default). The asymmetry exists so that argparse's
        default (0.5 µg/day Prop 65 MADL) does not silently clobber a
        deliberate ``madl_ug_per_day`` set in a formula file.
    """
    if cli_capsules_per_day is not None:
        capsules_per_day = cli_capsules_per_day
    else:
        capsules_per_day = file_overrides.get("capsules_per_day")
    if not capsules_per_day:
        raise ValueError(
            "--capsules-per-day is required (or set it in the ingredients file)."
        )

    if cli_madl != cli_madl_default:
        madl = cli_madl
    else:
        madl = file_overrides.get("madl_ug_per_day", cli_madl)

    return capsules_per_day, madl


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns 0 (safe) or 1 (over MADL). argparse handles 2."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    ingredients: list[Ingredient] = []
    file_overrides: dict = {}

    if args.ingredients_file:
        try:
            ingredients, file_overrides = load_ingredients_file(args.ingredients_file)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            parser.error(f"Could not read ingredients file: {exc}")

    if args.ingredient:
        for triplet in args.ingredient:
            try:
                ingredients.append(parse_ingredient_triplet(triplet))
            except ValueError as exc:
                parser.error(str(exc))

    if not ingredients:
        parser.error("Provide at least one --ingredient or an --ingredients-file.")

    try:
        capsules_per_day, madl = resolve_run_config(
            cli_capsules_per_day=args.capsules_per_day,
            cli_madl=args.madl,
            cli_madl_default=MADL_LEAD_UG_PER_DAY,
            file_overrides=file_overrides,
        )
    except ValueError as exc:
        parser.error(str(exc))

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
