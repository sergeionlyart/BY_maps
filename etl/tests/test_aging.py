"""Тесты INF-02 aging. Приёмка-специфика из TASK_SPEC: пирамиды сходятся
с переписными итогами; индикаторы в разумных диапазонах."""
import csv
import json

import pytest

from etl.common import ROOT

CURATED = ROOT / "data" / "curated"


@pytest.fixture(scope="session")
def aging():
    return json.loads((ROOT / "web/public/data/aging.json").read_text())


@pytest.fixture(scope="session")
def known():
    return json.loads((ROOT / "web/public/data/data.json").read_text())["territories"]


def test_pyramids_sum_to_census_totals(aging, known):
    """Сумма пирамиды = официальный итог переписи. Допуск - только
    поэлементное округление 34 ячеек (максимум 17 чел.); записи «возраст
    не определен» (296 чел. по стране в 2009) распределены пропорционально."""
    for t in ["BY-BR", "BY-VI", "BY-HO", "BY-HR", "BY-MI", "BY-MA", "BY-HM"]:
        rec = aging["territories"][t]
        for year, key in ((2009, "pyramid2009"), (2019, "pyramid2019")):
            s = sum(rec[key]["m"]) + sum(rec[key]["f"])
            official = known[t]["pop"][str(year)][0]
            assert abs(s - official) <= 17, (t, year, s, official)


def test_raion_pyramids_cover_all(aging):
    raions = [t for t in aging["territories"] if t.startswith("r-")]
    assert len(raions) == 118
    for t in raions:
        rec = aging["territories"][t]
        assert rec["pyramid2019"] and len(rec["pyramid2019"]["m"]) == 17
        assert rec["median2019"] and 30 < rec["median2019"] < 60, t
        assert 5 < rec["share65_2019"] < 35, t


def test_aging_direction_2009_2019(aging):
    """Старение: медианный возраст вырос в подавляющем большинстве районов."""
    ups = downs = 0
    for t, rec in aging["territories"].items():
        if t.startswith("r-") and rec["median2009"]:
            if rec["median2019"] > rec["median2009"]:
                ups += 1
            else:
                downs += 1
    assert ups > 100, (ups, downs)


def test_counterfactual_sane(aging):
    """Контрфакт «нулевая миграция»: у большинства районов естественная
    убыль; годы до порога кратны шагу и в горизонте."""
    rs = {t: v for t, v in aging["territories"].items() if t.startswith("r-")}
    negative = sum(1 for v in rs.values() if (v["naturalCagr"] or 0) < 0)
    assert negative >= 110, negative
    for t, v in rs.items():
        if v["yearsTo30"] is not None:
            assert v["yearsTo30"] % 5 == 0 and 0 <= v["yearsTo30"] <= 60, t
    # Минск существенно моложе периферии
    assert aging["territories"]["BY-HM"]["median2019"] < 40


def test_indicators_csv_consistent(aging):
    rows = list(csv.DictReader(open(CURATED / "aging_indicators.csv")))
    assert len(rows) == len(aging["territories"])
    by_id = {r["territory_id"]: r for r in rows}
    for t, rec in aging["territories"].items():
        assert float(by_id[t]["median2019"]) == rec["median2019"], t
