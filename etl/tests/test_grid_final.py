"""Инварианты финального web/public/data/grid.json (Приложение А ТЗ)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GRID_JSON = ROOT / "web" / "public" / "data" / "grid.json"

pytestmark = pytest.mark.skipif(
    not GRID_JSON.exists(), reason="etl.grid_project ещё не прогонялся")

BUDGET_KB = 1536


@pytest.fixture(scope="module")
def data():
    return json.loads(GRID_JSON.read_text())


def test_size_budget():
    assert GRID_JSON.stat().st_size / 1024 <= BUDGET_KB


def test_crs_is_equal_area_not_web_mercator(data):
    """D-001: расчётная сетка в ESRI:54009, не EPSG:3857 из примера
    Приложения А (сохраняет реальный размер ячейки "1 км")."""
    assert data["grid"]["crs"] == "ESRI:54009"
    assert data["grid"]["cell_m"] == 1000


def test_years(data):
    assert data["years"]["observed"] == [1975, 1980, 1985, 1990, 1995, 2000,
                                          2005, 2010, 2015, 2020]
    assert data["years"]["forecast"] == [2026, 2031, 2036, 2041, 2046, 2050]


def test_frames_present_for_key_years(data):
    assert "2020" in data["frames"]
    assert "2050:base:A" in data["frames"]
    assert len(data["frames"]) == 46


def test_territories_count(data):
    assert len(data["territories"]) == 119


def test_claims_status_reflects_g3_failure(data):
    """C-1/C-2 обязаны быть помечены "open_question" (D-007) - если тест
    вдруг видит "verified", проверь, не подрихтовали ли G-3 без обновления
    decisions/INF-15.md."""
    status = data["meta"]["claims_status"]
    assert status["C-001"] == "open_question"
    assert status["C-002"] == "open_question"
    assert status["C-003"] == "verified"


def test_honesty_disclaimer_present(data):
    honesty = data["meta"]["honesty"]
    assert "дазиметрическая" in honesty.lower() or "не является" in honesty.lower() \
        or "не независимая" in honesty.lower()


def test_validation_section_has_all_gates(data):
    v = data["validation"]
    assert "g1_reconciliation_summary" in v
    assert "g2_summary" in v
    assert "g3_nightlights_crosscheck" in v
    assert "g4_g5" in v
    assert "g6_network" in v and v["g6_network"] is not None
    assert "c3_correlation" in v and v["c3_correlation"] is not None
