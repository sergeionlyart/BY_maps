"""Инварианты INF-15 «Полотно» - прогнозная часть (grid_project.py, шаг 3).

Только стандартная библиотека - читает уже сгенерированный
data/raw/grid/metrics_forecast.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "grid"
METRICS = RAW / "metrics_forecast.json"

pytestmark = pytest.mark.skipif(
    not METRICS.exists(), reason="etl.grid_project ещё не прогонялся")

FORECAST_YEARS = [2026, 2031, 2036, 2041, 2046, 2050]
SCENARIOS = ["base", "optimistic", "negative"]
VARIANTS = ["A", "B"]
G2_TOLERANCE_PCT = 0.1


@pytest.fixture(scope="module")
def metrics():
    return json.loads(METRICS.read_text())


def test_forecast_years(metrics):
    assert metrics["forecast_years"] == FORECAST_YEARS


def test_scenarios_and_variants(metrics):
    assert metrics["scenarios"] == SCENARIOS
    assert metrics["variants"] == VARIANTS


def test_g2_normalization_within_tolerance(metrics):
    """G-2 (раздел 7 ТЗ): сумма клеток района = прогноз района ±0.1%,
    все сценарии, оба варианта - тест обязателен."""
    summary = metrics["g2_report_summary"]
    assert summary["max_pct_diff"] <= G2_TOLERANCE_PCT
    assert summary["n_checks"] > 1000


def test_all_scenario_variant_year_combinations_present(metrics):
    keys_present = set()
    for tid, rec in metrics["territories"].items():
        keys_present.update(rec["pop_grid_sum"].keys())
    expected = {f"{y}:{s}:{v}" for y in FORECAST_YEARS for s in SCENARIOS
                for v in VARIANTS}
    assert expected.issubset(keys_present)


def test_national_area_share_below_5_continues_rising_to_2050(metrics):
    """C-2: рост доли пустеющей территории продолжается до 2050 (все
    сценарии, вариант A - базовая инерционная проекция)."""
    series = metrics["national"]["area_share_below"]["5"]
    for scn in SCENARIOS:
        v0 = series[f"2026:{scn}:A"]
        v1 = series[f"2050:{scn}:A"]
        assert v1 >= v0, f"{scn}: area_share_below(5) не растёт к 2050 (A)"


def test_variant_a_and_b_both_normalize_to_same_raion_total(metrics):
    """Варианты A/Б различаются распределением ВНУТРИ района, но сумма
    района должна быть идентичной (обе привязаны к одному прогнозу)."""
    for tid, rec in metrics["territories"].items():
        for y in FORECAST_YEARS:
            for scn in SCENARIOS:
                a = rec["pop_grid_sum"].get(f"{y}:{scn}:A")
                b = rec["pop_grid_sum"].get(f"{y}:{scn}:B")
                if a is None or b is None:
                    continue
                if a == 0:
                    continue
                assert abs(a - b) / a < 0.001


def test_anchors_found_for_variant_b(metrics):
    assert len(metrics["variant_b_anchors"]) >= 1
