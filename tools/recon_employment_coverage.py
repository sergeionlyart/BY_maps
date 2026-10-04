#!/usr/bin/env python3
"""Разведка охвата статистики занятости (шаг ноль волны INF-17 — INF-19).

Вопрос разведки, заданный в handoff/09_next_research/RESEARCH_PROPOSALS_INF17-19.md
(INF-18, метод, шаг 1): что именно считает индикатор занятости дата-портала
Белстата 10102000017 «Численность занятого населения в среднем за период» —
занятых ПО МЕСТУ ЖИТЕЛЬСТВА или рабочие места ПО МЕСТУ РАБОТЫ, и сопоставим ли
охват между районами и по годам. От ответа зависит, вычислим ли остаточный
`commute_deficit` из этого индикатора (INF-18) и можно ли строить на нём
`labor_input` (INF-19).

Данные — только завендоренные: data/raw/wages/empl_person_10102000017_*.json,
data/curated/age2019.csv, web/public/data/data.json. Сеть не требуется.

Запуск: python3 tools/recon_employment_coverage.py
Выход:  docs/notes/employment_coverage_recon.json (+ таблицы в stdout)
"""
from __future__ import annotations

import csv
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from etl.census_age import RAION_RU2ID, _e          # noqa: E402
from etl.wages import CITY_RU2ID, OBL_RU2ID          # noqa: E402

RAW = ROOT / "data" / "raw" / "wages"
SPANS = ("empl_person_10102000017_2010-2019.json",
         "empl_person_10102000017_2020-2026.json")
YEARS = range(2010, 2025)        # районный ряд обрывается на 2024
# трудоспособный возраст для нормировки: 15-64 (сопоставимо с WPP/ОЭСР)
WORKING_AGE = {"15-19", "20-24", "25-29", "30-34", "35-39",
               "40-44", "45-49", "50-54", "55-59", "60-64"}
BREAK_THRESHOLD = 0.15           # скачок год-к-году, подозрительный на смену методологии


def _num(s: str | None) -> float | None:
    if not s:
        return None
    s = s.replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def load_employment() -> dict[str, dict[int, float]]:
    """territory_id -> {год: занятые, человек}."""
    raw: dict[str, dict[int, float]] = {}
    for fn in SPANS:
        d = json.loads((RAW / fn).read_text())
        years = [int(y) for y in d["tableHeader"][0]]
        for row in d["tableRows"]:
            name = row[0]["value"].strip()
            vals = {y: _num(c["value"]) for y, c in zip(years, row[1:])}
            raw.setdefault(name, {}).update({y: v for y, v in vals.items() if v is not None})
    out, unmapped = {}, []
    for name, series in raw.items():
        tid = (RAION_RU2ID.get(_e(name)) or CITY_RU2ID.get(name)
               or OBL_RU2ID.get(name))
        if tid is None:
            unmapped.append(name)
        else:
            out[tid] = series
    if unmapped:
        raise SystemExit(f"не сопоставлены названия территорий: {unmapped}")
    return out


def load_working_age() -> dict[str, int]:
    """territory_id -> население 15-64, перепись 2019 (переписной периметр:
    районы БЕЗ городов областного подчинения, города отдельными строками)."""
    wa: dict[str, int] = {}
    with open(ROOT / "data" / "curated" / "age2019.csv") as f:
        for r in csv.DictReader(f):
            if r["age_group"] in WORKING_AGE:
                wa[r["territory_id"]] = wa.get(r["territory_id"], 0) + int(r["pop"])
    return wa


def main() -> None:
    E = load_employment()
    wa = load_working_age()
    T = json.loads((ROOT / "web" / "public" / "data" / "data.json").read_text())["territories"]
    name = lambda t: T[t]["ru"]                                  # noqa: E731

    raions = sorted(t for t in E if t.startswith("r-"))
    cities = sorted(t for t in E if t.startswith("c-"))
    report: dict = {
        "indicator": "10102000017",
        "indicator_name": "Численность занятого населения в среднем за период",
        "source": "dataportal.belstat.gov.by/osids-public-api (завендорено в data/raw/wages/)",
        "unit": "210 (человек)",
        "territories": {"total": len(E), "raions": len(raions), "cities_oblast_subordination": len(cities)},
        "years_with_data": [y for y in YEARS if any(E[t].get(y) for t in E)],
    }

    # ---- A. полнота и сопоставимость по годам -------------------------------
    gaps = {name(t): [y for y in YEARS if E[t].get(y) is None] for t in E}
    gaps = {k: v for k, v in gaps.items() if v}
    yoy, breaks = [], []
    years = list(YEARS)
    for y0, y1 in zip(years, years[1:]):
        ch = [E[t][y1] / E[t][y0] - 1 for t in E if E[t].get(y0) and E[t].get(y1)]
        yoy.append({"from": y0, "to": y1, "median_pct": round(st.median(ch) * 100, 2),
                    "min_pct": round(min(ch) * 100, 1), "max_pct": round(max(ch) * 100, 1)})
        breaks += [{"year": f"{y0}-{y1}", "territory": name(t),
                    "change_pct": round((E[t][y1] / E[t][y0] - 1) * 100, 1)}
                   for t in E if E[t].get(y0) and E[t].get(y1)
                   and abs(E[t][y1] / E[t][y0] - 1) > BREAK_THRESHOLD]
    report["completeness"] = {"territories_with_gaps": gaps,
                              "yoy_change": yoy,
                              "breaks_over_15pct": breaks}

    # ---- B. тест «место жительства или место работы» ------------------------
    # Место работы обязано давать районы-ввозники с отношением > 1 (рабочих мест
    # больше, чем трудоспособных жителей) и районы-спальни глубоко внизу.
    # Место жительства ограничено сверху трудоспособным населением.
    ratio = []
    for t in raions + cities:
        e, w = E[t].get(2019), wa.get(t)
        if e and w:
            ratio.append({"territory_id": t, "name": name(t), "employed_2019": e,
                          "working_age_2019": w, "ratio": round(e / w, 4)})
    ratio.sort(key=lambda r: r["ratio"])
    vals = [r["ratio"] for r in ratio]
    suburbs = ["r-minski", "r-dziarzhynski", "r-smalavicki", "r-lahojski", "r-puchavicki"]
    report["workplace_vs_residence_test"] = {
        "denominator": "население 15-64, перепись 2019",
        "n": len(ratio),
        "median": round(st.median(vals), 4),
        "min": {"name": ratio[0]["name"], "ratio": ratio[0]["ratio"]},
        "max": {"name": ratio[-1]["name"], "ratio": ratio[-1]["ratio"]},
        "count_above_1": sum(1 for v in vals if v > 1.0),
        "minsk_suburbs": [r for r in ratio if r["territory_id"] in suburbs],
        "minsk_suburb_ranks": {r["name"]: f"{i + 1}/{len(ratio)}"
                               for i, r in enumerate(ratio) if r["territory_id"] in suburbs},
        "lowest_10": ratio[:10],
        "highest_10": ratio[-10:],
    }

    # ---- C. периметр: кто не покрыт ----------------------------------------
    report["perimeter_gap"] = {
        "missing": "г. Минск (BY-HM)",
        "reason": "страна/области/Минск отчитываются в unit 211 (тыс. человек); "
                  "запрос одного unit молча отбрасывает другой уровень",
        "sum_128_territories": {str(y): round(sum(E[t][y] for t in E if E[t].get(y)))
                                for y in (2010, 2019, 2024)},
    }

    out = ROOT / "docs" / "notes" / "employment_coverage_recon.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    # ---- печать ------------------------------------------------------------
    print(f"территорий: {len(E)} ({len(raions)} районов + {len(cities)} городов обл. подчинения)")
    print(f"годы с данными: {report['years_with_data'][0]}-{report['years_with_data'][-1]}, "
          f"пропусков: {len(gaps)}, скачков >15%: {len(breaks)}")
    print(f"\nзанятые/трудоспособные 2019: медиана {st.median(vals):.3f}, "
          f"min {vals[0]:.3f} ({ratio[0]['name']}), max {vals[-1]:.3f} ({ratio[-1]['name']}), "
          f"выше 1.0: {report['workplace_vs_residence_test']['count_above_1']}")
    print("\nпригороды Минска (ранг по отношению, из %d):" % len(ratio))
    for r in report["workplace_vs_residence_test"]["minsk_suburbs"]:
        print(f"  {r['name'][:24]:24s} {r['ratio']:.3f}  "
              f"ранг {report['workplace_vs_residence_test']['minsk_suburb_ranks'][r['name']]}")
    print(f"\nзаписано: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
