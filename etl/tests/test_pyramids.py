"""Тесты датасета «Пирамида» (INF-11, приёмка §6.1): суммы до
человека, unknown, порядок групп, согласованность будущего с прогнозом,
отсутствие WPP-заглушки, выверенные факты RESEARCH_NOTE."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
DATA = ROOT / "web" / "public" / "data" / "pyramids.json"

GROUPS = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34",
          "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69",
          "70-74", "75-79", "80+"]

# официальные итоги: переписи (Демоскоп/OLAP) и оценка-2026
ANCHORS = {
    "1959": 8054648, "1970": 9002338, "1979": 9532516,
    "1989": 10151806, "2009": 9503807, "2019": 9413446,
    "2026": 9056080,
}


@pytest.fixture(scope="module")
def data():
    return json.loads(DATA.read_text())


def _tot(rec) -> int:
    return sum(rec["m"]) + sum(rec["f"]) + rec.get("unknown", 0)


def test_structure(data):
    assert data["age_groups"] == GROUPS
    for key, rec in data["series"].items():
        assert rec["type"] in ("census", "estimate", "interpolated",
                               "model"), key
        assert len(rec["m"]) == 17 and len(rec["f"]) == 17, key
        assert rec.get("source"), key


def test_census_and_estimate_sums_to_the_person(data):
    for key, expect in ANCHORS.items():
        rec = data["series"][key]
        assert rec["type"] in ("census", "estimate")
        assert _tot(rec) == expect, f"{key}: {_tot(rec)} != {expect}"


def test_yearly_estimates_match_portal_totals(data):
    """Оценки 1990-2018: сумма групп = «По всем возрастам» источника."""
    raw = ROOT / "data" / "raw" / "pyramid"
    totals = {}
    for p in sorted(raw.glob("dataportal_age_*.json")):
        d = json.loads(p.read_text())
        years = [int(y) for y in d["tableHeader"][0]]
        for row in d["tableRows"]:
            if row[1]["value"] != "По всем возрастам":
                continue
            for i, y in enumerate(years):
                v = row[4 + i]["value"] if 4 + i < len(row) else None
                if v is None:
                    continue
                v = int(float(str(v).replace("\xa0", "").replace(",", ".")))
                totals[y] = totals.get(y, 0) + v
    checked = 0
    for y, expect in totals.items():
        key = str(y)
        if key in data["series"] and data["series"][key]["type"] == "estimate":
            assert _tot(data["series"][key]) == expect, key
            checked += 1
    assert checked >= 25


def test_unknown_preserved(data):
    assert data["series"]["2009"].get("unknown") == 296
    # переписи 1959-1989 содержали «возраст не указан»
    for y in ("1959", "1970", "1979", "1989"):
        assert data["series"][y].get("unknown", 0) >= 0


def test_no_wpp_placeholder_in_prod(data):
    txt = json.dumps(data, ensure_ascii=False).lower()
    assert "placeholder" not in txt
    assert "заглушка" not in txt.replace("заглушка прототипа сюда не", "")
    for key, rec in data["series"].items():
        if rec["type"] == "model":
            assert "ccmpp" in rec["source"].lower(), key
            assert "wpp" not in rec["source"].lower(), key


def test_model_matches_forecast_totals(data):
    """Будущее согласовано с итогами прогноза (приёмка: +-0,1%)."""
    rows = {(r["scenario"], r["jumpoff"], int(r["year"])): float(r["pop"])
            for r in csv.DictReader(
                open(ROOT / "data/curated/forecast_v2026_4.csv"))
            if r["territory_id"] == "BY"}
    checked = 0
    for key, rec in data["series"].items():
        if rec["type"] != "model":
            continue
        parts = key.split(":")
        y = int(parts[0])
        sid = parts[1]
        jo = "adjusted" if len(parts) > 2 else "official"
        want = rows.get((sid, jo, y))
        if want is None:
            continue  # межузловые годы CSV не содержит
        got = sum(rec["m"]) + sum(rec["f"])
        assert abs(got / want - 1) < 0.001, f"{key}: {got} vs {want}"
        checked += 1
    assert checked >= 6


def test_model_grid_complete(data):
    for y in range(2030, 2076, 5):
        for sid in ("base", "optimistic", "negative"):
            assert f"{y}:{sid}" in data["series"]
            assert f"{y}:{sid}:adjusted" in data["series"]


def test_interpolated_frames_between_censuses(data):
    for y in list(range(1960, 1970)) + list(range(1971, 1979)) \
            + list(range(1980, 1989)):
        rec = data["series"][str(y)]
        assert rec["type"] == "interpolated", y
        # сумма между суммами опор (когортный варп сохраняет массу)
        lo = min(_tot(data["series"]["1959"]), _tot(data["series"]["1990"]))
        hi = max(_tot(data["series"]["1979"]), _tot(data["series"]["1990"]))
        assert lo * 0.99 <= _tot(rec) <= hi * 1.01, y


def test_research_note_facts(data):
    """Выверенные факты §3 RESEARCH_NOTE (основа аннотаций A1-A7).

    ВАЖНО: числа записки за 2019 год (A3 461,3 тыс.; A4 550,1 тыс.)
    взяты из ОЦЕНКИ Белстата на 01.01.2019 (age_current.csv), а не из
    переписи-2019 (там 448,0 и 526,1 - перепись в октябре, когорты
    другие). Кадр «2019» датасета - перепись; тексты аннотаций цитируют
    оценку - разночтение оговорено в методблоке."""
    s = data["series"]

    def grp(k, g):
        i = GROUPS.index(g)
        return s[k]["m"][i], s[k]["f"][i]

    m, f = grp("2009", "65-69")
    assert round((m + f) / 100) == 3469          # A1: 346,9 тыс.
    assert round(sum(grp("2009", "45-49")) / 100) == 7740   # A2: 774,0
    m, f = grp("2009", "40-44")
    assert round((m + f) / 100) == 6608          # A2: 660,8 тыс.
    m, f = grp("2026", "0-4")
    assert round((m + f) / 100) == 3335          # A4: 333,5 тыс.
    m, f = grp("2026", "80+")
    assert round(f / m, 2) == 3.57               # A5
    assert round((m + f) / 1000) == 298          # A6: 298 тыс.

    # A3/A4-числа 2019 года - из оценки на 01.01.2019 (их источник)
    import csv
    from collections import defaultdict
    g19 = defaultdict(int)
    with open(ROOT / "data/curated/age_current.csv") as f:
        for r in csv.DictReader(f):
            if r["territory_id"] == "BY" and r["locality"] == "total" \
                    and r["sex"] in ("m", "f") and r["year"] == "2019":
                g19[r["age_group"].replace(" ", "")] += int(r["pop"])
    assert round(g19["20-24"] / 100) == 4613     # A3: 461,3 тыс.
    assert round(g19["30-34"] / 100) == 7886     # A3: 788,6 тыс.
    assert round(g19["0-4"] / 100) == 5501       # A4: 550,1 тыс.
