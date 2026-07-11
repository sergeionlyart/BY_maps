"""Тесты INF-07 chernobyl. Приёмка из TASK_SPEC: классификация от официальных
НПА с указанием редакций; сравнение с демографически схожими контролями."""
import csv
import json
import math

import pytest

from etl.common import ROOT

CURATED = ROOT / "data" / "curated"


@pytest.fixture(scope="session")
def cher():
    return json.loads((ROOT / "web/public/data/chernobyl.json").read_text())


@pytest.fixture(scope="session")
def terrs():
    return json.loads((ROOT / "web/public/data/data.json").read_text())["territories"]


@pytest.fixture(scope="session")
def zones_csv():
    return list(csv.DictReader(open(CURATED / "chernobyl_zones.csv")))


def test_classification(cher, terrs):
    """3 района зоны эвакуации (ПГРЭЗ) + 9 сильно загрязнённых."""
    k1 = [p for p in cher["pairs"] if p["klass"] == 1]
    k2 = [p for p in cher["pairs"] if p["klass"] == 2]
    assert len(k1) == 3 and len(k2) == 9
    assert {p["ru"] for p in k1} == {"Брагинский район", "Хойникский район",
                                     "Наровлянский район"}
    for p in cher["pairs"]:
        assert terrs[p["id"]]["level"] == "raion"
        assert p["closedHa"] and p["closedHa"] > 4000  # у всех есть закрытые территории


def test_np_totals_match_official(zones_csv):
    """Суммы НП по зонам = официальные итоги перечней: 2022 (2021 г.) и 2193 (2016 г.)."""
    s21 = sum(int(r["np_prk_2021"]) + int(r["np_po_2021"]) + int(r["np_posl_2021"])
              for r in zones_csv)
    s16 = sum(int(r["np_prk_2016"]) + int(r["np_po_2016"]) + int(r["np_posl_2016"])
              for r in zones_csv)
    assert s21 == 2022, s21
    assert s16 == 2193, s16


def test_controls_clean_and_matched(cher, terrs, zones_csv):
    """Контроль: вне перечней зон, уникален, сопоставим по населению-1979."""
    zone_ids = {r["territory_id"] for r in zones_csv}
    controls = [p["control"] for p in cher["pairs"]]
    assert len(set(controls)) == len(controls)
    for p in cher["pairs"]:
        assert p["control"] not in zone_ids, p["controlRu"]
        assert p["control"] not in {"r-minski", "r-dziarzhynski", "r-smaliavicki"}
        ratio = p["controlPop1979"] / p["pop1979"]
        assert abs(math.log(ratio)) < 0.8, (p["ru"], p["controlRu"], ratio)


def test_evacuation_districts_fell_behind_controls(cher, terrs):
    """Класс 1: каждый район зоны эвакуации сократился к 2019 г. сильнее контроля;
    класс 2 - большинство (изучаемый эффект, не тавтология: контроли выбраны
    без оглядки на динамику после 1979 г.)."""
    def idx2019(t, base):
        return terrs[t]["pop"]["2019"][0] / base * 100

    worse = {1: 0, 2: 0}
    for p in cher["pairs"]:
        a = idx2019(p["id"], p["pop1979"])
        c = idx2019(p["control"], p["controlPop1979"])
        if a < c:
            worse[p["klass"]] += 1
    assert worse[1] == 3, worse
    assert worse[2] >= 6, worse


def test_events_annotated(cher):
    years = [e["year"] for e in cher["events"]]
    assert years == sorted(years)
    assert years[0] == 1986 and years[-1] <= 2026
    assert all(e["label"] for e in cher["events"])
    assert "75" in cher["npa"]["current"] and "2021" in cher["npa"]["current"]
    assert "№ 9" in cher["npa"]["y2016"] or "9" in cher["npa"]["y2016"]


def test_csv_consistent_with_json(cher, zones_csv):
    by_id = {r["territory_id"]: r for r in zones_csv}
    for p in cher["pairs"]:
        row = by_id[p["id"]]
        assert int(row["class"]) == p["klass"]
        assert float(row["closed_area_ha"]) == p["closedHa"]
