"""Инварианты web/public/data/grid_story.json и слоя магистралей (INF-15 v2,
этап 2 - handoff/09_next_research/INF-15_grid_v2_brief.md раздел 7,
гипотезы C-004/C-005 - docs/preregistration/grid-v0.2.md)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STORY_JSON = ROOT / "web" / "public" / "data" / "grid_story.json"
HIGHWAYS_GEOJSON = ROOT / "web" / "public" / "data" / "geo" / "grid_highways.geojson"

pytestmark = pytest.mark.skipif(
    not STORY_JSON.exists(), reason="etl.grid_story ещё не прогонялся")

BUDGET_STORY_KB = 100
BUDGET_HIGHWAYS_KB = 2048


@pytest.fixture(scope="module")
def story():
    return json.loads(STORY_JSON.read_text())


def test_budgets():
    assert STORY_JSON.stat().st_size / 1024 <= BUDGET_STORY_KB
    assert HIGHWAYS_GEOJSON.stat().st_size / 1024 <= BUDGET_HIGHWAYS_KB


def test_c004_density_bands_match_independent_recount(story):
    """docs/preregistration/grid-v0.2.md §3: точное совпадение с зондажем
    docs/notes/grid_three_scenarios_2026-07-28.md §3.2."""
    bands = story["c004_density_bands"]["bands"]
    assert len(bands) == 6
    expected_n_cells = [17285, 24645, 23436, 10264, 1506, 941]
    assert [b["n_cells"] for b in bands] == expected_n_cells
    expected_change = [-20.5, -25.8, -29.3, -21.6, 10.3, 18.1]
    for b, exp in zip(bands, expected_change):
        assert abs(b["change_pct"] - exp) < 0.05
    # "правило пятисот": граница роста/убыли между 100-500 и 500-2000
    assert bands[3]["change_pct"] < 0
    assert bands[4]["change_pct"] > 0


def test_c005_highway_distance_gradient_monotonic(story):
    """Градиент должен быть отрицательным на всех поясах дальше 2 км и
    качественно совпадать с независимым пересчётом (см. preregistration
    v0.2 §3 - метод растеризации даёт малые расхождения, не разворот знака)."""
    bands = story["c005_highway_distance"]["bands"]
    assert len(bands) == 5
    assert bands[0]["change_pct"] > 0          # 0-2 км - рост
    for b in bands[1:]:
        assert b["change_pct"] < 0             # дальше - убыль
    # монотонность убыли (каждый следующий пояс хуже предыдущего) -
    # кроме последнего открытого пояса (20+ км - широкий, эффект насыщается)
    changes = [b["change_pct"] for b in bands]
    assert changes[1] > changes[2] > changes[3]


def test_half_population_area(story):
    """Совпадает с зондажем §3.1 и с независимым пересчётом preregistration
    v0.2 §3 - площадь, вмещающая половину населения страны, сжимается."""
    half = story["half_population_area_km2"]
    assert half["1975"] == 1131
    assert half["2020"] == 598
    assert half["2050:base:A"] < half["2020"] < half["1975"]


def test_raion_rankings_contain_known_extremes(story):
    r = story["raions"]
    shrunk_ids = {row["id"] for row in r["shrunk_most"]}
    grew_ids = {row["id"] for row in r["grew_most"]}
    assert "r-brahinski" in shrunk_ids          # Брагинский, -74.3% в брифе
    assert "r-brescki" in grew_ids              # Брестский, +98.0% в брифе
    assert r["n_raions_shrunk"] == 99
    assert r["n_raions_shrunk_40pct_or_more"] == 61
    # Брагинский - самый глубокий провал в наборе
    top_loss = min(row["change_pct"] for row in r["shrunk_most"])
    assert next(row for row in r["shrunk_most"] if row["id"] == "r-brahinski")["change_pct"] == top_loss
    # имена приложены в самой ETL (фиксированный top-N набор - не тянуть
    # отдельный справочник на клиенте ради 17 территорий)
    assert all(row["name_ru"] and row["name_be"] for row in r["shrunk_most"] + r["grew_most"])
    assert r["minsk_city"]["name_ru"]


def test_raion_by_id_covers_named_examples_outside_top8(story):
    """Регресс: шаг 4 истории называет Свислочский район в западной группе
    опустевших районов, но он не входит в top-8 по рангу (9-й, -57.3%) -
    поиск по имени/проценту должен идти через `by_id` (полный список),
    а не через shrunk_most/grew_most (только top-8), иначе интерполяция
    молча подставляет id вместо названия (найдено при проверке в браузере
    28.07.2026)."""
    by_id = story["raions"]["by_id"]
    assert len(by_id) == 119
    svislach = by_id["r-svislacki"]
    assert svislach["name_ru"] == "Свислочский район"
    assert svislach["change_pct"] < -50
    assert "r-svislacki" not in {r["id"] for r in story["raions"]["shrunk_most"]}


def test_cells_ge5_matches_brief(story):
    ge5 = story["cells_ge5_pop"]
    assert ge5["1975"] == 60792
    assert ge5["2020"] == 55377
    assert ge5["2050:base:A"] == 33203


def test_chernobyl_zone_layer_nonempty(story):
    zones = story["chernobyl_zone_class"]
    assert len(zones) > 0
    assert "r-brahinski" in zones
    assert zones["r-brahinski"] in (1, 2)


def test_highways_geojson_valid():
    d = json.loads(HIGHWAYS_GEOJSON.read_text())
    assert d["type"] == "FeatureCollection"
    assert len(d["features"]) > 100
    f0 = d["features"][0]
    assert f0["geometry"]["type"] == "LineString"
    assert len(f0["geometry"]["coordinates"][0]) == 2
    lon, lat = f0["geometry"]["coordinates"][0]
    assert 20 < lon < 36 and 51 < lat < 57   # грубая проверка - координаты над Беларусью
