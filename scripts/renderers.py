"""Output formatting: rich console report and JSON serialisation."""

from __future__ import annotations

import json

from .constants import RISK_STYLES
from .models import ExposureResult


def _guidance_for(result: ExposureResult) -> str:
    """Return the rich-markup guidance line appropriate to the risk level."""
    if result.exceeds_madl:
        return (
            "[bold red]Prop 65 warning required[/] for California sales at this "
            "formulation. Reduce per-capsule extract mass, lower the max daily "
            "capsule count, or source a lower-lead raw material."
        )
    if result.risk_level == "HIGH RISK":
        return (
            "[bold dark_orange]Within MADL but with < 20% headroom.[/] "
            "Typical ICP-MS ±10% variability could push a future lot over."
        )
    if result.risk_level == "CAUTION":
        return (
            "[bold yellow]Within MADL but above the 40%-of-MADL internal threshold.[/] "
            "Consider tightening the incoming-raw-material spec and per-lot retesting."
        )
    return "[bold green]Comfortable margin below the MADL.[/]"


def render_report_to_console(result: ExposureResult) -> None:
    """Pretty-print the result as a rich-formatted report to stdout."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    console = Console()
    style = RISK_STYLES.get(result.risk_level, "bold")

    headline = Text()
    headline.append(result.risk_level, style=style)
    headline.append(
        f"  —  {result.lead_ug_per_day:.4f} µg Pb/day  "
        f"({result.percent_of_madl:.1f}% of MADL "
        f"{result.madl_ug_per_day} µg/day)"
    )
    console.print(Panel(headline, title="Prop 65 Lead Exposure", title_align="left"))

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

    console.print(Panel(_guidance_for(result), title="Guidance", title_align="left"))


def render_report_to_json(result: ExposureResult) -> str:
    """Return the result serialised as pretty-printed JSON."""
    return json.dumps(result.to_dict(), indent=2)
