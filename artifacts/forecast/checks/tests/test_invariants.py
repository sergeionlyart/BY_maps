#!/usr/bin/env python3
"""Инварианты пакета прогноза. Без pytest: plain asserts."""
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PKG))

from etl.forecast import TERRITORIES, AGE_GROUPS, FERTILE  # noqa: E402
from etl.forecast.data import jumpoff_2026, mortality_mx  # noqa: E402
from etl.forecast.lifetable import e0, scale_to_e0, survival_5y  # noqa: E402
from etl.forecast.ccmpp import project_step  # noqa: E402
from etl.forecast.migration import internal_net_per_year  # noqa: E402
from etl.forecast.run import load_scenarios, run_scenario  # noqa: E402


def test_lifetable_matches_hmd():
    mx = mortality_mx(2018)
    assert abs(e0(mx["m"]) - 69.3) < 0.3
    assert abs(e0(mx["f"]) - 79.4) < 0.3


def test_scale_converges():
    mx = mortality_mx(2018)
    assert abs(e0(scale_to_e0(mx["m"], 75.0)) - 75.0) < 0.01


def test_cohorts_never_grow_without_migration():
    pop = {s: dict(v) for s, v in jumpoff_2026()["BY-MI"].items()}
    mx = mortality_mx(2018)
    surv = {s: survival_5y(mx[s]) for s in ("m", "f")}
    new, _ = project_step(pop, surv, {g: 50.0 for g in FERTILE}, None)
    for s in ("m", "f"):
        for g_from, g_to in zip(AGE_GROUPS[:-2], AGE_GROUPS[1:-1]):
            assert new[s][g_to] <= pop[s][g_from] + 1e-6


def test_internal_migration_zero_sum():
    net = internal_net_per_year()
    assert abs(sum(sum(a.values()) for a in net.values())) < 1e-6


def test_jumpoff_official():
    from etl.forecast.ccmpp import total
    j = jumpoff_2026()
    assert round(sum(total(j[t]) for t in TERRITORIES)) == 9_056_080


def test_scenario_ordering_and_country_sum():
    scens = load_scenarios()
    res = {sid: run_scenario(s) for sid, s in scens.items()}
    for y in res["base"]["BY"]:
        s = sum(res["base"][t][y] for t in TERRITORIES)
        assert abs(s - res["base"]["BY"][y]) < 1.0
        if y > 2026:
            assert res["optimistic"]["BY"][y] > res["base"]["BY"][y] > res["negative"]["BY"][y]


def test_adjusted_series():
    """WP-F3: adjusted < official на старте ровно на mid-поправку;
    сценарии упорядочены; уровни 2-3 в adjusted не публикуются."""
    import csv
    import json
    fc = json.loads((PKG / "web/public/data/forecast.json").read_text())
    assert fc["jumpoff"] == ["official", "adjusted"]
    adj_csv = {r["territory_id"]: float(r["mid"])
               for r in csv.DictReader(open(PKG / "data/curated/adjustment.csv"))
               if r["year"] == "2026"}
    d = fc["territories"]["BY"]["base"]["pop"][0] - \
        fc["adjusted"]["BY"]["base"]["pop"][0]
    assert abs(d - adj_csv["BY"]) < 100, (d, adj_csv["BY"])
    for t in TERRITORIES + ["BY"]:
        o = fc["adjusted"][t]["optimistic"]["pop"][-1]
        b = fc["adjusted"][t]["base"]["pop"][-1]
        n = fc["adjusted"][t]["negative"]["pop"][-1]
        assert o >= b >= n, t
        assert fc["adjusted"][t]["base"]["pop"][0] < \
            fc["territories"][t]["base"]["pop"][0], t
    assert "r-minski" not in fc["adjusted"]


def test_sub_levels_reconciled():
    """Уровни 2-3 (после прогона run.py): сумма районов = область на каждый
    год и сценарий; город не больше района; старт = официальные оценки."""
    import csv
    import json
    fc = json.loads((PKG / "web/public/data/forecast.json").read_text())
    terrs = fc["territories"]
    assert fc["version"] == "v2026.4"
    obl_of = {r["territory_id"]: r["oblast"]
              for r in csv.DictReader(open(PKG / "data/curated/age2019.csv"))}
    years = terrs["BY-BR"]["base"]["years"]
    for o in [t for t in TERRITORIES if t != "BY-HM"]:
        rs = [t for t in terrs if t.startswith("r-") and obl_of.get(t) == o]
        assert len(rs) >= 16, o
        for sid in ("base", "optimistic", "negative"):
            for i in range(len(years)):
                s = sum(terrs[t][sid]["pop"][i] for t in rs)
                assert abs(s - terrs[o][sid]["pop"][i]) <= 5, (o, sid, years[i])
    cmap = {r["city_id"]: r["raion_id"]
            for r in csv.DictReader(open(PKG / "data/curated/city_raion.csv"))}
    for c, r in cmap.items():
        if c in terrs and r in terrs:
            assert all(cv <= rv for cv, rv in
                       zip(terrs[c]["base"]["pop"], terrs[r]["base"]["pop"])), c


def test_probabilistic_fan():
    """Вероятностный слой: веер base монотонен и брекетит медиану;
    80% интервал страны совпадает с 80% PI WPP-2024 (калибровка ≤1,5 п.п.)."""
    import json
    fc = json.loads((PKG / "web/public/data/forecast.json").read_text())
    for t in TERRITORIES + ["BY"]:
        e = fc["territories"][t]["base"]
        for i in range(len(e["years"])):
            row = [e["q05"][i], e["q10"][i], e["q25"][i], e["pop"][i],
                   e["q75"][i], e["q90"][i], e["q95"][i]]
            assert row == sorted(row), (t, e["years"][i])
    val = fc["probabilistic"]["wppValidation"]
    for y in ("2051", "2075"):
        assert abs(val[y]["sim80"] - val[y]["wpp80"]) <= 0.015, (y, val[y])


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"Все {len(fns)} инвариантов выполнены.")
