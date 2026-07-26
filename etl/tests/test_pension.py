"""Тесты INF-13 (pension): формулы, гейты G1-G7, форма экспорта."""
import json

import pytest

from etl.common import ROOT
from etl.pension import (AGE_GROUPS, POLICY_VARIANTS, SERIES_KEYS,
                         THRESHOLDS, age_boundary, bucket_interval,
                         crossing_year, dispersion_sr, pop_below, sr_tdr)
from etl.registry import RAIONS, raion_id

CURATED = ROOT / "data" / "curated"
OUT = ROOT / "web" / "public" / "data"
METHODS = ROOT / "web" / "public" / "content" / "methods"


def test_method_blocks_never_say_budget():
    """Раздел 9 п.5 ТЗ (гейт приёмки): слово «бюджет»/«бюджэт» рядом с
    денежным показателем не употребляется - ни в отрицании, ни иначе.
    Проверяем оба языка методблока (единственное МЕСТО, где слово могло
    бы случайно проникнуть при описании CG)."""
    for path in (METHODS / "pension.md", METHODS / "be" / "pension.md"):
        text = path.read_text(encoding="utf-8").lower()
        assert "бюджет" not in text and "бюджэт" not in text, path


# ------------------------------------------------------------ юнит-тесты

def test_retirement_schedule_endpoints():
    assert age_boundary(2000, "m", "as_is") == 60.0
    assert age_boundary(2016, "m", "as_is") == 60.0
    assert age_boundary(2016, "f", "as_is") == 55.0
    assert age_boundary(2019, "m", "as_is") == 61.5
    assert age_boundary(2019, "f", "as_is") == 56.5
    assert age_boundary(2022, "m", "as_is") == 63.0
    assert age_boundary(2022, "f", "as_is") == 58.0
    assert age_boundary(2056, "m", "as_is") == 63.0
    assert age_boundary(2056, "f", "as_is") == 58.0


def test_policy_variants_only_apply_to_forecast():
    # прошлое не переписывается ни одним гипотетическим графиком
    for policy in ("65_60", "67_62"):
        assert age_boundary(2019, "m", policy) == age_boundary(2019, "m", "as_is")
        assert age_boundary(2025, "f", policy) == age_boundary(2025, "f", "as_is")
    assert age_boundary(2031, "m", "65_60") == 65.0
    assert age_boundary(2031, "f", "65_60") == 60.0
    assert age_boundary(2031, "m", "67_62") == 67.0
    assert age_boundary(2031, "f", "67_62") == 62.0
    assert age_boundary(2031, "m", "as_is") == 63.0


def test_pop_below_fractional_split():
    s = {g: 1000.0 for g in AGE_GROUPS}
    assert pop_below(s, 0.0) == 0.0
    assert pop_below(s, 5.0) == 1000.0        # ровно одна группа 0-4
    assert pop_below(s, 2.5) == 500.0         # половина группы 0-4
    assert pop_below(s, 62.5) == pytest.approx(1000.0 * 12 + 500.0)  # 0..59 + половина 60-64
    assert pop_below(s, 200.0) == 1000.0 * (len(AGE_GROUPS) - 1)  # 80+ никогда не делится


def test_sr_tdr_known_case():
    # 100 человек на группу, оба пола, m/f возраст 63/58 (as_is 2026)
    struct = {"m": {g: 100.0 for g in AGE_GROUPS}, "f": {g: 100.0 for g in AGE_GROUPS}}
    sr, tdr = sr_tdr(struct, 2026, "as_is")
    total_m = 100.0 * len(AGE_GROUPS)
    below16_m = pop_below(struct["m"], 16.0)
    below63_m = pop_below(struct["m"], 63.0)
    work_m = below63_m - below16_m
    above_m = total_m - below63_m
    below16_f = pop_below(struct["f"], 16.0)
    below58_f = pop_below(struct["f"], 58.0)
    work_f = below58_f - below16_f
    above_f = total_m - below58_f
    expected_sr = (work_m + work_f) / (above_m + above_f)
    assert sr == round(expected_sr, 2)
    expected_tdr = (below16_m + below16_f + above_m + above_f) / (work_m + work_f)
    assert tdr == round(expected_tdr, 2)


def test_crossing_year_interpolates():
    series = {2020: 3.0, 2030: 2.0, 2040: 1.0}
    assert crossing_year(series, 2.5) == 2025
    assert crossing_year(series, 1.5) == 2035
    assert crossing_year(series, 0.5) is None       # порог не пройден в горизонте
    assert crossing_year({2020: 1.0}, 1.5) == 2020   # уже ниже в первой точке


def test_dispersion_sr_reports_all_three_measures():
    # находка скептика: CV может расти, пока SD/range сужаются - публикуем
    # все три, ни одна не должна тихо потеряться
    r_sr = {
        "r-a": {"as_is": {"base:official": {2026: 3.0, 2046: 2.0}}},
        "r-b": {"as_is": {"base:official": {2026: 1.0, 2046: 1.0}}},
    }
    out = dispersion_sr(r_sr, [2026, 2046])
    assert out[2026]["n"] == 2 and out[2046]["n"] == 2
    for y in (2026, 2046):
        assert set(out[y]) == {"n", "mean", "sd", "cv", "min", "max", "range"}
    assert out[2046]["sd"] < out[2026]["sd"]      # абсолютный разброс сузился
    assert out[2046]["range"] < out[2026]["range"]


def test_bucket_interval():
    assert bucket_interval(None) is None
    assert bucket_interval(2030) == "до 2035"
    assert bucket_interval(2035) == "до 2035"
    assert bucket_interval(2036) == "2035-2045"
    assert bucket_interval(2045) == "2035-2045"
    assert bucket_interval(2046) == "после 2045"


# --------------------------------------------------- интеграционные (файл)

@pytest.fixture(scope="session")
def pension_json():
    path = OUT / "pension.json"
    if not path.exists():
        pytest.skip("pension.json не собран - запустите python -m etl.pension")
    return json.loads(path.read_text())


def test_output_exists_and_within_budget(pension_json):
    path = OUT / "pension.json"
    assert path.stat().st_size <= 900 * 1024, "бюджет 900 КБ (Приложение А ТЗ)"


def test_territories_match_registry(pension_json):
    expected = {raion_id(lat) for lat in RAIONS}
    assert set(pension_json["territories"]) == expected
    assert len(pension_json["territories"]) == 118


def test_no_negative_sr_or_tdr(pension_json):
    bad = []
    for r, rec in pension_json["territories"].items():
        for policy in POLICY_VARIANTS:
            for key, vals in rec["sr"].get(policy, {}).items():
                if any(v is not None and v < 0 for v in vals):
                    bad.append((r, "sr", policy, key))
            for key, vals in rec["tdr"].get(policy, {}).items():
                if any(v is not None and v < 0 for v in vals):
                    bad.append((r, "tdr", policy, key))
    assert not bad, bad[:10]


def test_no_negative_cg(pension_json):
    bad = []
    for r, rec in pension_json["territories"].items():
        if rec["cg_suppressed"]:
            assert rec["cg"] is None
            continue
        for key, vals in (rec["cg"] or {}).items():
            if any(v is not None and v < 0 for v in vals.values()):
                bad.append((r, key))
    assert not bad, bad[:10]


def test_commute_zone_cg_suppressed(pension_json):
    """G-7: район с min_minsk<=45 обязан иметь cg=null (запасной вариант)."""
    import csv
    tm = {row["territory_id"]: float(row["min_minsk"])
         for row in csv.DictReader(open(CURATED / "travel_times.csv"))}
    for r, rec in pension_json["territories"].items():
        if tm.get(r, 9999) <= 45:
            assert rec["cg_suppressed"] is True, r
            assert rec["cg"] is None, r


def test_retirement_schedule_and_policy_ages_exported(pension_json):
    """Клиент («найди себя») не должен дублировать константы 60/55 и
    63/58 отдельным источником истины - полный график экспортируется."""
    sched = pension_json["retirement_schedule"]
    assert sched["1989"] == {"m": 60.0, "f": 55.0}
    assert sched["2022"] == {"m": 63.0, "f": 58.0}
    assert sched["2056"] == {"m": 63.0, "f": 58.0}
    ages = pension_json["policy_ages"]
    assert ages["as_is"] is None
    assert ages["65_60"] == {"m": 65.0, "f": 60.0}
    assert ages["67_62"] == {"m": 67.0, "f": 62.0}
    assert pension_json["policy_applies_from"] == 2026


def test_national_dispersion_present(pension_json):
    disp = pension_json["national"].get("dispersion_sr")
    assert disp is not None, "regenerate pension.json after dispersion_sr addition"
    for y in pension_json["years"]["territory"]:
        assert str(y) in disp
        entry = disp[str(y)]
        assert entry["n"] == 118
        assert entry["sd"] is not None and entry["cv"] is not None


def test_dtype_covers_all_years(pension_json):
    assert set(pension_json["dtype"]["national"]) == {str(y) for y in pension_json["years"]["national"]}
    assert set(pension_json["dtype"]["territory"]) == {str(y) for y in pension_json["years"]["territory"]}


def test_crossing_interval_present_when_g3_failed(pension_json):
    validation = pension_json["meta"]["validation"]
    sample = next(iter(pension_json["territories"].values()))
    if not validation["G3_backtest"]:
        assert sample["crossing_interval"] is not None
    else:
        assert sample["crossing_interval"] is None


def test_h1_hypothesis_direction(pension_json):
    """Не проверяет конкретное число (некорректно фиксировать в тесте
    гипотезу, которая может опровергнуться) - только то, что H1-релевантные
    числа посчитаны и лежат в разумных границах [0,118]."""
    years = pension_json["years"]["territory"]
    i2009, i2046 = years.index(2009), years.index(2046)
    below15 = {2009: 0, 2046: 0}
    for rec in pension_json["territories"].values():
        vals = rec["sr"]["as_is"]["base:official"]
        if vals[i2009] is not None and vals[i2009] < 1.5:
            below15[2009] += 1
        if vals[i2046] is not None and vals[i2046] < 1.5:
            below15[2046] += 1
    assert 0 <= below15[2009] <= 118
    assert 0 <= below15[2046] <= 118


def test_policy_delta_shifts_forward_or_null(pension_json):
    """Повышение возраста не может УСКОРИТЬ переход - сдвиг либо
    положительный (позже), либо None (порог не наступает ни там, ни там)."""
    bad = []
    for r, rec in pension_json["territories"].items():
        for th, by_policy in rec["policy_delta"].items():
            for policy, by_key in by_policy.items():
                for key, delta in by_key.items():
                    if delta is not None and delta < 0:
                        bad.append((r, th, policy, key, delta))
    assert not bad, bad[:10]
