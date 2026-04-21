from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.calculate import build_arg_parser, main, resolve_run_config


def _reference_path(name: str) -> str:
    return str(Path(__file__).resolve().parent.parent / "reference" / name)


def test_main_returns_zero_when_exposure_is_well_below_madl(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["-i", "Test", "0.1", "100", "-c", "2"])
    assert exit_code == 0


def test_main_returns_one_when_exposure_is_massively_over_madl(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["-i", "Test", "10", "1000", "-c", "2"])
    assert exit_code == 1


def test_main_returns_one_for_multi_ingredient_reference(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["--ingredients-file", _reference_path("multi_ingredient.json")])
    assert exit_code == 1


def test_main_returns_zero_for_single_ingredient_reference(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["--ingredients-file", _reference_path("single_ingredient.json")])
    assert exit_code == 0


def test_main_returns_one_for_high_risk_formula_reference(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["--ingredients-file", _reference_path("high_risk_formula.json")])
    assert exit_code == 1


def test_main_returns_zero_for_safe_formula_reference(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["--ingredients-file", _reference_path("safe_formula.json"), "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["outputs"]["risk_level"] == "SAFE"


def test_main_returns_zero_for_caution_formula_reference(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["--ingredients-file", _reference_path("caution_formula.json"), "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["outputs"]["risk_level"] == "CAUTION"


def test_main_with_json_flag_emits_valid_json_to_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["-i", "X", "0.1", "100", "-c", "2", "--json"])
    assert exit_code == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert isinstance(payload, dict)
    assert "inputs" in payload
    assert "outputs" in payload


def test_main_with_no_args_exits_with_code_two() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2


def test_main_without_capsules_per_day_exits_with_code_two() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["-i", "X", "0.1", "100"])
    assert excinfo.value.code == 2


def test_main_with_negative_lead_ppm_exits_with_code_two() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["-i", "X", "-1.0", "100", "-c", "2"])
    assert excinfo.value.code == 2


def test_cli_capsules_per_day_overrides_file_value(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # multi_ingredient file has capsules_per_day=2. Override to 1 via CLI and confirm
    # the per-day exposure in the JSON output is exactly half.
    exit_code_at_two = main(
        ["-f", _reference_path("multi_ingredient.json"), "--json"]
    )
    out_at_two = capsys.readouterr().out
    payload_at_two = json.loads(out_at_two)
    ug_per_day_at_two = payload_at_two["outputs"]["lead_ug_per_day"]

    exit_code_at_one = main(
        ["-f", _reference_path("multi_ingredient.json"), "-c", "1", "--json"]
    )
    out_at_one = capsys.readouterr().out
    payload_at_one = json.loads(out_at_one)
    ug_per_day_at_one = payload_at_one["outputs"]["lead_ug_per_day"]

    assert ug_per_day_at_one == pytest.approx(ug_per_day_at_two / 2.0)
    # At 1 cap/day the formula drops to 0.290 ug/day → under MADL (0 exit).
    assert exit_code_at_one == 0
    assert exit_code_at_two == 1


def test_cli_madl_override_changes_the_reference_limit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        ["-i", "X", "0.5", "100", "-c", "2", "--madl", "5.0", "--json"]
    )
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["inputs"]["madl_ug_per_day"] == 5.0
    assert payload["outputs"]["exceeds_madl"] is False
    assert exit_code == 0


def test_build_arg_parser_returns_an_argument_parser() -> None:
    import argparse

    parser = build_arg_parser()
    assert isinstance(parser, argparse.ArgumentParser)


# ---------------------------------------------------------------------------
# Direct unit tests for resolve_run_config — locks in the asymmetric
# CLI-vs-file precedence rule documented in CLAUDE.md so a future refactor
# cannot silently "simplify" it.
# ---------------------------------------------------------------------------


_DEFAULT_MADL = 0.5


def test_resolve_run_config_cli_capsules_with_no_file_overrides_uses_cli() -> None:
    capsules, madl = resolve_run_config(
        cli_capsules_per_day=3,
        cli_madl=_DEFAULT_MADL,
        cli_madl_default=_DEFAULT_MADL,
        file_overrides={},
    )
    assert capsules == 3
    assert madl == _DEFAULT_MADL


def test_resolve_run_config_no_cli_capsules_falls_back_to_file() -> None:
    capsules, madl = resolve_run_config(
        cli_capsules_per_day=None,
        cli_madl=_DEFAULT_MADL,
        cli_madl_default=_DEFAULT_MADL,
        file_overrides={"capsules_per_day": 2},
    )
    assert capsules == 2
    assert madl == _DEFAULT_MADL


def test_resolve_run_config_cli_capsules_overrides_file_capsules() -> None:
    capsules, _madl = resolve_run_config(
        cli_capsules_per_day=1,
        cli_madl=_DEFAULT_MADL,
        cli_madl_default=_DEFAULT_MADL,
        file_overrides={"capsules_per_day": 4},
    )
    assert capsules == 1


def test_resolve_run_config_missing_capsules_everywhere_raises_value_error() -> None:
    with pytest.raises(ValueError, match="capsules-per-day"):
        resolve_run_config(
            cli_capsules_per_day=None,
            cli_madl=_DEFAULT_MADL,
            cli_madl_default=_DEFAULT_MADL,
            file_overrides={},
        )


def test_resolve_run_config_cli_madl_at_default_defers_to_file_madl() -> None:
    _capsules, madl = resolve_run_config(
        cli_capsules_per_day=2,
        cli_madl=_DEFAULT_MADL,
        cli_madl_default=_DEFAULT_MADL,
        file_overrides={"madl_ug_per_day": 1.25},
    )
    assert madl == 1.25


def test_resolve_run_config_cli_madl_non_default_overrides_file_madl() -> None:
    _capsules, madl = resolve_run_config(
        cli_capsules_per_day=2,
        cli_madl=5.0,
        cli_madl_default=_DEFAULT_MADL,
        file_overrides={"madl_ug_per_day": 1.25},
    )
    assert madl == 5.0


def test_resolve_run_config_cli_madl_at_default_no_file_returns_default() -> None:
    _capsules, madl = resolve_run_config(
        cli_capsules_per_day=2,
        cli_madl=_DEFAULT_MADL,
        cli_madl_default=_DEFAULT_MADL,
        file_overrides={},
    )
    assert madl == _DEFAULT_MADL


def test_resolve_run_config_cli_madl_non_default_no_file_returns_cli_value() -> None:
    _capsules, madl = resolve_run_config(
        cli_capsules_per_day=2,
        cli_madl=2.5,
        cli_madl_default=_DEFAULT_MADL,
        file_overrides={},
    )
    assert madl == 2.5


@pytest.mark.parametrize(
    ("cli_caps", "cli_madl", "cli_default", "file_overrides", "expected"),
    [
        # CLI caps always wins over file caps.
        (7, 0.5, 0.5, {"capsules_per_day": 2}, (7, 0.5)),
        # File caps used when CLI caps is absent.
        (None, 0.5, 0.5, {"capsules_per_day": 2}, (2, 0.5)),
        # CLI madl at default + file madl -> file wins.
        (2, 0.5, 0.5, {"madl_ug_per_day": 0.8}, (2, 0.8)),
        # CLI madl non-default + file madl -> CLI wins.
        (2, 1.0, 0.5, {"madl_ug_per_day": 0.8}, (2, 1.0)),
        # All from file, CLI only provides madl default.
        (None, 0.5, 0.5, {"capsules_per_day": 2, "madl_ug_per_day": 0.7}, (2, 0.7)),
    ],
)
def test_resolve_run_config_parametrized_matrix(
    cli_caps: int | None,
    cli_madl: float,
    cli_default: float,
    file_overrides: dict,
    expected: tuple[int, float],
) -> None:
    assert (
        resolve_run_config(
            cli_capsules_per_day=cli_caps,
            cli_madl=cli_madl,
            cli_madl_default=cli_default,
            file_overrides=file_overrides,
        )
        == expected
    )
