"""Инварианты INF-15 «Полотно» - network_per_capita и проверка G-6
(ТЗ раздел 7, проверка 6) + утверждение C-3 пререгистрации (grid-v0.1.md §3).

Тест читает уже сгенерированный data/raw/grid/network_metrics.json
(etl/grid_network.py) стандартной библиотекой - shapely/numpy/scipy НЕ
требуются для этого файла (сам пересчёт network_metrics.json - опциональный
шаг, см. requirements-raster.txt/requirements.txt), тот же паттерн
skipif, что в etl/tests/test_grid.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "grid"
METRICS = RAW / "network_metrics.json"
NETWORK_CSV = RAW / "network_by_raion.csv"
REGISTRY_CSV = RAW / "registry_road_stats.csv"

pytestmark = pytest.mark.skipif(
    not METRICS.exists(), reason="etl.grid_network ещё не прогонялся")

G6_TOLERANCE_PCT = 15.0
N_TERRITORIES = 119  # 118 районов + BY-HM


@pytest.fixture(scope="module")
def metrics():
    return json.loads(METRICS.read_text())


def test_file_exists_and_valid(metrics):
    assert isinstance(metrics, dict)
    for key in ("g6", "correlation_c3", "national", "territories"):
        assert key in metrics, f"отсутствует ключ верхнего уровня {key}"


def test_supporting_files_written():
    assert NETWORK_CSV.exists()
    assert REGISTRY_CSV.exists()
    rows = NETWORK_CSV.read_text(encoding="utf-8").strip().splitlines()
    assert rows[0] == "raion,highway_class,length_km"
    assert len(rows) > 1


def test_g6_recorded_with_explicit_number(metrics):
    """Раздел 7 ТЗ, проверка 6 + чеклист аудита п.2: у каждой из восьми
    проверок должно стоять ЧИСЛО, а не слово "пройдено"."""
    g6 = metrics["g6"]
    for key in ("osm_total_km", "official_total_km", "delta_pct",
                "tolerance_pct", "passed", "mode"):
        assert key in g6, f"G-6 отчёт без поля {key}"
    assert isinstance(g6["osm_total_km"], (int, float)) and g6["osm_total_km"] > 0
    assert isinstance(g6["official_total_km"], (int, float)) and g6["official_total_km"] > 0
    assert g6["tolerance_pct"] == G6_TOLERANCE_PCT
    # delta_pct должен быть математически согласован с осм/официальной цифрой
    expected_delta = ((g6["osm_total_km"] - g6["official_total_km"])
                       / g6["official_total_km"] * 100.0)
    assert abs(g6["delta_pct"] - expected_delta) < 0.05
    # passed должен быть логически согласован с допуском
    assert g6["passed"] == (abs(g6["delta_pct"]) <= G6_TOLERANCE_PCT)


def test_g6_mode_matches_pass_fail(metrics):
    """Раздел 7 ТЗ проверка 6, ветка "иначе": если G-6 не пройдена -
    network_per_capita публикуется ТОЛЬКО как relative_index, без
    абсолютных км. Если пройдена - абсолютные числа разрешены."""
    g6 = metrics["g6"]
    if g6["passed"]:
        assert g6["mode"] == "absolute"
    else:
        assert g6["mode"] == "relative_index"


def test_g6_official_source_documented(metrics):
    g6 = metrics["g6"]
    assert g6.get("official_source"), "не указан источник официальной статистики"
    assert g6.get("official_accessed"), "не указана дата обращения к источнику"


def test_correlation_c3_present_with_sign_and_pvalue(metrics):
    """Пререгистрация grid-v0.1.md §3 (C-3): корреляция Spearman
    network_per_capita_2026 vs pop_change_1989_2026 по 118 районам,
    знак и p-value обязательны для контракта опровержения."""
    c3 = metrics["correlation_c3"]
    for key in ("n_raions", "spearman_rho", "p_value", "sign",
                "significant_at_0.05", "supports_c3"):
        assert key in c3, f"C-3 отчёт без поля {key}"
    assert c3["n_raions"] == 118, "C-3 считается по 118 районам (без BY-HM)"
    assert -1.0 <= c3["spearman_rho"] <= 1.0
    assert 0.0 <= c3["p_value"] <= 1.0
    assert c3["sign"] in ("negative", "positive", "zero")
    expected_sign = ("negative" if c3["spearman_rho"] < 0
                      else "positive" if c3["spearman_rho"] > 0 else "zero")
    assert c3["sign"] == expected_sign
    expected_significant = c3["p_value"] < 0.05
    assert c3["significant_at_0.05"] == expected_significant
    # контракт опровержения (пререгистрация §3/§7): подтверждение C-3 =
    # отрицательная И значимая корреляция
    expected_supports = (c3["sign"] == "negative" and c3["significant_at_0.05"])
    assert c3["supports_c3"] == expected_supports


def test_all_territories_have_network_per_capita(metrics):
    territories = metrics["territories"]
    assert len(territories) == N_TERRITORIES, (
        f"ожидали {N_TERRITORIES} территорий (118 районов + BY-HM), "
        f"получили {len(territories)}")
    mode = metrics["g6"]["mode"]
    for tid, rec in territories.items():
        assert "road_km_total" in rec and rec["road_km_total"] >= 0
        assert "pop_change_1989_2026_pct" in rec
        assert "relative_index_per_1000_vs_national_mean" in rec
        assert rec["relative_index_per_1000_vs_national_mean"] is not None, (
            f"{tid}: относительный индекс network_per_capita обязателен "
            "независимо от исхода G-6")
        if mode == "absolute":
            assert rec["road_km_per_1000"] is not None, (
                f"{tid}: G-6 пройдена, но road_km_per_1000 не заполнен")
            assert rec["road_km_per_km2"] is not None
        else:
            assert rec["road_km_per_1000"] is None, (
                f"{tid}: G-6 не пройдена, абсолютные км/1000 не должны "
                "публиковаться (только relative_index)")
            assert rec["road_km_per_km2"] is None


def test_territories_include_all_118_raions_and_by_hm(metrics):
    territories = metrics["territories"]
    raion_ids = [tid for tid in territories if tid.startswith("r-")]
    assert len(raion_ids) == 118
    assert "BY-HM" in territories


def test_pop_change_uses_1989_baseline_or_documented_fallback(metrics):
    """Раздел 4 пререгистрации: если 1989 недоступен - ближайший
    последующий перепис. год, помечается is_fallback."""
    territories = metrics["territories"]
    for tid, rec in territories.items():
        baseline = rec["pop_baseline_1989"]
        assert "year" in baseline and "value" in baseline and "is_fallback" in baseline
        if not baseline["is_fallback"]:
            assert baseline["year"] == 1989
        else:
            assert baseline["year"] > 1989


def test_national_totals_consistent(metrics):
    national = metrics["national"]
    g6 = metrics["g6"]
    assert national["road_km_total"] == g6["osm_total_km"]
    assert national["n_edges"] > 0
    assert 0 <= national["n_edges_snapped_to_nearest"] < national["n_edges"]
