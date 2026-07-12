"""Тесты INF-05 `migration`. Приёмка из TASK_SPEC: каждая цифра внешней
волны - с источником и датой обращения; оценки интервалами; по районам
зеркальная статистика не раскладывается."""
import csv
import json

import pytest

from etl.common import ROOT
from etl.migration import (build, external, interoblast_matrix, ladder,
                           oblast_flows, raion_net, ESTIMATES, NON_EU)

RAW_MIG = ROOT / "data" / "raw" / "migration"


@pytest.fixture(scope="session")
def data():
    return json.loads((ROOT / "web/public/data/data.json").read_text())["territories"]


@pytest.fixture(scope="session")
def result():
    return build()


@pytest.fixture(scope="session")
def published():
    return json.loads((ROOT / "web/public/data/migration.json").read_text())


def test_registry_covers_all_files():
    """Каждый завендоренный файл - в реестре с sha256."""
    reg = {r["notes"]: r for r in
           csv.DictReader(open(RAW_MIG / "registry.csv"))}
    files = [f.name for f in RAW_MIG.iterdir()
             if f.name != "registry.csv" and not f.name.startswith(".")]
    assert set(files) == set(reg)
    for r in reg.values():
        assert len(r["sha256"]) == 64
        assert r["accessed"] == "2026-07-12"


def test_raion_net_coverage():
    """128 территорий (118 районов + 10 городов обл. подчинения);
    дыра 2020-2023 (Белстат не публиковал), 1994-2019 + 2024-2025 есть."""
    net = raion_net()
    assert len(net) == 128
    raions = [t for t in net if t.startswith("r-")]
    cities = [t for t in net if t.startswith("c-")]
    assert len(raions) == 118 and len(cities) == 10
    for t, ser in net.items():
        years = set(ser)
        assert not years & {2020, 2021, 2022, 2023}, t
        assert {2015, 2019, 2024, 2025} <= years, t


def test_raion_sums_match_oblast():
    """Сумма сальдо районов области = сальдо области (2019 и 2024)."""
    net = raion_net()
    flows = oblast_flows()
    # области -> их районы через registry.py (parent в data.json)
    data = json.loads((ROOT / "web/public/data/data.json").read_text())["territories"]
    for obl in ("BY-BR", "BY-VI", "BY-HO", "BY-HR", "BY-MI", "BY-MA"):
        for y in (2019, 2024):
            kids = [t for t in net
                    if data.get(t, {}).get("parent") == obl
                    or data.get(data.get(t, {}).get("raion") or "", {}).get("parent") == obl
                    or data.get(t, {}).get("level") == "city"
                    and data.get(t, {}).get("parent") == obl]
            s = sum(net[t].get(y, 0) for t in kids)
            want = flows[obl]["Всего по всем потокам миграции"][y]
            assert s == want, (obl, y, s, want)


def test_official_intl_positive():
    """Официальное международное сальдо РБ положительно во все годы -
    ключевой контраст с зеркальной статистикой."""
    flows = oblast_flows()
    intl = flows["BY"]["Международная миграция"]
    for y, v in intl.items():
        if y >= 2010:
            assert v > 0, (y, v)
    assert intl[2019] == 13_870


def test_ladder_consistency(result, data):
    """Ярусы дают полное разбиение страны; урбанизация сходится с
    официальными долями переписей (допуск 1,5 п.п.)."""
    l = result["ladder"]
    official = {1999: 69.3, 2009: 74.5, 2019: 77.6}
    for i, y in enumerate(l["years"]):
        total = sum(l["tiers"][k][i] for k in l["tiers"])
        want = float(data["BY"]["pop"][str(y)][0])
        assert abs(total - want) < 1, (y, total, want)
        if y in official:
            urban = total - l["tiers"]["rural"][i]
            assert abs(urban / total * 100 - official[y]) < 1.5, y


def test_matrix_invariants(result):
    """F602: 42 потока, 1 459 418 переходов; Минск - единственный
    нетто-магнит; нетто по стране = 0."""
    m = result["matrix"]
    assert len(m["flows"]) == 42
    assert m["total"] == 1_459_418
    assert sum(m["net"].values()) == 0
    assert m["net"]["BY-HM"] > 0
    assert all(v < 0 for k, v in m["net"].items() if k != "BY-HM")
    assert m["flows"][0] == {"from": "BY-MI", "to": "BY-HM", "n": 310_081}


def test_external_sources(result):
    """Приёмка: каждая цифра внешней волны с источником, датой и
    снапшотом в реестре; оценки - интервалами."""
    reg = {r["notes"] for r in csv.DictReader(open(RAW_MIG / "registry.csv"))}
    for e in ESTIMATES:
        assert e["low"] <= e["high"]
        assert e["who"] and e["published"] and e["src"]
        assert e["snap"] in reg, e["snap"]
    for n in NON_EU:
        assert n["stock"] > 0 and n["asof"] and n["src"]
        assert n["snap"] in reg, n["snap"]
    # провенанс: сток Грузии и Сербии реально присутствует в своём
    # снапшоте (регрессия на перепутанный указатель, аудит INF-05)
    ge = next(n for n in NON_EU if n["geo"] == "GE")
    snap = (RAW_MIG / ge["snap"]).read_text(errors="ignore")
    assert "12 808" in snap or "12808" in snap, "снапшот Грузии не содержит 12 808"
    rs = next(n for n in NON_EU if n["geo"] == "RS")
    snap = (RAW_MIG / rs["snap"]).read_text(errors="ignore")
    assert "1159" in snap or "1 159" in snap, "снапшот Сербии не содержит 1159"
    ext = result["external"]
    assert ext["accessed"] == "2026-07-12"
    # коридор спеки 100-600 тыс. покрыт оценками
    assert min(e["low"] for e in ESTIMATES) == 100_000
    assert max(e["high"] for e in ESTIMATES) == 600_000


def test_eurostat_anchors(result):
    """Контрольные точки Eurostat: сток ЕС-27 и пик первичных ВНЖ."""
    ext = result["external"]
    assert ext["euStock"]["2019"] == 133_889
    assert ext["euStock"]["2024"] == 386_834
    assert ext["euFirst"]["2022"] == 311_516
    pl = next(c for c in ext["countries"] if c["geo"] == "PL")
    assert pl["latest"] == 251_362 and pl["s2019"] == 55_902


def test_interval_and_timeline(result):
    """Интервал WP-F3 не пересчитан заново, а импортирован; кумулятив
    монотонный и сходится к интервалу."""
    ext = result["external"]
    assert (ext["interval"]["low"], ext["interval"]["mid"],
            ext["interval"]["high"]) == (178_285, 269_955, 415_883)
    tl = ext["timeline"]
    for k in ("low", "mid", "high"):
        assert all(a <= b for a, b in zip(tl[k], tl[k][1:]))
        assert tl[k][-1] == ext["interval"][k]


def test_no_raion_breakdown_of_mirror(published):
    """Ограничение спеки: зеркальная статистика по районам не
    раскладывается - в раздаче нет района с полем внешнего оттока."""
    for tid, r in published["raions"].items():
        assert set(r) <= {"rate1519", "rate2425", "net"}, tid


def test_published_consistency(result, published):
    assert published["version"]
    assert len(published["raions"]) == 128
    assert published["matrix"]["total"] == result["matrix"]["total"]
    assert published["external"]["euStock"] == {
        str(y): v for y, v in result["external"]["euStock"].items()}
