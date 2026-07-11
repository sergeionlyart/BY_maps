"""WP-F5, бэктест: обучение на данных <=2009 -> прогноз 2019 -> сравнение
с переписью-2019 (уровни: страна и области - состав MVP этапа 3).

Параметры «как их видели в 2009» - уровни и ЛИНЕЙНЫЕ ТРЕНДЫ, обученные
на 1999-2009 (стандартное правило: продолжение наблюдаемого тренда):
- стартовая структура: перепись-2009 (age2009.csv);
- ASFR областей 2009 года, масштабируемые трендом национального СКР
  1999->2009 (ежегодник, табл. 4.10);
- смертность: HMD mx-2009, масштабируемая к e0 с трендом 1999->2009
  (по полу);
- миграция: внутренний профиль матрицы F602-2009 с объёмом 60 тыс.
  перемещений/год; международное сальдо +10 тыс./год (официальные сальдо
  2005-2009).

Бенчмарк - наивная линейная экстраполяция: P2019 = P2009 * (P2009/P1999).
Гейты (TASK_SPEC WP-F5): национальный итог +-2% факта; MAPE областей
не хуже наивного бенчмарка.

Запуск: python -m etl.forecast.backtest -> docs/notes/backtest_results.json
"""
from __future__ import annotations

import json

import csv

from ..common import ROOT
from . import TERRITORIES, FERTILE, STEP
from .data import census_structure, mortality_mx, asfr_profile, CURATED
from .lifetable import survival_5y, e0 as calc_e0, scale_to_e0
from .ccmpp import project_step, total
from .migration import internal_net_per_year, _age_profile, INTL_KEYS, _SEX_SPLIT
from . import AGE_GROUPS

INTL_NET_2000S = 10_000  # чел/год, официальное сальдо РБ 2005-2009


def _e0_observed(year: int) -> dict[str, float]:
    """e0 из HMD-таблиц (life_expectancy при age=0)."""
    out = {}
    col = {"male": "m", "female": "f"}
    for r in csv.DictReader(open(CURATED / "mortality.csv")):
        if (int(r["year"]) == year and r["sex"] in col and r["age"] == "0"
                and r["type"] == "period"):
            out[col[r["sex"]]] = float(r["life_expectancy"])
    return out


def _tfr_national(year: int) -> float:
    """Национальный СКР как средневзвешенный областной (веса - женщины 15-49
    переписи-2009); для тренда важна только относительная динамика."""
    prof = asfr_profile(year)
    c09 = census_structure(2009)
    num = den = 0.0
    for t in TERRITORIES:
        w = sum(c09[t]["f"][g] for g in FERTILE)
        num += prof["tfr"][t] * w
        den += w
    return num / den


def run_backtest() -> dict:
    pops = {t: {s: dict(v) for s, v in census_structure(2009)[t].items()}
            for t in TERRITORIES}
    mx09 = mortality_mx(2009)
    prof09 = asfr_profile(2009)
    internal = internal_net_per_year(2009)
    age_prof = _age_profile(2009)

    # линейные тренды 1999->2009 (обучение только на прошлом)
    e0_99, e0_09 = _e0_observed(1999), _e0_observed(2009)
    e0_slope = {s: (e0_09[s] - e0_99[s]) / 10 for s in ("m", "f")}
    tfr_99, tfr_09 = _tfr_national(1999), _tfr_national(2009)
    tfr_slope = (tfr_09 - tfr_99) / 10

    for step_i in range(2):  # 2009 -> 2014 -> 2019
        years_ahead = step_i * STEP + STEP / 2  # середина шага
        surv = {}
        for s in ("m", "f"):
            target = e0_09[s] + e0_slope[s] * years_ahead
            surv[s] = survival_5y(scale_to_e0(mx09[s], target))
        tfr_scale = (tfr_09 + tfr_slope * years_ahead) / tfr_09
        for t in TERRITORIES:
            asfr = {g: prof09["asfr"][t].get(g, 0.0) * tfr_scale for g in FERTILE}
            net = {"m": dict.fromkeys(AGE_GROUPS, 0.0),
                   "f": dict.fromkeys(AGE_GROUPS, 0.0)}
            for a in AGE_GROUPS:
                net_year = internal[t][a] + INTL_NET_2000S * INTL_KEYS[t] * age_prof[a]
                for s in ("m", "f"):
                    net[s][a] += net_year * STEP * _SEX_SPLIT
            pops[t], _ = project_step(pops[t], surv, asfr, net)

    predicted = {t: total(pops[t]) for t in TERRITORIES}
    predicted["BY"] = sum(predicted.values())
    return predicted


def evaluate() -> dict:
    actual19 = {t: total(census_structure(2019)[t]) for t in TERRITORIES}
    actual19["BY"] = sum(actual19.values())
    pred = run_backtest()

    # наивный бенчмарк: P2019 = P2009 * (P2009 / P1999); итоги переписей -
    # в data/curated/oblast_totals.csv (самодостаточно для пакета)
    totals = {}
    for r in csv.DictReader(open(CURATED / "oblast_totals.csv")):
        totals[(r["territory_id"], r["year"])] = int(r["pop"])
    naive = {}
    for t in TERRITORIES:
        p99 = totals[(t, "1999")]
        p09 = totals[(t, "2009")]
        naive[t] = p09 * (p09 / p99)
    naive["BY"] = sum(naive.values())

    def ape(a: float, b: float) -> float:
        return abs(a - b) / b * 100

    report = {
        "national": {
            "actual": actual19["BY"], "model": round(pred["BY"]),
            "naive": round(naive["BY"]),
            "model_err_pct": round((pred["BY"] - actual19["BY"]) / actual19["BY"] * 100, 2),
            "naive_err_pct": round((naive["BY"] - actual19["BY"]) / actual19["BY"] * 100, 2),
        },
        "oblasts": {},
    }
    m_apes, n_apes = [], []
    for t in TERRITORIES:
        m, n = ape(pred[t], actual19[t]), ape(naive[t], actual19[t])
        m_apes.append(m)
        n_apes.append(n)
        report["oblasts"][t] = {"actual": actual19[t], "model": round(pred[t]),
                                "naive": round(naive[t]),
                                "model_ape": round(m, 2), "naive_ape": round(n, 2)}
    report["mape_model"] = round(sum(m_apes) / len(m_apes), 2)
    report["mape_naive"] = round(sum(n_apes) / len(n_apes), 2)
    report["gates"] = {
        "national_within_2pct": abs(report["national"]["model_err_pct"]) <= 2.0,
        "beats_naive_mape": report["mape_model"] <= report["mape_naive"],
    }
    return report


def main() -> None:
    rep = evaluate()
    dest = ROOT / "docs" / "notes" / "backtest_results.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    n = rep["national"]
    print(f"страна: факт {n['actual']:,} | модель {n['model']:,} ({n['model_err_pct']:+}%) "
          f"| наивная {n['naive']:,} ({n['naive_err_pct']:+}%)")
    print(f"MAPE областей: модель {rep['mape_model']}% vs наивная {rep['mape_naive']}%")
    print(f"гейты: {rep['gates']}")


if __name__ == "__main__":
    main()
