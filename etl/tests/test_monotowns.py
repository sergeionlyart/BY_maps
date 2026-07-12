"""Тесты INF-06 `monotowns`. Приёмка из TASK_SPEC: реестр в пакете (CSV)
с построчными источниками; matched comparison воспроизводим; причинность
не заявляется."""
import csv
import json

import pytest

from etl.common import ROOT
from etl.monotowns import build, risk_band, OBL_CENTERS, DEP_WEIGHT

RAW = ROOT / "data" / "raw" / "monotowns"


@pytest.fixture(scope="session")
def result():
    return build()


@pytest.fixture(scope="session")
def published():
    return json.loads((ROOT / "web/public/data/monotowns.json").read_text())


@pytest.fixture(scope="session")
def data():
    return json.loads((ROOT / "web/public/data/data.json").read_text())["territories"]


def test_registry_sourced_and_valid(data):
    """46 записей; каждый city_id существует; ≥1 источник у каждой."""
    reg = json.loads((RAW / "registry.json").read_text())
    assert len(reg) == 46
    for p in reg:
        assert p["city_id"] in data, p["city_id"]
        assert data[p["city_id"]]["level"] == "city"
        assert len(p.get("sources", [])) >= 1, p["city_id"]
        assert p["mono_dependence"] in ("high", "medium", "low")
        for s in p.get("sanctions", []):
            assert s["jurisdiction"] and s["date"]


def test_curated_csv_matches_registry():
    """Плоский CSV согласован с registry.json и несёт источники."""
    reg = {p["city_id"] for p in
           json.loads((RAW / "registry.json").read_text())}
    rows = list(csv.DictReader(open(ROOT / "data/curated/monotowns.csv")))
    assert {r["city_id"] for r in rows} == reg
    for r in rows:
        assert int(r["n_sources"]) >= 1
        assert r["sources"].startswith("http")


def test_risk_band_logic():
    """Полоса риска: зависимость + санкции; границы 3/2/1/0."""
    assert risk_band("high", 3)[1] == "высокий"
    assert risk_band("high", 0)[1] == "повышенный"
    assert risk_band("medium", 1)[1] == "повышенный"
    assert risk_band("medium", 0)[1] == "умеренный"
    assert risk_band("low", 1)[1] == "умеренный"
    assert risk_band("low", 0)[1] == "низкий"


def test_towns_and_risk(result):
    """46 городов; полоса риска пересчитывается из зависимости+санкций."""
    towns = result["towns"]
    assert len(towns) == 46
    for t in towns:
        score = DEP_WEIGHT[t["dep"]] + (1 if t["nSanctions"] else 0)
        assert t["riskScore"] == score
        assert t["risk"] == risk_band(t["dep"], t["nSanctions"])[1]


def test_matched_controls_calipered(result):
    """Контроли не включают моногорода и облцентры; калипер по размеру:
    у кого нет сопоставимых - gap=None и controls=[]."""
    mono_ids = {t["id"] for t in result["towns"]}
    for t in result["towns"]:
        for c in t["controls"]:
            assert c not in mono_ids and c not in OBL_CENTERS, (t["id"], c)
        if t["gap"] is None:
            assert t["controls"] == [], t["id"]
        else:
            assert 1 <= len(t["controls"]) <= 8
        assert t["index"]["1989"] == 100.0


def test_index_matches_series(result, data):
    """Индекс города воспроизводится из рядов проекта (к 1989)."""
    for t in result["towns"][:10]:
        v = data[t["id"]]
        base = float(v["pop"]["1989"][0])
        for y in ("2019", "2026"):
            want = round(float(v["pop"][y][0]) / base * 100, 1)
            assert abs(t["index"][y] - want) < 1e-6, (t["id"], y)


def test_dependence_gradient(result):
    """АССОЦИАЦИЯ: среди сопоставимых по размеру моногородов высокая
    зависимость от одного завода связана с бОльшим отставанием от
    типовых, чем средняя (высокая gap < средняя gap)."""
    dep = result["aggregate"]["byDep"]
    assert dep["high"]["medianGap"] < dep["medium"]["medianGap"]
    assert dep["high"]["nMatched"] >= 10


def test_large_monotowns_unmatched(result):
    """Крупнейшие моногорода не с чем сравнивать по размеру (они и есть
    крупные города без облцентров) - честный gap=None, не подгонка."""
    unmatched = [t for t in result["towns"] if t["gap"] is None]
    assert len(unmatched) >= 10
    names = {t["ru"] for t in unmatched}
    assert "Солигорск" in names and "Жодино" in names


def test_published_consistency(result, published):
    assert published["version"]
    assert len(published["towns"]) == 46
    pub = {t["id"]: t for t in published["towns"]}
    for t in result["towns"]:
        assert abs((pub[t["id"]]["gap"] or 0) - (t["gap"] or 0)) < 1e-6, t["id"]
