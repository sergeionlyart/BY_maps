"""Тесты этапа 0 (INF-13/14): районная возрастная деталь прогноза.

Гейты из Приложения А ТЗ INF-13: сумма районов = область +-0,1% по каждой
группе/году/полу/сценарию; сумма по возрастам = итог района в forecast.json
+-0,1%; нет отрицательных; номенклатура совпадает с реестром."""
import csv
import json

import pytest

from etl.common import ROOT
from etl.forecast import AGE_GROUPS

CURATED = ROOT / "data" / "curated"
OBLS = ["BY-BR", "BY-VI", "BY-HO", "BY-HR", "BY-MI", "BY-MA"]


@pytest.fixture(scope="session")
def raion_age():
    return json.loads(
        (CURATED / "forecast_age_raion_v2026_4.json").read_text())


@pytest.fixture(scope="session")
def fc():
    return json.loads((ROOT / "web/public/data/forecast.json").read_text())


@pytest.fixture(scope="session")
def obl_of():
    return {r["territory_id"]: r["oblast"]
            for r in csv.DictReader(open(CURATED / "age2019.csv"))}


@pytest.fixture(scope="session")
def obl_targets():
    """Пересчитывает возрастно-половую структуру каждой области для всех
    (сценарий, старт) - независимый от sub.py путь (ядро CCMPP уровня 0-1),
    используется только как эталон сравнения в тестах."""
    from etl.forecast.run import (load_scenarios, run_scenario,
                                  jumpoff_adjusted, RAION_AGE_YEARS)
    scens = load_scenarios()
    adj_jump, _ = jumpoff_adjusted()
    out = {}
    for sid, s in scens.items():
        _, structs = run_scenario(s, keep_structures=True)
        out[f"{sid}:official"] = {
            o: interp(structs[o], RAION_AGE_YEARS) for o in OBLS}
        _, adj_structs = run_scenario(s, keep_structures=True, jumpoff=adj_jump)
        out[f"{sid}:adjusted"] = {
            o: interp(adj_structs[o], RAION_AGE_YEARS) for o in OBLS}
    return out


def interp(traj: dict, years: list[int]) -> dict:
    from etl.forecast.sub import interp_struct
    return {y: interp_struct(traj, y) for y in years}


def test_nomenclature_matches_registry(raion_age):
    from etl.registry import RAIONS, raion_id
    expected = {raion_id(lat) for lat in RAIONS}
    got = set(raion_age["territories"])
    assert got == expected, (got - expected, expected - got)
    assert len(got) == 118


def test_structure_shape(raion_age):
    assert raion_age["age_groups"] == AGE_GROUPS
    assert raion_age["node_years"] == [2026, 2031, 2036, 2041, 2046, 2051, 2056]
    assert set(raion_age["scenarios"]) == {"base", "optimistic", "negative"}
    assert set(raion_age["jumpoffs"]) == {"official", "adjusted"}
    r = next(iter(raion_age["territories"].values()))
    assert set(r) == {f"{sid}:{jo}" for sid in raion_age["scenarios"]
                      for jo in raion_age["jumpoffs"]}
    for year_map in r.values():
        assert set(year_map) == {str(y) for y in raion_age["node_years"]}
        for cell in year_map.values():
            assert set(cell) == {"m", "f"}
            assert len(cell["m"]) == len(AGE_GROUPS)
            assert len(cell["f"]) == len(AGE_GROUPS)


def test_no_negative_populations(raion_age):
    bad = []
    for t, series in raion_age["territories"].items():
        for key, year_map in series.items():
            for y, cell in year_map.items():
                if any(v < 0 for v in cell["m"] + cell["f"]):
                    bad.append((t, key, y))
    assert not bad, bad[:10]


def test_raion_sum_equals_forecast_json_total(raion_age, fc):
    """Сумма по возрастам района = итог района в forecast.json +-0.1%
    (только official - у forecast.json нет районного adjusted)."""
    terrs = fc["territories"]
    bad = []
    for t, series in raion_age["territories"].items():
        pts = dict(zip(terrs[t]["base"]["years"], terrs[t]["base"]["pop"]))
        for y_str, cell in series["base:official"].items():
            y = int(y_str)
            s = sum(cell["m"]) + sum(cell["f"])
            ref = pts[y]
            if ref > 0 and abs(s - ref) / ref > 0.001:
                bad.append((t, y, s, ref))
    assert not bad, bad[:10]


def test_raions_sum_to_oblast_by_cell(raion_age, obl_of, obl_targets):
    """Сумма районов области = целевая возрастно-половая структура области
    (+-0.1%), по каждой группе/году/полу/сценарию/старту."""
    bad = []
    checked = 0
    for key, obl_map in obl_targets.items():
        for o in OBLS:
            rs = [t for t in raion_age["territories"] if obl_of.get(t) == o]
            assert len(rs) >= 16, (o, len(rs))
            for y in raion_age["node_years"]:
                target = obl_map[o][y]
                for s in ("m", "f"):
                    for i, g in enumerate(AGE_GROUPS):
                        got = sum(raion_age["territories"][t][key][str(y)][s][i]
                                 for t in rs)
                        want = target[s][g]
                        checked += 1
                        if want > 50 and abs(got - want) / want > 0.001:
                            bad.append((key, o, y, s, g, got, want))
    assert checked > 1000
    assert not bad, bad[:10]
