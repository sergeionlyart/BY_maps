"""Инварианты INF-15 «Полотно» - кадры карты и G-3 (grid_frames.py, шаг 4).

Только стандартная библиотека - читает уже сгенерированные
web/public/data/grid_frames/*.webp|meta.json|budget_report.json и
data/raw/grid/g3_nightlights_crosscheck.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FRAMES = ROOT / "web" / "public" / "data" / "grid_frames"
RAW = ROOT / "data" / "raw" / "grid"
G3 = RAW / "g3_nightlights_crosscheck.json"

pytestmark = pytest.mark.skipif(
    not FRAMES.exists(), reason="etl.grid_frames ещё не прогонялся")


def test_budget_report_within_limits():
    report = json.loads((FRAMES / "budget_report.json").read_text())
    assert report["total_mb"] <= report["total_mb_budget"]
    assert report["frame_kb_max_observed"] <= report["frame_kb_budget"]
    assert report["within_budget"] is True


def test_observed_frames_exist_for_all_epochs():
    EPOCHS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020]
    for e in EPOCHS:
        assert (FRAMES / f"pop_{e}.webp").exists()


def test_forecast_frames_exist_for_all_combinations():
    years = [2026, 2031, 2036, 2041, 2046, 2050]
    for y in years:
        for scn in ("base", "optimistic", "negative"):
            for variant in ("A", "B"):
                assert (FRAMES / f"pop_{y}_{scn}_{variant}.webp").exists()


def test_meta_has_geolocation():
    meta = json.loads((FRAMES / "meta.json").read_text())
    assert len(meta["bounds_lonlat"]) == 4
    assert meta["width"] > 0 and meta["height"] > 0


@pytest.mark.skipif(not G3.exists(), reason="G-3 ещё не считалась")
def test_g3_documented_not_hidden():
    """Раздел 7 ТЗ: результат G-3 (пройдена или нет) публикуется как есть,
    вместе с разбивкой по районам-хозяевам городов (условие ревью D-005)."""
    g3 = json.loads(G3.read_text())
    assert g3["n_raions"] > 100
    assert g3["pct_agree"] is not None
    assert "city_host_raions" in g3 and "non_host_raions" in g3
    assert isinstance(g3["disagreements"], list)
    # G-3 провалена по факту расчёта (D-007) - фиксируем известный статус,
    # чтобы регресс (неожиданное исправление без объяснения) был заметен.
    assert g3["pass"] is False
    assert g3["pct_agree"] < 70
