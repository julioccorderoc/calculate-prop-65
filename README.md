# Prop 65 Lead Exposure Calculator

Agent skill + CLI. Computes whether dietary supplement capsule formulation exceeds California Proposition 65 Maximum Allowable Dose Level (MADL) for lead.

Raw material passing COA under USP <232> / ICH Q3D (oral Pb PDE 5 ug/day) can still fail California Prop 65, whose lead MADL is 0.5 ug/day under Title 27 CCR 25805 — 10x stricter. That gap drives finished-product recalls and warning-label decisions. Tool does linear deterministic capsule math: lead ppm per raw-material COA, mg per capsule, max daily capsule count → ug/day exposure, percent-of-MADL, four-zone risk classification.

## Install as an agent skill

Repo ships as an [Agent Skill](https://github.com/anthropics/skills) — any LLM harness supporting skills can invoke it when users ask about Prop 65 lead calculations, MADL comparisons, or California warning decisions. `SKILL.md` at root is the manifest.

```bash
npx skills add julioccorderoc/calculate-prop-65 -g -y
```

### Other sources

```bash
npx skills add https://github.com/julioccorderoc/calculate-prop-65            # full URL
npx skills add git@github.com:julioccorderoc/calculate-prop-65.git            # SSH
npx skills add ./calculate-prop-65                          # local path
```

`npx skills` auto-detects `SKILL.md` at repo root and wires it into the agent harness's skill directory. See [vercel-labs/skills](https://github.com/vercel-labs/skills) for the installer spec.

Once installed, the agent invokes the skill on triggers like "Prop 65", "MADL", "California warning", "lead in supplements". See [SKILL.md](./SKILL.md) for full trigger list and usage.

## Install as a CLI / library

Managed with [uv](https://docs.astral.sh/uv/). Python >= 3.10.

```bash
git clone https://github.com/julioccorderoc/calculate-prop-65.git
cd calculate-prop-65
uv sync
```

Installs package plus dev group (`pytest`, `rich`). No build step.

To run without installing — `scripts/calculate.py` carries PEP 723 inline-script header; uv resolves deps on the fly:

```bash
uv run scripts/calculate.py --help
```

## Quick start

### CLI

Single ingredient, 2 capsules per day:

```bash
uv run scripts/calculate.py -i "Loquat Leaf 10:1" 0.3604 600 -c 2
```

Multiple raw materials per capsule (lead contributions add):

```bash
uv run scripts/calculate.py \
  -i "White Mulberry Leaf"    0.60 250 \
  -i "Cinnamon Cassia 12:1"   0.80  85 \
  -i "Veggie Blend"           0.40 180 \
  -c 2
```

From versioned JSON formula file:

```bash
uv run scripts/calculate.py --ingredients-file reference/multi_ingredient.json
```

Append `--json` for machine-readable payload instead of rich console report.

### Library

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

`result.ingredient_breakdown()` returns per-ingredient rows sorted by ug/day descending — reformulation leverage map.

### JSON ingredients file schema

Top-level: `ingredients[]` with `name`, `lead_ppm`, `mg_per_capsule`. Optional top-level `capsules_per_day`, `madl_ug_per_day`.

## The math

Lead on COA reported in parts per million. By definition `1 ppm == 1 ug Pb / g raw material`. Per capsule:

```text
lead_ug_per_capsule = sum over ingredients of (lead_ppm * mg_per_capsule / 1000)
lead_ug_per_day     = lead_ug_per_capsule * capsules_per_day
percent_of_MADL     = lead_ug_per_day / 0.5 * 100
```

`/ 1000` converts mg to g, since ppm is ug/g.

California Prop 65 lead MADL: 0.5 ug/day (Title 27 CCR 25805, reproductive-toxicity endpoint). USP <232> / ICH Q3D sets oral PDE at 5 ug/day — limit most raw-material COAs are written against — so Prop 65 is 10x stricter. That 10x gap is why this tool exists.

## Risk zones

Four zones by fraction of MADL:

| Zone       | Range of daily exposure | Meaning                                                                                   |
|------------|-------------------------|-------------------------------------------------------------------------------------------|
| SAFE       | < 40% of MADL           | Comfortable headroom.                                                                     |
| CAUTION    | 40% to 80% of MADL      | Within MADL but above 40% internal target for at-risk products. Tighten COA spec.         |
| HIGH RISK  | 80% to 100% of MADL     | Less than 20% headroom. Typical ICP-MS +/- 10% variability can push future lot over.      |
| OVER LIMIT | >= 100% of MADL         | Prop 65 warning required for California sales. Reformulate, re-source, or add warning.    |

Boundaries inclusive-lower (`>=`). Exactly 100% of MADL classifies as OVER LIMIT.

## Reference fixtures

`reference/` holds canonical JSON fixtures — one per risk zone. Double as worked examples, skill demos, and pytest fixtures:

| File                       | Risk zone  | Shape                      |
|----------------------------|------------|----------------------------|
| `safe_formula.json`        | SAFE       | Clean vitamin-mineral stack.    |
| `caution_formula.json`     | CAUTION    | Turmeric + botanicals.          |
| `single_ingredient.json`   | HIGH RISK  | One high-mass botanical.        |
| `multi_ingredient.json`    | OVER LIMIT | Three-ingredient herbal capsule. |
| `high_risk_formula.json`   | OVER LIMIT | Synthetic stress test.          |

## Project layout

```text
.
├── SKILL.md            # agent skill manifest (trigger + usage)
├── README.md           # this file
├── scripts/
│   ├── __init__.py     # re-exports Ingredient, ExposureResult, calculate_lead_exposure
│   ├── calculate.py    # CLI entry point (uv inline-script shebang)
│   ├── constants.py    # MADL + risk-zone thresholds
│   ├── models.py       # Ingredient, ExposureResult dataclasses
│   ├── calculator.py   # pure calculate_lead_exposure function
│   ├── loaders.py      # CLI-triplet + JSON-file input parsers
│   └── renderers.py    # rich-console + JSON output renderers
├── reference/          # JSON fixtures (also used by tests + skill examples)
├── tests/              # pytest suite
├── pyproject.toml
└── uv.lock
```

Import from top-level package (`from scripts import calculate_lead_exposure, Ingredient`) for stable library use — internal layout may shift, package-level exports won't.

## Running the tests

```bash
uv run pytest
```

Single test file, verbose:

```bash
uv run pytest tests/test_calculator.py -v
```

## Exit codes

| Code | Meaning                                                        |
|------|----------------------------------------------------------------|
| 0    | Daily exposure below MADL. No Prop 65 warning required.        |
| 1    | Daily exposure at or above MADL. Warning required.             |
| 2    | Usage or input error (argparse default).                       |

Stable. Use in shell pipelines or CI to gate builds.

## Regulatory references

- **California Prop 65 lead MADL: 0.5 ug/day**, reproductive-toxicity endpoint, Title 27 CCR section 25805.
- **USP <232> / ICH Q3D oral Pb PDE: 5 ug/day** — limit most raw-material COAs are written against.
- **10x gap** between them drives this tool. COA saying "passes spec" under USP <232> can fail Prop 65 once you multiply through by per-capsule extract mass and max daily dose. Re-run math against 0.5 ug/day before any California labeling decision.

## Disclaimer

Not legal advice. Tool computes exposure math from user-supplied inputs; labeling decisions require regulatory review.

## Notes

Educational comments embedded in `scripts/` are load-bearing domain knowledge, not decoration — preserve on any refactor. They make this a teaching tool a regulatory-affairs hire can read top to bottom, not just a calculator.
