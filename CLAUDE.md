# CLAUDE.md

Project: Prop 65 Lead Exposure Calculator. Supplement-formulation compliance tool, packaged as agent skill.

## What this repo is

Pure-Python package (`scripts/`). Computes whether capsule formulation exceeds California Prop 65 lead MADL (0.5 ug/day). Ships as CLI and as agent skill (`SKILL.md` at root).

## Architecture rules

- `scripts/` is a package. One job per module: `constants`, `models`, `calculator`, `loaders`, `renderers`, `calculate` (CLI orchestrator). No cross-cutting helpers in random files.
- `calculator.py` stays side-effect free. No I/O, no printing, no file reads. Pure calculation function is the point; everything else wraps it.
- CLI entry (`scripts/calculate.py`) is thin: parse args, call loaders, call calculator, call renderers. No business logic here.
- Public API lives in `scripts/__init__.py`'s `__all__` (currently `Ingredient`, `ExposureResult`, `calculate_lead_exposure`, `MADL_LEAD_UG_PER_DAY`). Add new public names there. Private names (leading underscore) never imported from tests or outside their module.
- `rich` imported lazily inside `render_report_to_console` so core package stays dependency-free. Do not hoist import to module scope.

## Domain rules (load-bearing, do NOT change without explicit user signoff)

- `MADL_LEAD_UG_PER_DAY = 0.5`: California Prop 65 reproductive-toxicity limit for lead (Title 27 CCR section 25805). Not arbitrary.
- `CAUTION_THRESHOLD_FRACTION = 0.40`: organization's internal 40% release target for at-risk products. No change without regulatory signoff.
- `HIGH_RISK_THRESHOLD_FRACTION = 0.80`: typical ICP-MS analytical variability is +/- 10%, so above 80% of MADL a future lot can flip over. No change without signoff.
- Risk zone boundaries are `>=` (inclusive lower). Exactly 100% of MADL classifies as OVER LIMIT (not HIGH RISK). Tests lock this. Do not "fix" it.
- `1 ppm == 1 ug Pb / g raw material` is math basis. Factor of 1000 converts mg to g. Do not refactor units without updating every docstring.
- `ingredient_breakdown` guards division by zero by substituting `1.0` when total per-day lead is 0, so all-zero-ppm formulation yields 0% rows instead of `ZeroDivisionError`. Preserve guard.

## Input conventions (users get these wrong)

- `mg_per_capsule` is per ONE capsule. Not per serving, not per day. Label says "Take 1 capsule twice daily, 500 mg per serving" and each serving is one capsule -> `mg_per_capsule=500` and `capsules_per_day=2`. Script multiplies; user must not pre-multiply.
- `lead_ppm` is straight from COA. No unit conversion. No division.
- `capsules_per_day` is MAX label dose (e.g. "up to 2 capsules" -> 2), not typical dose.

## CLI precedence rule (subtle)

- `--capsules-per-day` on CLI overrides value in `--ingredients-file`.
- `--madl` on CLI overrides file value ONLY if CLI value differs from default (0.5). Do not "simplify" this asymmetry.
- `main()` returns `1` when result exceeds MADL, `0` otherwise; argparse handles `2`. Keep exit-code contract.

## Running and testing

- Install: `uv sync`
- Run CLI: `uv run scripts/calculate.py ...` (uv inline-script shebang, also works standalone).
- Run tests: `uv run pytest` (config in `pyproject.toml`; `testpaths=["tests"]`, `pythonpath=["."]`).
- Reference JSON files in `reference/` are fixtures for tests and `SKILL.md` examples. Change numbers and downstream tests and skill docs drift. Intentional — update all three together.

## Changes that need user signoff

- Changing any regulatory constant in `scripts/constants.py`.
- Adding new risk zone or renaming existing ones.
- Changing JSON schema accepted by `load_ingredients_file` (currently: `ingredients[]` with `name`, `lead_ppm`, `mg_per_capsule`; optional top-level `capsules_per_day` and `madl_ug_per_day`).
- Removing CLI precedence rule or `--json` output format.

## When making changes

- Re-run `uv run pytest` before claiming done.
- Adding new ingredient field, regulatory constant, or output key -> update `SKILL.md` AND `README.md` AND relevant JSON fixtures in `reference/`. All three must agree.
- Preserve educational docstrings in `scripts/`. Encode domain knowledge (ppm conversion, Prop 65 vs USP <232>, ICP-MS variability). Point of the code, not decoration.
