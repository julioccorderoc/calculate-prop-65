# CLAUDE.md

Project: Prop 65 Lead Exposure Calculator, an NCL supplement-formulation compliance tool, packaged as a Claude Code skill.

## What this repo is

A tiny, pure-Python package (`scripts/`) that computes whether a capsule formulation exceeds the California Prop 65 lead MADL (0.5 ug/day). It ships as a CLI and as a Claude Code skill (`SKILL.md` at root).

## Architecture rules

- `scripts/` is a package, not a dumping ground. Each module has one job: `constants`, `models`, `calculator`, `loaders`, `renderers`, `calculate` (CLI orchestrator). Keep it that way. Do not add cross-cutting helpers to random files.
- `calculator.py` must stay side-effect free. No I/O, no printing, no file reads. The pure calculation function is the whole point; everything else wraps it.
- The CLI entry (`scripts/calculate.py`) is thin. It parses args, calls loaders, calls the calculator, calls renderers. Do not put business logic there.
- Public API lives in `scripts/__init__.py`'s `__all__` (currently `Ingredient`, `ExposureResult`, `calculate_lead_exposure`, `MADL_LEAD_UG_PER_DAY`). When you add something public, add it there. When something is private (leading underscore), do NOT import it from tests or elsewhere outside its module.
- `rich` is imported lazily inside `render_report_to_console` so the core package stays dependency-free. Do not hoist the import to module scope.

## Domain rules (load-bearing, do NOT change without explicit user signoff)

- `MADL_LEAD_UG_PER_DAY = 0.5` is the California Prop 65 reproductive-toxicity limit for lead (Title 27 CCR section 25805). It is not arbitrary.
- `CAUTION_THRESHOLD_FRACTION = 0.40` is NCL's internal 40% release target for at-risk products. Do not change without regulatory signoff.
- `HIGH_RISK_THRESHOLD_FRACTION = 0.80` exists because typical ICP-MS analytical variability is +/- 10%, so above 80% of MADL a future lot can flip over. Do not change without signoff.
- Risk zone boundaries are `>=` (inclusive lower). The boundary at exactly 100% of MADL classifies as OVER LIMIT (not HIGH RISK). Tests lock this in. Do not "fix" it.
- `1 ppm == 1 ug Pb / g raw material` is the basis of the math. The factor of 1000 converting mg to g is why the calculation works. Do not refactor to use different units without updating every docstring.
- `ingredient_breakdown` guards division by zero by substituting `1.0` when total per-day lead is 0, so an all-zero-ppm formulation yields 0% rows instead of a `ZeroDivisionError`. Preserve that guard.

## Input conventions (users get these wrong)

- `mg_per_capsule` is per ONE capsule, not per serving and not per day. If the label says "Take 1 capsule twice daily, 500 mg per serving" and each serving is one capsule, `mg_per_capsule=500` and `capsules_per_day=2`. The script multiplies; the user must not pre-multiply.
- `lead_ppm` is straight from the COA. Do not unit-convert. Do not divide by anything.
- `capsules_per_day` is the MAX label dose (e.g. "up to 2 capsules" -> 2), not the typical dose.

## CLI precedence rule (subtle)

- `--capsules-per-day` on the CLI overrides the value in `--ingredients-file`.
- `--madl` on the CLI overrides the file value ONLY if the CLI value differs from the default (0.5). This is the preserved behavior from `original.py`. Do not "simplify" it.
- `main()` returns `1` when the result exceeds MADL, `0` otherwise; argparse handles `2`. Keep that exit-code contract.

## Running and testing

- Install: `uv sync`
- Run CLI: `uv run scripts/calculate.py ...` (the script has a uv inline-script shebang so it also works standalone).
- Run tests: `uv run pytest` (pytest config lives in `pyproject.toml`; `testpaths=["tests"]`, `pythonpath=["."]`).
- The reference JSON files in `reference/` are fixtures used by tests and by `SKILL.md` examples. If you change the numbers, downstream tests and the skill docs will drift. That is intentional — update all three together.

## Changes that need user signoff

- Changing any regulatory constant in `scripts/constants.py`.
- Adding a new risk zone or renaming existing ones.
- Changing the JSON schema accepted by `load_ingredients_file` (currently: `ingredients[]` with `name`, `lead_ppm`, `mg_per_capsule`; optional top-level `capsules_per_day` and `madl_ug_per_day`).
- Removing the CLI precedence rule or the `--json` output format.
- Removing `original.py` from the repo (it is preserved as a historical reference).

## Files that are NOT source of truth

- `original.py` — kept as a reference copy of the pre-refactor standalone script. The live code lives in `scripts/`. Do not edit `original.py`; if a bug exists, fix it in `scripts/`.

## When making changes

- Re-run `uv run pytest` before claiming anything is done.
- If you add a new ingredient field, regulatory constant, or output key, update `SKILL.md` AND `README.md` AND the relevant JSON fixtures in `reference/`. All three have to agree.
- Preserve the educational docstrings in `scripts/`. They encode domain knowledge (ppm conversion, Prop 65 vs USP <232>, ICP-MS variability). That is the point of the code, not decoration.
