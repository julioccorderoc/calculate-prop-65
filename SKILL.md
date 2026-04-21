---
name: calculate-prop-65
description: Calculate California Prop 65 lead exposure (MADL 0.5 ug/day) for dietary supplement capsule formulations from COA ppm values and per-capsule ingredient masses. Use for Prop 65 warning-label decisions, reviewing heavy-metal COAs vs California limits, budgeting lead across multi-ingredient capsules, reformulating to reduce lead, or comparing USP <232> / ICH Q3D COA specs to Prop 65. Triggers on "Prop 65", "Proposition 65", "MADL", "California warning", "lead in supplements", "capsule lead math", "heavy metal compliance for California".
---

# Prop 65 Lead Exposure Calculator

Computes whether finished capsule product exceeds California Proposition 65 MADL for lead (0.5 ug/day) given raw-material COA lead ppm, mg per capsule, and max label dose in capsules/day. Works for any capsule product.

## When to use this skill

- Deciding whether capsule product needs California Prop 65 warning label.
- COA has lead in ppm; need finished-product exposure.
- Formulating/reformulating multi-ingredient capsule; need lead budget across ingredients.
- Identifying dominant lead contributor to tighten spec or swap suppliers.
- Raw material "passes COA" under USP <232> / ICH Q3D (5 ug/day PDE) but may fail Prop 65 (0.5 ug/day, 10x stricter).
- Questions about MADL, 27 CCR 25805, California heavy-metal compliance for dietary supplements.

Do NOT invoke for general heavy-metal toxicology, FDA Supplement Facts labeling, or pure USP <232> questions unconnected to Prop 65.

## How it works

Math is linear. Per ingredient, `1 ppm == 1 ug Pb / g raw material`:

```
lead_ug_per_capsule = sum over ingredients of (lead_ppm * mg_per_capsule / 1000)
lead_ug_per_day     = lead_ug_per_capsule * capsules_per_day
percent_of_MADL     = lead_ug_per_day / 0.5 * 100
```

Four risk zones by fraction of MADL:

| Zone         | Range of daily exposure | Meaning |
|--------------|-------------------------|---------|
| SAFE         | < 40% of MADL           | Comfortable headroom. |
| CAUTION      | 40% - 80% of MADL       | Within MADL but above 40% internal target for at-risk products. |
| HIGH RISK    | 80% - 100% of MADL      | Within MADL, <20% headroom. Typical ICP-MS variability (+/- 10%) can push future lot over. |
| OVER LIMIT   | >= 100% of MADL         | Prop 65 warning required for California sales. Reformulate or re-source. |

## Usage

### Quick single-ingredient check

```bash
uv run scripts/calculate.py -i "Loquat Leaf 10:1" 0.3604 600 -c 2
```

One raw material, 0.3604 ppm lead on COA, 600 mg per capsule, two capsules/day.

### Multi-ingredient capsule

```bash
uv run scripts/calculate.py \
  -i "White Mulberry Leaf"    0.60 250 \
  -i "Cinnamon Cassia 12:1"   0.80  85 \
  -i "Veggie Blend"           0.40 180 \
  -c 2
```

Repeat `-i` per raw material. Lead contributions add.

### From JSON formula file

```bash
uv run scripts/calculate.py --ingredients-file reference/multi_ingredient.json
```

Use for versioned formulas or when same spec is referenced from multiple places. CLI flags `--capsules-per-day` and `--madl` override file values — test "what if 3 caps/day" without editing file.

### Machine-readable output

```bash
uv run scripts/calculate.py --ingredients-file reference/multi_ingredient.json --json
```

Emits full input + output payload as JSON on stdout. Use when piping to other tooling.

### Library use

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

`result.ingredient_breakdown()` returns per-ingredient rows sorted by ug/day descending — leverage map for reformulation.

## Input reference

### `--ingredient NAME PPM MG_PER_CAPSULE`

- `NAME` — any string; quote if it contains spaces or colons (e.g. `"Loquat Leaf 10:1"`). Label only, not math.
- `PPM` — lead result from COA, parts per million. `1 ppm == 1 ug Pb / g raw material`.
- `MG_PER_CAPSULE` — mg of this raw material in **one capsule**. Most common input error. NOT serving dose, NOT daily dose, NOT batch mass. If label says "Take 1 capsule twice daily, 500 mg per serving" and each serving is one capsule, then `MG_PER_CAPSULE = 500` and `--capsules-per-day 2`. Do not pre-multiply; script does it.

### JSON file schema

```json
{
  "capsules_per_day": 2,
  "madl_ug_per_day":  0.5,
  "ingredients": [
    {"name": "White Mulberry Leaf",  "lead_ppm": 0.60, "mg_per_capsule": 250},
    {"name": "Cinnamon Cassia 12:1", "lead_ppm": 0.80, "mg_per_capsule":  85},
    {"name": "Veggie Blend",         "lead_ppm": 0.40, "mg_per_capsule": 180}
  ]
}
```

`madl_ug_per_day` optional, defaults to 0.5. `capsules_per_day` may be set in file or CLI; CLI wins if both set. Canonical example in `reference/multi_ingredient.json`.

## Output interpretation

Console renderer prints headline verdict, per-ingredient breakdown table (sorted by ug/day descending), totals block, guidance panel. Guidance text depends on risk zone:

- **SAFE** — "Comfortable margin below the MADL." No action.
- **CAUTION** — "Within MADL but above the 40%-of-MADL internal threshold. Consider tightening incoming-raw-material spec and per-lot retesting." Trigger to renegotiate supplier specs.
- **HIGH RISK** — "Within MADL but with < 20% headroom. Typical ICP-MS +/- 10% variability could push a future lot over." Imminent-risk: re-source, reduce per-capsule extract mass, or lower max daily capsule count.
- **OVER LIMIT** — "Prop 65 warning required for California sales at this formulation." Non-optional. Reformulate or add warning.

Breakdown table identifies dominant lead contributor — leverage point for reformulation.

## Exit codes

- `0` — Daily exposure below MADL. No Prop 65 warning required.
- `1` — Daily exposure at or above MADL. Warning required.
- `2` — Usage or input error (argparse default).

Stable; use in shell pipelines or CI to gate builds.

## Regulatory references

- California Prop 65 MADL for lead: **0.5 ug/day**, reproductive-toxicity endpoint, Title 27 CCR section 25805.
- USP <232> / ICH Q3D oral Permitted Daily Exposure for lead: **5 ug/day**. Limit most raw-material COAs are written against.
- Prop 65 is **10x stricter** than USP <232>. COA that "passes spec" under USP <232> can fail Prop 65 once per-capsule extract mass and max daily dose are accounted for. Always re-run math against 0.5 ug/day before California labeling decision.
