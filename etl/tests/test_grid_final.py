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


def test_centroid_track_extends_to_2050_without_degenerate_points(data):
    """D-009: до фикса centroid_pre_grid() усреднял по единственному
    району (BY-HM), в 1897/1959 трек молча вырождался в координаты
    Минска - обнаружено при доработке B-5. Трек финального grid.json
    также обязан достраиваться прогнозом до 2050 (не обрывается на
    2020, как было до doc/decisions/INF-15.md D-006/D-009)."""
    track = data["national"]["centroid_track"]
    years = [c["year"] for c in track]
    assert years == sorted(years), "трек должен быть отсортирован по году"
    assert years[0] == 1897
    assert years[-1] == 2050
    assert 1970 in years and 2020 in years and 2026 in years

    coords_by_year = {c["year"]: (c["lon"], c["lat"]) for c in track}
    assert coords_by_year[1897] != coords_by_year[1970], (
        "1897 и 1970 не должны совпадать с точностью до вырождения "
        "«среднее по одному району» (см. D-009)")

    by_year = {c["year"]: c for c in track}
    assert by_year[1897]["dtype"] == "e"
    assert by_year[1897]["err_km"] > by_year[1970]["err_km"], (
        "оценка 1897 года грубее (город. население переписи) - err_km обязан быть шире")
    for c in track:
        assert 51.0 <= c["lat"] <= 57.0
        assert 22.0 <= c["lon"] <= 33.0
        assert "err_km" in c and "dtype" in c


def test_g9_concentration_check_present_and_honestly_failing(data):
    """D-013 (docs/decisions/INF-15.md): G-9 - проверка внутрирайонного
    распределения, которую G-2 (сверка только суммы клеток района) не
    делает. Найдено и независимо перепроверено 28.07.2026: наблюдаемая
    доля топ-5 клеток района практически не менялась 45 лет (1975-2020,
    разброс 25.0-26.5%), а лог-линейная экстраполяция доли клетки даёт
    55.4% уже к 2050 (canonical base:A). Это ОЖИДАЕМО непройденная
    проверка - тест фиксирует нынешнее (честно опубликованное) состояние,
    а не требует его "исправить". Если в будущем экстраполяция изменится
    так, что G-9 станет проходить, - это следует сознательно отразить
    здесь (не расширять допуск молча)."""
    g9 = data["validation"]["g9_concentration_check"]
    assert g9["pass"] is False
    assert g9["n_raions_checked"] == 118
    assert g9["n_raions_violated"] > 50
    # наблюдаемый период (1975-2020) - концентрация практически неподвижна
    hist = g9["national_mean_top5_share_by_year"]
    assert abs(hist["2020"] - hist["1975"]) < 0.02
    # прогноз 2050 base:A - более чем вдвое от наблюдаемого уровня 2020 года
    assert g9["national_mean_top5_share_2050_base_a"] > hist["2020"] * 2


def test_frames_present_for_key_years(data):
    """B-2 (docs/decisions/INF-15.md): frames разбит на pop/density -
    режим «класс плотности» получил собственный набор из 46 кадров."""
    for mode in ("pop", "density"):
        assert "2020" in data["frames"][mode]
        assert "2050:base:A" in data["frames"][mode]
        assert len(data["frames"][mode]) == 46


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
