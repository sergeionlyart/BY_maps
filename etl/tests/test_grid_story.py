"""Инварианты web/public/data/grid_story.json и слоёв магистралей/рек
(INF-15 v2 этап 2 - handoff/09_next_research/INF-15_grid_v2_brief.md
раздел 7, гипотезы C-004/C-005; INF-15 v3 - реки, гипотезы C-006/C-007 -
docs/preregistration/grid-v0.2.md §§3, 8; исход - docs/decisions/
INF-15.md D-015: C-006 подтверждена направленно (open_question), C-007
ОПРОВЕРГНУТА собственным заранее заданным критерием)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STORY_JSON = ROOT / "web" / "public" / "data" / "grid_story.json"
HIGHWAYS_GEOJSON = ROOT / "web" / "public" / "data" / "geo" / "grid_highways.geojson"
RIVERS_GEOJSON = ROOT / "web" / "public" / "data" / "geo" / "grid_rivers.geojson"

pytestmark = pytest.mark.skipif(
    not STORY_JSON.exists(), reason="etl.grid_story ещё не прогонялся")

BUDGET_STORY_KB = 100
BUDGET_HIGHWAYS_KB = 2048
BUDGET_RIVERS_KB = 2048


@pytest.fixture(scope="module")
def story():
    return json.loads(STORY_JSON.read_text())


def test_budgets():
    assert STORY_JSON.stat().st_size / 1024 <= BUDGET_STORY_KB
    assert HIGHWAYS_GEOJSON.stat().st_size / 1024 <= BUDGET_HIGHWAYS_KB
    assert RIVERS_GEOJSON.stat().st_size / 1024 <= BUDGET_RIVERS_KB


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


# --------------------------------------------------------------------
# v3: реки, C-006 (матрица река x дорога), C-007 (пояса удалённости) -
# docs/preregistration/grid-v0.2.md §8, docs/decisions/INF-15.md D-015
# --------------------------------------------------------------------

def test_rivers_geojson_valid():
    d = json.loads(RIVERS_GEOJSON.read_text())
    assert d["type"] == "FeatureCollection"
    assert len(d["features"]) > 50
    f0 = d["features"][0]
    assert f0["geometry"]["type"] == "LineString"
    lon, lat = f0["geometry"]["coordinates"][0]
    assert 20 < lon < 36 and 51 < lat < 57


def test_c007_river_distance_bands_sum_to_country(story):
    """Доли по 5 поясам должны в сумме давать ~100% населения страны в
    каждом году (полное разбиение растра на непересекающиеся пояса)."""
    bands = story["c007_river_distance"]["bands"]
    assert len(bands) == 5
    for key in ("share_1975_pct", "share_2020_pct"):
        total = sum(b[key] for b in bands if b[key] is not None)
        assert abs(total - 100.0) < 1.0


def test_c007_refuted_by_own_criterion(story):
    """D-015: критерий опровержения §8.1 - "пояс 0-2 км имеет бо́льшую
    долю населения, чем пояс 2-5 км" - сработал. Регресс-тест фиксирует
    именно это (честный провал, не повод скрыть находку)."""
    bands = story["c007_river_distance"]["bands"]
    share_0_2 = bands[0]["share_2020_pct"]
    share_2_5 = bands[1]["share_2020_pct"]
    assert share_0_2 > share_2_5   # опровержение C-007, как заявлено в тексте истории
    # при этом ТЕМП РОСТА в 2-5 км выше, чем у самой воды (частично
    # похоже на находку документа v3, но не то же самое утверждение)
    assert bands[1]["change_pct"] > bands[0]["change_pct"]


def test_c006_matrix_only_intersection_group_grows(story):
    """C-006: критерий опровержения §8.1 ("растёт более чем одна из
    четырёх групп" ИЛИ "группа река+дорога не растёт") НЕ сработал -
    растёт ровно группа пересечения."""
    groups = {g["id"]: g for g in story["c006_river_road_matrix"]["groups"]}
    assert set(groups) == {"both", "river_only", "road_only", "neither"}
    assert groups["both"]["change_pct"] > 0
    for gid in ("river_only", "road_only", "neither"):
        assert groups[gid]["change_pct"] < 0


def test_c006_independent_check_present_and_honest_about_sample_size(story):
    """Независимая проверка на городах (docs/preregistration/grid-v0.2.md
    §8.2) должна присутствовать и явно фиксировать размер групп - маленькая
    группа сравнения (n_rest) не должна маскироваться."""
    chk = story["c006_river_road_matrix"]["independent_check"]
    assert chk["n_cities_total"] > 150
    assert chk["n_both"] + chk["n_rest"] <= chk["n_cities_total"]
    assert "p_value" in chk and "direction_confirmed" in chk


def test_c007_cities_include_named_examples(story):
    cities = {c["id"]: c for c in story["c007_river_distance"]["cities"]}
    assert "c-minsk" in cities and "c-salihorsk" in cities and "c-maladziechna" in cities
    assert cities["c-salihorsk"]["is_exception"] is True
    assert cities["c-maladziechna"]["is_exception"] is True
    # значения обязаны быть реальными числами (не None, не хардкод в компоненте)
    for c in cities.values():
        assert isinstance(c["river_km"], (int, float))
        assert isinstance(c["road_km"], (int, float))


def test_islands_frames_cover_observed_years_and_2050(story):
    frames = story["islands_frames"]
    for y in (1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020):
        assert str(y) in frames
    assert "2050:base:A" in frames
    for url in frames.values():
        rel = url.lstrip("/")
        assert (ROOT / "web" / "public" / rel).exists()


def test_matrix_and_river_buffer_frames_exist(story):
    for key in ("matrix_frame", "river_buffer_frame", "rule500_frame"):
        rel = story[key].lstrip("/")
        assert (ROOT / "web" / "public" / rel).exists()
