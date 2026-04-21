# Prop 65 Lead Exposure Calculator

Calculate whether a dietary supplement capsule formulation exceeds the California Proposition 65 Maximum Allowable Dose Level (MADL) for lead.

A raw material that cleanly passes its Certificate of Analysis (COA) under USP <232> / ICH Q3D (oral Pb PDE 5 ug/day) can still fail California Prop 65, whose MADL for lead is 0.5 ug/day under Title 27 CCR 25805 -- 10x stricter. That gap is where finished-product recalls and warning-label decisions live. This tool does the linear, deterministic capsule math for you: take the lead ppm off each raw-material COA, the mg of each raw material per capsule, and the max daily capsule count, and it returns the ug/day exposure, a percent-of-MADL, and a four-zone risk classification.

## What this repo is

Two things in one:

1. **A CLI tool** (`scripts/calculate.py`) -- run it on a raw-material COA and a formulation to find out whether the finished product needs a Prop 65 warning for California sales.
2. **A Claude Code skill** (`SKILL.md` at the root) -- lets Claude invoke the same logic on behalf of users who describe their formulation in natural language.

Both paths use the same underlying code in `scripts/`.

## Installation

The project is managed with [uv](https://docs.astral.sh/uv/). Python >= 3.10 is required.

```bash
uv sync
```

That installs the package plus the dev group (`pytest`, `rich`). No build step.

If you just want to run the CLI without installing the package, `scripts/calculate.py` carries a PEP 723 inline-script header, so uv will resolve its dependencies on the fly:

```bash
uv run scripts/calculate.py --help
```

## Quick start

### As a CLI

Single ingredient, 2 capsules per day:

```bash
uv run scripts/calculate.py -i "Loquat Leaf 10:1" 0.3604 600 -c 2
```

Multiple raw materials in one capsule (lead contributions add):

```bash
uv run scripts/calculate.py \
  -i "White Mulberry Leaf"    0.60 250 \
  -i "Cinnamon Cassia 12:1"   0.80  85 \
  -i "Veggie Blend"           0.40 180 \
  -c 2
```

From a versioned JSON formula file:

```bash
uv run scripts/calculate.py --ingredients-file reference/level_off.json
```

Append `--json` to any of the above to emit a machine-readable payload instead of the rich console report.

### As a library

```python
from scripts import calculate_lead_exposure, Ingredient

result = calculate_lead_exposure(
    ingredients=[
        Ingredient(name="White Mulberry Leaf",  lead_ppm=0.60, mg_per_capsule=250),
        Ingredient(name="Cinnamon Cassia 12:1", lead_ppm=0.80, mg_per_capsule=85),
        Ingredient(name="Veggie Blend",         lead_ppm=0.40, mg_per_capsule=180),
    ],
    capsules_per_day=2,
)
print(result.lead_ug_per_day, result.percent_of_madl, result.risk_level)
```

`result.ingredient_breakdown()` returns per-ingredient rows sorted by ug/day descending -- the leverage map for reformulation.

### As a Claude Code skill

This repo is also a Claude Code skill. If installed where Claude Code can discover it (typically under `~/.claude/skills/` or a project-level `.claude/skills/`), Claude will invoke it automatically when users ask about Prop 65 lead calculations, MADL comparisons, or California warning decisions. See `SKILL.md` for the full triggering description and Claude-facing usage notes.

## The math

Lead on a COA is reported in parts per million, and by definition `1 ppm == 1 ug Pb / g raw material`. So for a capsule:

```text
lead_ug_per_capsule = sum over ingredients of (lead_ppm * mg_per_capsule / 1000)
lead_ug_per_day     = lead_ug_per_capsule * capsules_per_day
percent_of_MADL     = lead_ug_per_day / 0.5 * 100
```

The MADL for lead under California Prop 65 is 0.5 ug/day (Title 27 CCR 25805, reproductive-toxicity endpoint). USP <232> / ICH Q3D sets the oral PDE at 5 ug/day -- the limit most raw-material COAs are written against -- so Prop 65 is 10x stricter. That 10x gap is the whole reason this tool exists.

## Risk zones

Exposure is classified into four zones based on fraction of MADL:

| Zone       | Range of daily exposure | Meaning                                                                                              |
|------------|-------------------------|------------------------------------------------------------------------------------------------------|
| SAFE       | < 40% of MADL           | Comfortable headroom.                                                                                |
| CAUTION    | 40% to 80% of MADL      | Within MADL but above NCL's 40% internal target for at-risk products. Consider tightening COA spec.  |
| HIGH RISK  | 80% to 100% of MADL     | Less than 20% headroom. Typical ICP-MS +/- 10% variability can push a future lot over the limit.     |
| OVER LIMIT | >= 100% of MADL         | Prop 65 warning required for California sales. Reformulate, re-source, or add the warning.           |

## Project layout

```text
.
├── SKILL.md            # Claude Code skill manifest (trigger + usage)
├── README.md           # this file
├── CLAUDE.md           # project conventions for Claude instances
├── scripts/
│   ├── __init__.py     # re-exports Ingredient, ExposureResult, calculate_lead_exposure
│   ├── calculate.py    # CLI entry point (uv inline-script shebang)
│   ├── constants.py    # MADL + risk-zone thresholds
│   ├── models.py       # Ingredient, ExposureResult dataclasses
│   ├── calculator.py   # pure calculate_lead_exposure function
│   ├── loaders.py      # CLI-triplet + JSON-file input parsers
│   └── renderers.py    # rich-console + JSON output renderers
├── reference/
│   ├── level_off.json          # multi-ingredient formula (over MADL)
│   ├── single_ingredient.json  # single-ingredient formula (under MADL)
│   └── high_risk_formula.json  # demonstrably over-MADL example
├── tests/              # pytest test suite
├── original.py         # preserved reference copy of the pre-refactor script
├── pyproject.toml
└── uv.lock
```

Each `scripts/*.py` module has a single responsibility; import from the top-level package (`from scripts import calculate_lead_exposure, Ingredient`) for stable library use -- the internal module layout may shift, but the package-level exports will not.

Two things about this layout that are easy to miss:

- **`original.py` is preserved, not source-of-truth.** It is a working standalone copy of the pre-refactor script, kept for historical reference and because its docstrings document the domain reasoning in one place. It still runs. Do not edit it. If you want to change behavior, change `scripts/`.
- **`reference/` is the skill's canonical fixture directory.** This follows the Claude Code skill convention where skill-bundled reference material lives under `reference/`. Those JSON files are not just worked examples -- they are the machine-readable test fixtures the CLI examples and the pytest suite both point at.

## Running the tests

```bash
uv run pytest
```

To run a single test file with verbose output:

```bash
uv run pytest tests/test_calculator.py -v
```

## Exit codes

| Code | Meaning                                                        |
|------|----------------------------------------------------------------|
| 0    | Daily exposure is below the MADL. No Prop 65 warning required. |
| 1    | Daily exposure is at or above the MADL. Warning required.      |
| 2    | Usage or input error (argparse default).                       |

These are stable; use them in shell pipelines or CI to gate builds.

## Regulatory references

- **California Prop 65 lead MADL: 0.5 ug/day**, reproductive-toxicity endpoint, Title 27 CCR section 25805.
- **USP <232> / ICH Q3D oral Pb PDE: 5 ug/day** -- the limit most raw-material COAs are written against.
- The **10x gap** between those two is the reason this tool exists. A COA that says "passes spec" under USP <232> can easily fail Prop 65 once you multiply through by per-capsule extract mass and max daily dose. Always re-run the math against 0.5 ug/day before making a California labeling decision.

## License and attribution

Built for Natural Cure Labs (NCL) internal formulation and QA work. The educational comments embedded in `scripts/` (and in `original.py`) are load-bearing domain knowledge, not decoration -- preserve them on any refactor. They are the difference between this being a calculator and this being a teaching tool a new regulatory-affairs hire can read top to bottom.
