"""Тесты прогноза (WP-F2/F4/F5): инварианты движка и обязательные гейты."""
import json

import pytest

from etl.common import ROOT
from etl.forecast import TERRITORIES, AGE_GROUPS, FERTILE
from etl.forecast.data import jumpoff_2026, mortality_mx, census_structure
from etl.forecast.lifetable import e0, scale_to_e0, survival_5y
from etl.forecast.ccmpp import project_step, total
from etl.forecast.migration import internal_net_per_year
from etl.forecast.run import load_scenarios, run_scenario
from etl.forecast.backtest import evaluate


@pytest.fixture(scope="session")
def scens():
    return load_scenarios()


@pytest.fixture(scope="session")
def base_series(scens):
    return run_scenario(scens["base"])


def test_lifetable_matches_hmd():
    mx = mortality_mx(2018)
    assert abs(e0(mx["m"]) - 69.3) < 0.3   # HMD 2018: 69.2-69.3
    assert abs(e0(mx["f"]) - 79.4) < 0.3


def test_scale_to_e0_converges():
    mx = mortality_mx(2018)
    for target in (72.0, 76.5, 80.0):
        assert abs(e0(scale_to_e0(mx["m"], target)) - target) < 0.01


def test_cohorts_never_grow_without_migration():
    """Без миграции когорта не может вырасти (только дожитие)."""
    pop = {s: dict(v) for s, v in jumpoff_2026()["BY-MI"].items()}
    mx = mortality_mx(2018)
    surv = {s: survival_5y(mx[s]) for s in ("m", "f")}
    new, _ = project_step(pop, surv, {g: 50.0 for g in FERTILE}, None)
    for s in ("m", "f"):
        for g_from, g_to in zip(AGE_GROUPS[:-2], AGE_GROUPS[1:-1]):
            assert new[s][g_to] <= pop[s][g_from] + 1e-6, (s, g_from)
        assert new[s]["80+"] <= pop[s]["75-79"] + pop[s]["80+"] + 1e-6


def test_no_negative_populations(base_series):
    for t, pts in base_series.items():
        for y, v in pts.items():
            assert v >= 0, (t, y)


def test_country_equals_sum_of_oblasts(base_series):
    for y in base_series["BY"]:
        s = sum(base_series[t][y] for t in TERRITORIES)
        assert abs(s - base_series["BY"][y]) < 1.0, y


def test_internal_migration_zero_sum():
    net = internal_net_per_year()
    total_net = sum(sum(a.values()) for a in net.values())
    assert abs(total_net) < 1e-6
    # Минск - чистый реципиент
    assert sum(net["BY-HM"].values()) > 0


def test_jumpoff_matches_official():
    j = jumpoff_2026()
    country = sum(total(j[t]) for t in TERRITORIES)
    assert round(country) == 9_056_080  # оценка Белстата на 01.01.2026


def test_scenario_ordering(scens):
    """optimistic > base > negative на всём горизонте."""
    res = {sid: run_scenario(s)["BY"] for sid, s in scens.items()}
    for y in res["base"]:
        if y == 2026:
            continue
        assert res["optimistic"][y] > res["base"][y] > res["negative"][y], y


def test_wpf4_calibration_gates(scens):
    """WP-F4: base-2050 в +-3% от медианы WPP; optimistic <= high;
    negative < low."""
    import csv
    wpp = {}
    for r in csv.DictReader(open(ROOT / "data/raw/wpp2024/blr_total_all_variants.csv")):
        wpp.setdefault(r["Variant"], {})[int(r["Time"])] = float(r["PopTotal"])
    res = {sid: run_scenario(s)["BY"] for sid, s in scens.items()}
    base_2050 = res["base"][2051] / 1000
    assert abs(base_2050 / wpp["Medium"][2050] - 1) <= 0.03, base_2050
    assert res["optimistic"][2051] / 1000 <= wpp["High"][2050] * 1.01
    assert res["negative"][2051] / 1000 < wpp["Low"][2050]


def test_wpf5_backtest_gates():
    """WP-F5: национальный итог бэктеста +-2%; MAPE лучше наивного."""
    rep = evaluate()
    assert rep["gates"]["national_within_2pct"], rep["national"]
    assert rep["gates"]["beats_naive_mape"], (rep["mape_model"], rep["mape_naive"])


def test_forecast_json_fresh():
    """Опубликованный forecast.json соответствует пересчёту."""
    published = json.loads((ROOT / "web/public/data/forecast.json").read_text())
    assert published["version"] == "v2026.3"
    assert published["horizon"] == [2026, 2075]
    assert set(published["scenarios"]) == {"base", "optimistic", "negative"}
    t = published["territories"]
    # уровни 0-1 присутствуют; уровни 2-3 (районы/города) - этап 5
    assert set(TERRITORIES + ["BY"]) <= set(t)
    for terr in TERRITORIES + ["BY"]:
        base = t[terr]["base"]
        assert base["years"][0] == 2026 and base["years"][-1] == 2075
        assert len(base["pop"]) == len(base["years"])
        assert "q10" in base and "q90" in base
        for lo, mid, hi in zip(base["q10"], base["pop"], base["q90"]):
            assert lo <= mid <= hi
    # стартовая точка = официальная оценка
    assert t["BY"]["base"]["pop"][0] == 9_056_080


def test_deterministic(scens):
    a = run_scenario(scens["base"])["BY"][2076]
    b = run_scenario(scens["base"])["BY"][2076]
    assert a == b
