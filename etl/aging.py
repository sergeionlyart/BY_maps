"""INF-02 `aging`: старение районов - индикаторы возрастной структуры и
контрфактная передвижка «при нулевой миграции».

Индикаторы по каждому району (и области/стране) из переписей 2009/2019:
- медианный возраст (линейная интерполяция внутри 5-летней группы);
- доля 65+; изменение доли 65+ 2009->2019;
- коэффициент демографической нагрузки (0-14 плюс 65+ к 15-64, на 100);
- «лет до порога 30% доли 65+» и «естественная динамика 2019->2039» -
  из контрфактной когортной передвижки БЕЗ миграции (смертность и
  рождаемость базового сценария прогноза v2026.2): показывает, где
  депопуляция самоподдерживается самой структурой.

Запуск: python -m etl.aging  ->  web/public/data/aging.json
                                 data/curated/aging_indicators.csv
"""
from __future__ import annotations

import csv
import json

from .common import ROOT, OUT
from .forecast import AGE_GROUPS, FERTILE, STEP
from .forecast.data import mortality_mx, asfr_profile
from .forecast.lifetable import survival_5y, scale_to_e0
from .forecast.ccmpp import project_step, total

CURATED = ROOT / "data" / "curated"
THRESHOLD_65 = 0.30
HORIZON_STEPS = 12  # 2019 + 60 лет
OLD_GROUPS = ["65-69", "70-74", "75-79", "80+"]
YOUNG_GROUPS = ["0-4", "5-9", "10-14"]

# фиксированные e0 контрфакта: уровень базовой траектории v2026.2 (WPP medium)
# на ~2035-2040 гг., применяется на всём горизонте (упрощение: без роста
# дожития; стресс e0 +-1 год - см. AGENT.md пакета)
E0_BASE = {"m": 72.0, "f": 81.5}


def load_structures(year: int) -> dict:
    """{terr: {sex: {age: pop}}} - все территории файла (районы+города+области).

    Записи «Возраст не определен» (перепись-2009: 296 чел. по стране, 0,003%;
    в 2019 - ни одной) распределяются пропорционально структуре территории и
    пола - стандартная практика; суммы пирамид сходятся с официальными
    итогами."""
    out: dict = {}
    undet: dict = {}
    for r in csv.DictReader(open(CURATED / f"age{year}.csv")):
        t, s = r["territory_id"], r["sex"]
        age = r["age_group"].replace("80 и старше", "80+")
        if age not in AGE_GROUPS:
            if "не определен" in age:
                undet[(t, s)] = undet.get((t, s), 0) + int(r["pop"])
            continue
        out.setdefault(t, {"m": dict.fromkeys(AGE_GROUPS, 0.0),
                           "f": dict.fromkeys(AGE_GROUPS, 0.0)})
        out[t][s][age] += int(r["pop"])
    for (t, s), extra in undet.items():
        base = sum(out[t][s].values())
        if base:
            for g in AGE_GROUPS:
                out[t][s][g] += extra * out[t][s][g] / base
    return out


def median_age(pop: dict) -> float:
    """Медианный возраст по 5-летним группам (интерполяция внутри группы)."""
    totals = [pop["m"][g] + pop["f"][g] for g in AGE_GROUPS]
    n = sum(totals)
    half = n / 2
    acc = 0.0
    for i, g in enumerate(AGE_GROUPS):
        if acc + totals[i] >= half:
            lower = i * STEP
            width = 20 if g == "80+" else STEP  # открытая группа условно до 100
            frac = (half - acc) / totals[i] if totals[i] else 0
            return round(lower + frac * width, 1)
        acc += totals[i]
    return 80.0


def share65(pop: dict) -> float:
    old = sum(pop["m"][g] + pop["f"][g] for g in OLD_GROUPS)
    return old / (total(pop) or 1)


def dependency_ratio(pop: dict) -> float:
    """(0-14 + 65+) / 15-64, на 100 человек трудоспособного возраста."""
    young = sum(pop["m"][g] + pop["f"][g] for g in YOUNG_GROUPS)
    old = sum(pop["m"][g] + pop["f"][g] for g in OLD_GROUPS)
    work = total(pop) - young - old
    return round((young + old) / (work or 1) * 100, 1)


def counterfactual(pop: dict, oblast: str) -> dict:
    """Передвижка 2019 -> +60 лет БЕЗ миграции (базовые смертность/ASFR).

    Возвращает {'years_to_30pct': лет от 2019 (None, если не пересекает),
                'natural_cagr_20y': средн. годовой темп 2019-2039, %}.
    """
    mx = mortality_mx(2018)
    surv = {s: survival_5y(scale_to_e0(mx[s], E0_BASE[s])) for s in ("m", "f")}
    prof = asfr_profile(2018)["asfr"].get(oblast) or {}
    asfr = {g: prof.get(g, 0.0) for g in FERTILE}

    cur = {s: dict(v) for s, v in pop.items()}
    start_total = total(cur)
    years_to = None
    pop20y = None
    if share65(cur) >= THRESHOLD_65:
        years_to = 0
    for step_i in range(1, HORIZON_STEPS + 1):
        cur, _ = project_step(cur, surv, asfr, None)
        if step_i == 4:  # 20 лет
            pop20y = total(cur)
        if years_to is None and share65(cur) >= THRESHOLD_65:
            years_to = step_i * STEP
    cagr = ((pop20y / start_total) ** (1 / 20) - 1) * 100 if start_total and pop20y else None
    return {"years_to_30pct": years_to,
            "natural_cagr_20y": round(cagr, 2) if cagr is not None else None}


def pyramid(pop: dict) -> dict:
    return {"m": [round(pop["m"][g]) for g in AGE_GROUPS],
            "f": [round(pop["f"][g]) for g in AGE_GROUPS]}


def main() -> None:
    s09, s19 = load_structures(2009), load_structures(2019)
    # область каждого района - из файла
    obl_of = {}
    for r in csv.DictReader(open(CURATED / "age2019.csv")):
        obl_of[r["territory_id"]] = r["oblast"]

    prof_keys = set(asfr_profile(2018)["asfr"])
    out = {}
    rows = []
    for t, pop19 in s19.items():
        pop09 = s09.get(t)
        obl = obl_of.get(t) or (t if t.startswith("BY-") else "BY-MI")
        # ASFR-профиль области района (у Минска - собственный, низкий)
        cf = counterfactual(pop19, obl if obl in prof_keys else "BY-MI")
        rec = {
            "median2009": median_age(pop09) if pop09 else None,
            "median2019": median_age(pop19),
            "share65_2009": round(share65(pop09) * 100, 1) if pop09 else None,
            "share65_2019": round(share65(pop19) * 100, 1),
            "depRatio2019": dependency_ratio(pop19),
            "yearsTo30": cf["years_to_30pct"],
            "naturalCagr": cf["natural_cagr_20y"],
            "pyramid2009": pyramid(pop09) if pop09 else None,
            "pyramid2019": pyramid(pop19),
        }
        out[t] = rec
        rows.append({"territory_id": t, "oblast": obl,
                     **{k: v for k, v in rec.items() if not k.startswith("pyramid")}})

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "aging.json").write_text(json.dumps({
        "version": "1.0.1",
        "ageGroups": AGE_GROUPS,
        "threshold": 30,
        "counterfactual": "нулевая миграция; смертность/рождаемость базового сценария v2026.2",
        "territories": out,
    }, ensure_ascii=False))

    rows.sort(key=lambda r: (r["oblast"], r["territory_id"]))
    with open(CURATED / "aging_indicators.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    raions = [t for t in out if t.startswith("r-")]
    worst = sorted(raions, key=lambda t: out[t]["share65_2019"], reverse=True)[:3]
    print(f"OK: aging.json ({len(out)} территорий, {len(raions)} районов)")
    print("  старейшие районы по доле 65+:",
          ", ".join(f"{t} {out[t]['share65_2019']}%" for t in worst))


if __name__ == "__main__":
    main()
