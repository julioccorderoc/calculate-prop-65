"""First-class risk-zone taxonomy for Prop 65 lead exposure.

Each :class:`RiskZone` bundles everything the rest of the package needs to
know about a qualitative zone: its ordered threshold (as a fraction of the
MADL, inclusive lower bound), its user-facing display name, its ``rich``
console style, and the guidance paragraph shown in reports.

Historically these four facets lived in four different modules — a
``CAUTION_THRESHOLD_FRACTION`` constant, a ``risk_level`` string, a
``RISK_STYLES`` dict, and a ``_guidance_for`` helper. Unifying them means
adding a new zone or tweaking guidance happens in exactly one place.

Boundary semantics (load-bearing): zones are classified with an **inclusive
lower bound** (``fraction >= threshold``). Exactly 100% of MADL classifies
as ``OVER_LIMIT`` — not ``HIGH_RISK``. This reflects regulatory practice:
at or above the MADL a Prop 65 warning is required, it is not borderline.
"""

from __future__ import annotations

from enum import Enum

from .constants import (
    CAUTION_THRESHOLD_FRACTION,
    HIGH_RISK_THRESHOLD_FRACTION,
)


class RiskZone(Enum):
    """Qualitative Prop 65 exposure classification.

    Members are ordered from lowest to highest risk. The ``value`` tuple
    carries the domain data (threshold, display name, rich style, guidance
    text) — using a tuple keeps each member self-contained so iteration is
    total and ordering is stable.

    Display names (``SAFE``, ``CAUTION``, ``HIGH RISK``, ``OVER LIMIT``)
    appear in user-facing output and in JSON payloads; they are part of the
    public contract and must not change without updating SKILL.md, README.md
    and reference fixtures.
    """

    # Members are declared in ascending-threshold order so ``classify`` can
    # walk them from highest to lowest and pick the first match.
    SAFE = (
        0.0,
        "SAFE",
        "bold green",
        "[bold green]Comfortable margin below the MADL.[/]",
    )
    CAUTION = (
        CAUTION_THRESHOLD_FRACTION,
        "CAUTION",
        "bold yellow",
        (
            "[bold yellow]Within MADL but above the 40%-of-MADL internal threshold.[/] "
            "Consider tightening the incoming-raw-material spec and per-lot retesting."
        ),
    )
    HIGH_RISK = (
        HIGH_RISK_THRESHOLD_FRACTION,
        "HIGH RISK",
        "bold dark_orange",
        (
            "[bold dark_orange]Within MADL but with < 20% headroom.[/] "
            "Typical ICP-MS ±10% variability could push a future lot over."
        ),
    )
    OVER_LIMIT = (
        1.0,
        "OVER LIMIT",
        "bold red",
        (
            "[bold red]Prop 65 warning required[/] for California sales at this "
            "formulation. Reduce per-capsule extract mass, lower the max daily "
            "capsule count, or source a lower-lead raw material."
        ),
    )

    def __init__(
        self,
        threshold_fraction: float,
        display_name: str,
        rich_style: str,
        guidance: str,
    ) -> None:
        self.threshold_fraction = threshold_fraction
        self.display_name = display_name
        self.rich_style = rich_style
        self.guidance = guidance

    def __str__(self) -> str:  # pragma: no cover - trivial
        """Return the user-facing display name (e.g. ``"HIGH RISK"``)."""
        return self.display_name

    @classmethod
    def classify(cls, fraction_of_madl: float) -> "RiskZone":
        """Return the zone for a given exposure fraction.

        ``fraction_of_madl`` is ``lead_ug_per_day / madl_ug_per_day``. The
        lookup is inclusive-lower (``>=``) — exactly 100% of MADL is
        ``OVER_LIMIT``, exactly 80% is ``HIGH_RISK``, exactly 40% is
        ``CAUTION``. Tests lock these boundaries; do not "fix" them.
        """
        # Walk from highest threshold down and pick the first zone the
        # fraction meets. Equivalent to nested ``if`` guards but driven off
        # the enum members so adding a zone requires no change here.
        for zone in reversed(list(cls)):
            if fraction_of_madl >= zone.threshold_fraction:
                return zone
        # Unreachable: SAFE.threshold_fraction is 0.0 and a negative
        # fraction is already rejected by upstream validation. Keep a
        # defensive fallback rather than raising.
        return cls.SAFE
