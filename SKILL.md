---
name: calculate-prop-65
description: Calculate California Prop 65 lead exposure (MADL 0.5 ug/day) for dietary supplement capsule formulations given Certificate of Analysis (COA) ppm values and per-capsule ingredient masses. Use whenever the user is deciding whether a supplement needs a Prop 65 warning label, reviewing heavy-metal COAs against California limits, budgeting lead across multi-ingredient capsule formulas, reformulating to reduce lead exposure, or comparing USP <232> / ICH Q3D COA specs to Prop 65. Triggers on "Prop 65", "Proposition 65", "MADL", "California warning", "lead in supplements", "capsule lead math", "heavy metal compliance for California", and similar formulator / QA / regulatory-affairs contexts.
---

# Prop 65 Lead Exposure Calculator

Computes whether a finished capsule product exceeds the California Proposition 65 Maximum Allowable Dose Level (MADL) for lead (0.5 ug/day) given the lead ppm on each raw-material COA, the mg of each raw material per capsule, and the maximum label dose in capsules/day. Built for Natural Cure Labs formulations but works for any capsule product.

## When to use this skill

- User is deciding whether a capsule product needs a California Prop 65 warning label.
- User shares a Certificate of Analysis (COA) with a lead result in ppm and wants to know the finished-product exposure.
- User is formulating or reformulating a multi-ingredient capsule (e.g. a botanical stack) and needs a lead budget across ingredients.
- User wants to identify which ingredient contributes the most lead so they can tighten that spec or swap suppliers.
- User is confused because a raw material "passes COA" under USP <232> / ICH Q3D (5 ug/day PDE) but may still fail Prop 65 (0.5 ug/day, 10x stricter).
- User asks about MADL, 27 CCR 25805, or California heavy-metal compliance for a dietary supplement.

Do NOT invoke for general heavy-metal toxicology, FDA Supplement Facts labeling, or pure USP <232> questions that are not being connected to Prop 65.

## How it works

The math is linear. For each ingredient, `1 ppm == 1 ug Pb / g raw material`, so:

```
lead_ug_per_capsule = sum over ingredients of (lead_ppm * mg_per_capsule / 1000)
lead_ug_per_day     = lead_ug_per_capsule * capsules_per_day
percent_of_MADL     = lead_ug_per_day / 0.5 * 100
```

Results are classified into four risk zones based on the fraction of MADL:

| Zone         | Range of daily exposure | Meaning |
|--------------|-------------------------|---------|
| SAFE         | < 40% of MADL           | Comfortable headroom. |
| CAUTION      | 40% - 80% of MADL       | Within MADL but above the 40% internal target NCL uses for at-risk products. |
| HIGH RISK    | 80% - 100% of MADL      | Within MADL but less than 20% headroom. Typical ICP-MS analytical variability (+/- 10%) can push a future lot over. |
| OVER LIMIT   | >= 100% of MADL         | Prop 65 warning required for California sales. Reformulate or re-source. |

## Usage

### Quick single-ingredient check

```bash
uv run scripts/calculate.py -i "Loquat Leaf 10:1" 0.3604 600 -c 2
```

This says: one raw material, 0.3604 ppm lead on the COA, 600 mg of that raw material per capsule, two capsules per day.

### Multi-ingredient capsule

```bash
uv run scripts/calculate.py \
  -i "White Mulberry Leaf"    0.60 250 \
  -i "Cinnamon Cassia 12:1"   0.80  85 \
  -i "Veggie Blend"           0.40 180 \
  -c 2
```

Repeat `-i` once per raw material in the capsule. Lead contributions add.

### From a JSON formula file

```bash
uv run scripts/calculate.py --ingredients-file reference/level_off.json
```

Use this for versioned formulas or when the same spec is referenced from multiple places. CLI flags `--capsules-per-day` and `--madl` override values set in the file, so you can quickly test "what if we went to 3 caps/day" without editing the file.

### Machine-readable output

```bash
uv run scripts/calculate.py --ingredients-file reference/level_off.json --json
```

Emits the full input + output payload as JSON on stdout. Use this when piping into other tooling.

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

`result.ingredient_breakdown()` returns per-ingredient rows sorted by ug/day descending, which is the leverage map for reformulation.

## Input reference

### `--ingredient NAME PPM MG_PER_CAPSULE`

- `NAME` - any string; quote it if it contains spaces or colons (e.g. `"Loquat Leaf 10:1"`). Labeling only, not used in math.
- `PPM` - the lead result from the COA, in parts per million. `1 ppm == 1 ug Pb / g raw material`.
- `MG_PER_CAPSULE` - milligrams of this raw material in **one capsule**. This is the single most common input error. It is NOT the serving dose, NOT the daily dose, and NOT the batch mass. If the label says "Take 1 capsule twice daily, 500 mg per serving" and each serving is one capsule, then `MG_PER_CAPSULE = 500` and `--capsules-per-day 2`. Do not multiply yourself; the script does that.

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

`madl_ug_per_day` is optional and defaults to 0.5. `capsules_per_day` may be set in the file or on the CLI; the CLI value wins if both are set. See `examples/level_off.json` for the canonical example.

## Output interpretation

The console renderer prints a headline verdict, a per-ingredient breakdown table (sorted by ug/day descending), a totals block, and a guidance panel. The guidance text depends on the risk zone:

- **SAFE** - "Comfortable margin below the MADL." No action needed.
- **CAUTION** - "Within MADL but above the 40%-of-MADL internal threshold. Consider tightening the incoming-raw-material spec and per-lot retesting." Good trigger to renegotiate supplier specs.
- **HIGH RISK** - "Within MADL but with < 20% headroom. Typical ICP-MS +/- 10% variability could push a future lot over." Treat as imminent-risk: either re-source, reduce per-capsule extract mass, or lower the max daily capsule count.
- **OVER LIMIT** - "Prop 65 warning required for California sales at this formulation." Action is non-optional. Reformulate or add the warning.

Look at the breakdown table to identify the dominant lead contributor - that is the leverage point for reformulation.

## Exit codes

- `0` - Daily exposure is below the MADL. No Prop 65 warning required.
- `1` - Daily exposure is at or above the MADL. Warning required.
- `2` - Usage or input error (argparse default).

These are stable; use them in shell pipelines or CI to gate builds.

## Regulatory references

- California Prop 65 MADL for lead: **0.5 ug/day**, reproductive-toxicity endpoint, Title 27 CCR section 25805.
- Compare to USP <232> / ICH Q3D oral Permitted Daily Exposure for lead: **5 ug/day**. This is the limit most raw-material COAs are written against.
- Prop 65 is **10x stricter** than USP <232>. A COA that says "passes spec" under USP <232> can easily fail Prop 65 once you account for the per-capsule extract mass and the max daily dose. Always re-run the math against 0.5 ug/day before making a California labeling decision.
