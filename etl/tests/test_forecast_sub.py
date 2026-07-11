"""Тесты этапа 5: субрегиональный прогноз (уровни 2-3).

Инварианты: согласование районы+города=область, город<=район, стартовая
калибровка к официальным оценкам 2026, неизменность уровней 0-1,
бэктест-гейты районов и городов, свойства shrinkage/floor."""
import csv
import json

import pytest

from etl.common import ROOT

CURATED = ROOT / "data" / "curated"


@pytest.fixture(scope="session")
def fc():
    return json.loads((ROOT / "web/public/data/forecast.json").read_text())


@pytest.fixture(scope="session")
def data():
    return json.loads((ROOT / "web/public/data/data.json").read_text())["territories"]


@pytest.fixture(scope="session")
def obl_of():
    return {r["territory_id"]: r["oblast"]
            for r in csv.DictReader(open(CURATED / "age2019.csv"))}


OBLS = ["BY-BR", "BY-VI", "BY-HO", "BY-HR", "BY-MI", "BY-MA"]


def test_version_and_coverage(fc):
    assert fc["version"] == "v2026.2"
    terrs = fc["territories"]
    raions = [t for t in terrs if t.startswith("r-")]
    cities = [t for t in terrs if t.startswith("c-")]
    assert len(raions) == 118
    assert len(cities) >= 190, len(cities)  # 10 обл.подч. + ~186 долей + Минск + Орша/Полоцк
    for t in list(terrs)[:50]:
        for sid in ("base", "optimistic", "negative"):
            assert sid in terrs[t], t


def test_level01_unchanged(fc):
    """Контрольные значения уровней 0-1 = значения пакета v1.0.1 (этап 3)."""
    e = fc["territories"]["BY"]["base"]
    by = dict(zip(e["years"], e["pop"]))
    assert by[2051] == 7528557
    assert by[2075] == 5969883
    q = dict(zip(e["years"], e["q90"]))
    assert q[2075] == 6985592
    neg = dict(zip(*[fc["territories"]["BY"]["negative"][k] for k in ("years", "pop")]))
    assert neg[2075] == 4334254


def test_raions_sum_to_oblast(fc, obl_of):
    """Σ районов (экспортный периметр) = область, каждый год и сценарий."""
    terrs = fc["territories"]
    years = terrs["BY-BR"]["base"]["years"]
    for o in OBLS:
        rs = [t for t in terrs if t.startswith("r-") and obl_of.get(t) == o]
        assert len(rs) >= 16
        for sid in ("base", "optimistic", "negative"):
            for i in range(len(years)):
                s = sum(terrs[t][sid]["pop"][i] for t in rs)
                assert abs(s - terrs[o][sid]["pop"][i]) <= 5, (o, sid, years[i])


def test_city_not_above_raion(fc):
    """Город не превышает свой район (экспортные периметры)."""
    terrs = fc["territories"]
    cmap = {r["city_id"]: r["raion_id"]
            for r in csv.DictReader(open(CURATED / "city_raion.csv"))}
    for c, r in cmap.items():
        if c not in terrs or r not in terrs:
            continue
        for sid in ("base", "negative"):
            cp, rp = terrs[c][sid]["pop"], terrs[r][sid]["pop"]
            assert all(cv <= rv for cv, rv in zip(cp, rp)), (c, r, sid)


def test_start_calibrated_to_official(fc, data, obl_of):
    """Старт 2026 = официальная оценка: уровень 2 (районы и города обл.
    подчинения) откалиброван жёстко (1%); города уровня 3 - трендовые
    доли, допуск 5% (отклоняются только ряды, оборванные до 2026)."""
    terrs = fc["territories"]
    level2 = {t for t in obl_of if t.startswith(("r-", "c-"))}
    for t in terrs:
        if not t.startswith(("r-", "c-")) or t == "c-minsk":
            continue
        pops = data[t]["pop"]
        fact = pops.get("2026", pops[max(pops)])[0]
        model = terrs[t]["base"]["pop"][0]
        tol = 0.01 if t in level2 or t.startswith("r-") else 0.05
        assert abs(model - fact) / fact < tol, (t, model, fact)


def test_scenarios_ordered(fc):
    """На дальнем горизонте: optimistic >= base >= negative (районы)."""
    terrs = fc["territories"]
    bad = []
    for t in terrs:
        if not t.startswith("r-"):
            continue
        o = terrs[t]["optimistic"]["pop"][-1]
        b = terrs[t]["base"]["pop"][-1]
        n = terrs[t]["negative"]["pop"][-1]
        if not (o >= b >= n):
            bad.append(t)
    assert not bad, bad


def test_minsk_mirror(fc):
    assert fc["territories"]["c-minsk"]["base"]["pop"] == \
        fc["territories"]["BY-HM"]["base"]["pop"]


def test_backtest_gates():
    bt = json.loads((ROOT / "docs/notes/backtest_sub.json").read_text())
    r, c = bt["raions_2026"], bt["cities_2019"]
    assert r["gate_beats_naive"], (r["mape_model"], r["mape_naive"])
    assert r["mape_model"] < 3.0, r["mape_model"]
    assert r["n"] == 128
    assert c["gate_not_worse_than_naive"], (c["mape_model"], c["mape_naive"])
    assert c["n"] >= 180


def test_shrinkage_floor_units():
    """Юнит: floor/cap и чернобыльский вес в shrunk_ccr."""
    from etl.forecast.sub import shrunk_ccr, K_SHRINK, CCR_FLOOR, W_CAP_CHERNOBYL
    from etl.forecast import AGE_GROUPS
    p09 = {s: {g: 1000.0 for g in AGE_GROUPS} for s in ("m", "f")}
    obl = {"m": [1.0] * 14, "f": [1.0] * 14, "open": {"m": 0.5, "f": 0.6},
           "cwr04": {"m": 0.1, "f": 0.1}, "cwr59": {"m": 0.1, "f": 0.1}}
    # экстремально низкий CCR района прижимается к floor
    terr = {"m": [0.01] * 14, "f": [0.01] * 14, "open": {"m": 0.01, "f": 0.01},
            "cwr04": {"m": 0.001, "f": 0.001}, "cwr59": {"m": 0.001, "f": 0.001}}
    out = shrunk_ccr(terr, obl, p09, chernobyl=False)
    assert all(abs(r - CCR_FLOOR * 1.0) < 1e-9 for r in out["m"])
    # чернобыльский район: вес территории не выше W_CAP_CHERNOBYL
    terr2 = {"m": [2.0] * 14, "f": [2.0] * 14, "open": {"m": 2.0, "f": 2.0},
             "cwr04": {"m": 0.3, "f": 0.3}, "cwr59": {"m": 0.3, "f": 0.3}}
    out2 = shrunk_ccr(terr2, obl, p09, chernobyl=True)
    w = 1000.0 / (1000.0 + K_SHRINK)  # = 0.5 == W_CAP, вес не выше кэпа
    expected = min(w, W_CAP_CHERNOBYL) * 2.0 + (1 - min(w, W_CAP_CHERNOBYL)) * 1.0
    assert abs(out2["m"][0] - expected) < 1e-9


def test_no_dead_cities(fc, data):
    """Города с рядом, оборванным до 2019, не прогнозируются."""
    terrs = fc["territories"]
    for t in terrs:
        if t.startswith("c-") and t != "c-minsk":
            assert int(max(data[t]["pop"])) >= 2019, t
