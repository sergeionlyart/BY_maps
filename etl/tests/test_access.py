"""Тесты INF-04 `access`. Приёмка из TASK_SPEC: версия OSM и параметры
в манифесте; травел-таймы воспроизводимы скриптом; пояса и регрессия
согласованы с опубликованным access.json."""
import csv
import hashlib
import json

import pytest

from etl.access import (BELTS, belt_of, build, dijkstra, _hav,
                        OBL_CENTER_CITY)
from etl.common import ROOT

CURATED = ROOT / "data" / "curated"


@pytest.fixture(scope="session")
def result():
    return build()


@pytest.fixture(scope="session")
def published():
    return json.loads((ROOT / "web/public/data/access.json").read_text())


def test_haversine():
    """Минск - Брест по прямой ~ 327 км."""
    d = _hav(53.9023, 27.5619, 52.0938, 23.6852)
    assert 315 < d < 340, d


def test_dijkstra_toy():
    """Игрушечный граф: кратчайший путь через промежуточный узел."""
    adj = {1: [(2, 10.0), (3, 25.0)], 2: [(1, 10.0), (3, 10.0)],
           3: [(1, 25.0), (2, 10.0)]}
    d = dijkstra(adj, [1])
    assert d[3] == 20.0  # 1->2->3 короче прямого 1->3
    # мультиисточник: расстояние = минимум по источникам
    d2 = dijkstra(adj, [1, 3])
    assert d2[2] == 10.0


def test_belts_partition():
    """Пояса покрывают [0, inf) без дыр и перекрытий."""
    assert BELTS[0][0] == 0
    for (lo, hi, _), (lo2, _, _) in zip(BELTS, BELTS[1:]):
        assert hi == lo2
    assert belt_of(0) == "<45 мин"
    assert belt_of(44.9) == "<45 мин"
    assert belt_of(45) == "45-90 мин"
    assert belt_of(149.9) == "1,5-2,5 ч"
    assert belt_of(900) == ">2,5 ч"


def test_border_registry():
    """Реестр переходов: 15 записей, статусы согласованы с хронологией."""
    rows = list(csv.DictReader(open(CURATED / "border_crossings.csv")))
    assert len(rows) == 15
    n19 = sum(1 for r in rows if r["status_2019"] == "open")
    n_nadir = sum(1 for r in rows if r["status_nadir"] == "open")
    n26 = sum(1 for r in rows if r["status_2026"] == "open")
    assert (n19, n_nadir, n26) == (13, 4, 6)
    for r in rows:
        # закрытые к 2026 имеют дату и инициатора закрытия
        if r["status_2019"] == "open" and r["status_2026"] == "closed":
            assert r["closed_date"] and r["closed_by"], r["name_ru"]
        # реоткрытые - дату реоткрытия
        if r["closed_date"] and r["status_2026"] == "open":
            assert r["reopened_date"], r["name_ru"]
        assert 51 < float(r["lat"]) < 57 and 23 < float(r["lon"]) < 29


def test_osm_registry_manifest():
    """Приёмка: версия OSM-выгрузки и параметры графа зафиксированы."""
    reg = {r["id"]: r for r in
           csv.DictReader(open(ROOT / "data/raw/osm/registry.csv"))}
    pbf = reg["geofabrik_pbf"]
    assert "8c2f87148173f06fd144146079b99e54" in pbf["notes"]  # md5
    assert "2026-07-10" in pbf["notes"]                        # версия выгрузки
    graph = reg["graph_edges"]
    # хеш самого файла, не только его наличие в реестре
    h = hashlib.sha256(
        (ROOT / "data/raw/osm/graph_edges.csv.gz").read_bytes()).hexdigest()
    assert h == graph["sha256"]
    # скорости по классам задокументированы в реестре
    for s in ("105", "90", "75", "60", "45"):
        assert s in graph["notes"], s


def test_coverage_and_sanity(result):
    """118 районов; травел-таймы в правдоподобных коридорах."""
    rows = {r["id"]: r for r in result["rows"]}
    assert len(rows) == 118
    # якорные времена (Дейкстра по графу secondary+, консервативные скорости)
    assert 185 < rows["r-brescki"]["minsk"] < 235      # Минск-Брест ~3.5 ч
    assert 185 < rows["r-homielski"]["minsk"] < 235    # Минск-Гомель
    assert rows["r-minski"]["minsk"] == 0
    for t, r in rows.items():
        assert 0 <= r["minsk"] < 400, t
        assert r["eff"] <= r["minsk"] + 1e-9, t
        assert r["eu2019"] > 0 or t in ("r-brescki",), t
        # доступность ЕС в 2019 не хуже, чем в надир и в 2026
        assert r["euNadir"] >= r["eu2019"] - 1e-9, t
        assert r["eu2026"] >= r["eu2019"] - 1e-9, t
        # реоткрытия 11.2025: в 2026 не хуже надира
        assert r["eu2026"] <= r["euNadir"] + 1e-9, t


def test_belt_sizes(result):
    """Разбиение по эффективной доступности: все 118, пригород непуст."""
    prof = {p["belt"]: p["n"] for p in result["profile_eff"]}
    assert sum(prof.values()) == 118
    assert prof["<45 мин"] >= 20          # 10 хостов + пригороды
    assert prof[">2,5 ч"] <= 15           # дальняя периферия мала


def test_gradient_profile(result):
    """Ядро гипотезы INF-04: кольцо 1,5-2,5 ч хуже пригорода и хуже
    дальней периферии (немонотонность - «тень»)."""
    prof = {p["belt"]: p["median"] for p in result["profile_eff"]}
    assert prof["<45 мин"] > prof["1,5-2,5 ч"]
    assert prof[">2,5 ч"] > prof["1,5-2,5 ч"]
    # профиль до Минска: пригород Минска растёт
    prof_m = {p["belt"]: p["median"] for p in result["profile_minsk"]}
    assert prof_m["<45 мин"] > 0


def test_regression_reproducible(result, published):
    """Коэффициенты регрессии совпадают с опубликованными."""
    reg = result["reg"]
    pub = published["regression"]
    for i, b in enumerate(reg["beta"]):
        assert abs(b - pub["beta"][i]) < 5e-4, i
        assert abs(reg["se_hc1"][i] - pub["seHc1"][i]) < 5e-4, i
    assert reg["n"] == 118
    assert abs(reg["r2"] - pub["r2"]) < 5e-4
    # знаки поясов: пригород > 0, кольцо < 0 (к базе >2,5 ч)
    names = result["belt_names"]
    assert reg["beta"][1 + names.index("<45 мин")] > 0
    assert reg["beta"][1 + names.index("1,5-2,5 ч")] < 0


def test_published_consistency(result, published):
    """access.json согласован с build(): территории и надир."""
    assert published["version"]
    assert len(published["territories"]) == 118
    for r in result["rows"]:
        p = published["territories"][r["id"]]
        assert abs(p["minMinsk"] - r["minsk"]) < 1e-6, r["id"]
        assert abs(p["euDeltaNadir"] - r["eu_delta_nadir"]) < 1e-6, r["id"]
    # надир: гродненский пояс терял >1,5 ч к ЕС
    assert published["territories"]["r-hrodzienski"]["euDeltaNadir"] > 90
    # брестский коридор в модельном надире без потерь (короткий эпизод
    # закрытия Тересполя 12-25.09.2025 моделью не выделяется)
    assert published["territories"]["r-brescki"]["euDeltaNadir"] == 0


def test_travel_times_csv(published):
    """Кураторский CSV согласован с access.json."""
    rows = list(csv.DictReader(open(CURATED / "travel_times.csv")))
    assert len(rows) == 118
    for r in rows:
        p = published["territories"][r["territory_id"]]
        assert abs(float(r["min_minsk"]) - p["minMinsk"]) < 1e-6
        assert abs(float(r["min_eu_nadir"]) - p["euNadir"]) < 1e-6
        assert r["oblcenter"] in OBL_CENTER_CITY


def test_west30(published):
    """Запад-30: ближайшие к ЕС-2019; потери надира локализованы."""
    w30 = published["west30"]
    assert len(w30) == 30
    t = published["territories"]
    others = [k for k in t if k not in w30]
    max_w30 = max(t[k]["eu2019"] for k in w30)
    assert all(t[k]["eu2019"] >= max_w30 - 1e-9 for k in others)
    # локализация шока: и нулевые, и >1,5-часовые потери внутри запада-30
    deltas = [t[k]["euDeltaNadir"] for k in w30]
    assert min(deltas) == 0 and max(deltas) > 90
