from __future__ import annotations

import json

import pytest

from scripts import Ingredient, calculate_lead_exposure
from scripts.renderers import render_report_to_console, render_report_to_json


def test_render_report_to_json_round_trips_to_to_dict() -> None:
    ingredients = [
        Ingredient(name="A", lead_ppm=0.60, mg_per_capsule=250.0),
        Ingredient(name="B", lead_ppm=0.80, mg_per_capsule=85.0),
    ]
    result = calculate_lead_exposure(ingredients=ingredients, capsules_per_day=2)
    raw = render_report_to_json(result)
    assert isinstance(raw, str)
    parsed = json.loads(raw)
    assert parsed == result.to_dict()


@pytest.mark.parametrize(
    ("lead_ppm", "mg_per_capsule", "capsules_per_day", "expected_level"),
    [
        (0.01, 100.0, 1, "SAFE"),
        (2.5, 100.0, 1, "CAUTION"),        # 0.25 ug/day = 50% of MADL
        (4.5, 100.0, 1, "HIGH RISK"),      # 0.45 ug/day = 90% of MADL
        (10.0, 100.0, 2, "OVER LIMIT"),    # 2.0 ug/day = 400% of MADL
    ],
)
def test_render_report_to_console_emits_risk_level(
    lead_ppm: float,
    mg_per_capsule: float,
    capsules_per_day: int,
    expected_level: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ingredients = [
        Ingredient(name="Test", lead_ppm=lead_ppm, mg_per_capsule=mg_per_capsule)
    ]
    result = calculate_lead_exposure(
        ingredients=ingredients, capsules_per_day=capsules_per_day
    )
    assert result.risk_level == expected_level
    render_report_to_console(result)
    captured = capsys.readouterr()
    assert expected_level in captured.out
