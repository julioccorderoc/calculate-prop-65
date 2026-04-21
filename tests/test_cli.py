from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.calculate import build_arg_parser, main


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
