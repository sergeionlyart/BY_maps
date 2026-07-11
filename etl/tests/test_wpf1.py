"""Инварианты WP-F1 (приёмка из TASK_SPEC): возрастно-половые структуры
переписей 2009/2019, текущие структуры, миграционная матрица, реестр."""
import csv
import json
from pathlib import Path

import pytest

from etl.common import ROOT

CURATED = ROOT / "data" / "curated"
OBLS = ["BY-BR", "BY-VI", "BY-HO", "BY-HR", "BY-MI", "BY-MA"]
AGE_GROUPS_18 = 18  # 0-4 ... 85 и старше


@pytest.fixture(scope="session", params=[2009, 2019])
def age_census(request):
    year = request.param
    rows = list(csv.DictReader(open(CURATED / f"age{year}.csv")))
    return year, rows


@pytest.fixture(scope="session")
def known():
    return json.loads((ROOT / "web/public/data/data.json").read_text())["territories"]


def test_census_age_sums_match_official(age_census, known):
    """Сумма возрастных групп по территории = официальный итог переписи
    (допуск по спеке 0,1%; фактически расхождение нулевое)."""
    year, rows = age_census
    totals = {}
    for r in rows:
        totals[r["territory_id"]] = totals.get(r["territory_id"], 0) + int(r["pop"])
    for obl in OBLS + ["BY-HM"]:
        official = known[obl]["pop"][str(year)][0]
        assert abs(totals[obl] - official) / official <= 0.001, (year, obl)
        assert totals[obl] == official  # фактически точное совпадение
    country = sum(totals[o] for o in OBLS + ["BY-HM"])
    assert country == known["BY"]["pop"][str(year)][0]


def test_census_age_children_sum_to_oblast(age_census):
    """Районы + города обл. подчинения = область, до человека."""
    year, rows = age_census
    obl_totals, child_totals = {}, {}
    for r in rows:
        t, v = r["territory_id"], int(r["pop"])
        if t.startswith(("r-", "c-")):
            child_totals[r["oblast"]] = child_totals.get(r["oblast"], 0) + v
        elif t in OBLS:
            obl_totals[t] = obl_totals.get(t, 0) + v
    for obl in OBLS:
        assert obl_totals[obl] == child_totals[obl], (year, obl)


def test_census_age_coverage(age_census):
    """118 районов, все 18 групп, оба пола, оба типа местности."""
    year, rows = age_census
    raions = {r["territory_id"] for r in rows if r["territory_id"].startswith("r-")}
    assert len(raions) == 118, (year, len(raions))
    ages = {r["age_group"] for r in rows}
    assert len(ages) == AGE_GROUPS_18, (year, sorted(ages))
    assert {r["sex"] for r in rows} == {"m", "f"}
    assert {r["locality"] for r in rows} == {"urban", "rural"}


def test_age_current_additivity():
    rows = list(csv.DictReader(open(CURATED / "age_current.csv")))
    assert rows, "age_current.csv пуст"
    for terr in ["BY", "BY-MI", "BY-HM"]:
        for year in ["2019", "2024", "2026"]:
            def s(sex, loc):
                return sum(int(r["pop"]) for r in rows
                           if r["territory_id"] == terr and r["year"] == year
                           and r["sex"] == sex and r["locality"] == loc)
            assert s("m", "total") + s("f", "total") == s("t", "total"), (terr, year)
            assert s("t", "urban") + s("t", "rural") == s("t", "total"), (terr, year)
    # известный итог: страна на 01.01.2026 - 9 056 080 (оценка Белстата)
    total_2026 = sum(int(r["pop"]) for r in rows
                     if r["territory_id"] == "BY" and r["year"] == "2026"
                     and r["sex"] == "t" and r["locality"] == "total")
    assert total_2026 == 9_056_080


def test_migration_matrix_sane():
    rows = list(csv.DictReader(open(CURATED / "migration_internal.csv")))
    assert rows
    for year in ("2009", "2019"):
        yr = [r for r in rows if r["year"] == year]
        origins = {r["origin_oblast"] for r in yr}
        dests = {r["dest_oblast"] for r in yr}
        assert origins == dests == set(OBLS + ["BY-HM"]), year
        # приток в Минск больше оттока из Минска (центростремительность)
        to_minsk = sum(int(r["migrants"]) for r in yr
                       if r["dest_oblast"] == "BY-HM" and r["origin_oblast"] != "BY-HM")
        from_minsk = sum(int(r["migrants"]) for r in yr
                         if r["origin_oblast"] == "BY-HM" and r["dest_oblast"] != "BY-HM")
        assert to_minsk > from_minsk, year


def test_wpp_controls():
    rows = list(csv.DictReader(open(ROOT / "data/raw/wpp2024/blr_total_all_variants.csv")))
    med = {r["Time"]: float(r["PopTotal"]) for r in rows if r["Variant"] == "Medium"}
    assert abs(med["2024"] - 9056.696) < 0.01
    assert abs(med["2050"] - 7449.0) < 200      # медиана WPP ~7,45 млн (калибровка WP-F4)
    low = {r["Time"]: float(r["PopTotal"]) for r in rows if r["Variant"] == "Low"}
    high = {r["Time"]: float(r["PopTotal"]) for r in rows if r["Variant"] == "High"}
    assert low["2100"] < med["2100"] < high["2100"]


def test_wcde_controls():
    rows = list(csv.DictReader(open(ROOT / "data/raw/wcde/blr_pop_total_ssp123.csv")))
    by = {(r["scenario"], r["year"]): float(r["pop_thousands"]) for r in rows}
    assert abs(by[("SSP2", "2020")] - 9661.0) < 1
    assert by[("SSP1", "2100")] < by[("SSP2", "2100")] < by[("SSP3", "2100")]


def test_fertility_mortality_extracts():
    fert = list(csv.DictReader(open(CURATED / "fertility.csv")))
    years = {int(r["year"]) for r in fert}
    assert min(years) <= 1964 and max(years) >= 2018
    mort = list(csv.DictReader(open(CURATED / "mortality.csv")))
    years_m = {int(r["year"]) for r in mort}
    assert min(years_m) <= 1959 and max(years_m) >= 2018
    # ОПЖ при рождении 2018 в разумных пределах
    e0 = [float(r["life_expectancy"]) for r in mort
          if r["year"] == "2018" and r["age"] == "0" and r["sex"] == "total"
          and "life_expectancy" in r]
    if e0:
        assert 73 < e0[0] < 76


def test_registry_covers_files():
    """Каждый файл из реестра существует и sha совпадает (дата+лицензия есть)."""
    import hashlib
    rows = list(csv.DictReader(open(ROOT / "data/raw/registry_wpf1.csv")))
    assert len(rows) >= 15
    for r in rows:
        p = ROOT / r["file"]
        assert p.is_file(), r["file"]
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        assert actual == r["sha256"], r["file"]
        assert r["accessed"] and r["license"] and r["source_url"]
