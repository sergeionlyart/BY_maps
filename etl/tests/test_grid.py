"""Инварианты INF-15 «Полотно» - наблюдаемая часть (grid.py, шаг 2).

Тесты читают уже сгенерированные data/raw/grid/*.json|csv (вендоренные в
репозиторий - маленькие вырезки/агрегаты, см. раздел 6 ТЗ) стандартной
библиотекой - rasterio/scipy НЕ требуются для этого файла (растровые шаги
пересоздания - etl/grid_extract.py/etl/grid.py - опциональны, см.
requirements-raster.txt).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "grid"
METRICS = RAW / "metrics_observed.json"
RECON = RAW / "reconciliation.csv"

pytestmark = pytest.mark.skipif(
    not METRICS.exists(), reason="etl.grid ещё не прогонялся")

EPOCHS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020]
RAION_TOL_PCT = 3.0
NATIONAL_TOL_PCT = 1.0
MAX_FAILED_RAIONS = 15


@pytest.fixture(scope="module")
def metrics():
    return json.loads(METRICS.read_text())


@pytest.fixture(scope="module")
def recon_rows():
    with RECON.open() as f:
        return list(csv.DictReader(f))


def test_epochs_complete(metrics):
    assert metrics["epochs"] == EPOCHS


def test_territories_count(metrics):
    # 118 районов + Минск
    assert len(metrics["territories"]) == 119


def test_pop_grid_sum_present_for_all_epochs(metrics):
    for tid, rec in metrics["territories"].items():
        for epoch in EPOCHS:
            assert str(epoch) in rec["pop_grid_sum"], f"{tid} missing {epoch}"


def test_g1_constrained_matches_official_exactly(metrics, recon_rows):
    """После constrained-калибровки (D-005) сумма клеток района ДОЛЖНА
    совпадать с официальным рядом почти точно (константа по построению,
    не эмпирический тест) - допуск здесь техническая погрешность
    округления/интерполяции, не научный порог G-1.1."""
    off_by_raion_epoch = {}
    for r in recon_rows:
        if r["official"]:
            off_by_raion_epoch[(r["raion"], r["epoch"])] = float(r["official"])
    checked = 0
    for tid, rec in metrics["territories"].items():
        for epoch in EPOCHS:
            off = off_by_raion_epoch.get((tid, str(epoch)))
            if off is None or off <= 0:
                continue
            grid_sum = rec["pop_grid_sum"][str(epoch)]
            pct = abs(grid_sum - off) / off * 100.0
            assert pct <= 0.5, f"{tid}/{epoch}: constrained grid_sum={grid_sum} vs official={off} ({pct:.3f}%)"
            checked += 1
    assert checked > 1000


def test_g1_raw_reconciliation_documented_not_hidden(metrics):
    """Раздел 7 ТЗ, проверка 1: список районов вне допуска ПУБЛИКУЕТСЯ, не
    прячется в средней цифре - здесь проверяем, что summary содержит
    полный список и корректно классифицирует случай ">15 районов"."""
    summary = metrics["reconciliation_summary"]
    assert summary["n_failed_raions_ever"] > MAX_FAILED_RAIONS
    assert summary["drop_raw_raion_numbers"] is True
    assert len(summary["failed_raions_ever"]) == summary["n_failed_raions_ever"]
    assert "per_epoch_fail" in summary and len(summary["per_epoch_fail"]) == len(EPOCHS)


def test_national_area_share_below_5_monotonic_nondecreasing(metrics):
    """Утверждение C-2 (пререгистрация): area_share_below(5) растёт весь
    наблюдаемый ряд. Допуск шума 0.5 п.п. между соседними эпохами."""
    series = metrics["national"]["area_share_below"]["5"]
    vals = [series[str(e)] for e in EPOCHS]
    for i in range(1, len(vals)):
        assert vals[i] >= vals[i - 1] - 0.005, (
            f"area_share_below(5) упало между {EPOCHS[i-1]} и {EPOCHS[i]}: "
            f"{vals[i-1]} -> {vals[i]}")
    assert vals[-1] > vals[0]


def test_national_population_weighted_density_grows_1990_2020(metrics):
    """Утверждение C-1: population-weighted density растёт даже когда
    arithmetic density падает - проверяем на подпериоде явного спада
    численности страны (1990-2020, наблюдаемый ряд data.json)."""
    pw = metrics["national"]["population_weighted_density"]
    arith = metrics["national"]["arithmetic_density"]
    assert pw["2020"] > pw["1990"]
    assert arith["2020"] < arith["1990"]


def test_raw_vs_constrained_agree_in_direction(metrics):
    """Условие ревью D-005 (raw vs constrained): направление и порядок
    величины национальных метрик не должны зависеть от калибровки."""
    raw = metrics["national_raw"]
    below5_raw = [raw["area_share_below"]["5"][str(e)] for e in EPOCHS]
    below5_c = [metrics["national"]["area_share_below"]["5"][str(e)] for e in EPOCHS]
    assert below5_raw[-1] > below5_raw[0]  # тоже растёт на сырых данных
    for r, c in zip(below5_raw, below5_c):
        assert abs(r - c) < 0.02, "raw/constrained разошлись более чем на 2 п.п."
    pw_raw = [raw["population_weighted_density"][str(e)] for e in EPOCHS]
    assert pw_raw[-1] > pw_raw[EPOCHS.index(1990)]


def test_settlement_components_present(metrics):
    for epoch in EPOCHS:
        sc = metrics["national"]["settlement_components"][str(epoch)]
        assert sc["n_components"] >= 1
        assert 0 <= sc["largest_share_of_pop"] <= 1


def test_g4_robust_to_polesye_chernobyl_exclusion(metrics):
    g4 = metrics["validation"]["g4_polesye_chernobyl"]
    assert g4["n_excluded"] > 0
    assert g4["still_monotonic_nondecreasing"] is True
    assert g4["growth_1975_2020"] > 0, "C-2 не подтверждается без Полесья/Чернобыля"


def test_g5_centroid_shift_within_tolerance(metrics):
    g5 = metrics["validation"]["g5_centroid_sensitivity"]
    assert g5["pass"] is True
    assert g5["max_shift_km"] < 15


def test_centroid_track_covers_full_range(metrics):
    years = sorted(c["year"] for c in metrics["national"]["centroid_track"])
    assert years[0] <= 1959
    assert years[-1] == 2020
    for c in metrics["national"]["centroid_track"]:
        assert 51.0 <= c["lat"] <= 57.0
        assert 22.0 <= c["lon"] <= 33.0
        assert "err_km" in c and "dtype" in c
