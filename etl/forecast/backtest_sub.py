"""Бэктесты уровней 2-3 (этап 5, гейты из validation.md §4 п.3).

Районы (Гамильтон-Перри): CCR обучены на переписях 2009-2019; прогноз
итогов районов и городов обл. подчинения на 2026 (out-of-sample: 7 лет
после обучающего окна) против официальных оценок Белстата на 01.01.2026.
Обе модели - CCR и наивная (линейная экстраполяция итога 2009-2019) -
нормируются к фактическому областному итогу 2026: гейт проверяет
РАСПРЕДЕЛЕНИЕ населения между районами, а не областной уровень (он
приходит из уровня 1 и провалидирован бэктестом этапа 3).
Гейт: MAPE(CCR) < MAPE(наивной).

Города (доля в районе): логистический тренд обучен на ряде до 2009
включительно; прогноз доли на 2019 x фактический район-2019 против
переписи-2019. Наивная: доля заморожена на уровне 2009.
Гейт: MAPE(логистической) <= MAPE(наивной).

Запуск: python -m etl.forecast.backtest_sub -> docs/notes/backtest_sub.json
"""
from __future__ import annotations

import json

from ..common import ROOT, OUT
from .data import jumpoff_2026
from . import sub

NOTES = ROOT / "docs" / "notes"


def _ape(model: float, fact: float) -> float:
    return abs(model - fact) / fact * 100


def backtest_raions() -> dict:
    """CCR-прогноз 2019->2026 против официальных оценок, гейт по MAPE."""
    children = sub.project_children()
    official = sub.official_totals_2026()
    obl = sub.oblast_of()

    # мишень нормировки: фактические областные структуры на 01.01.2026
    jump = jumpoff_2026()
    obl_structs = {o: {2026: jump[o]} for o in jump if o != "BY-HM"}
    model = sub.reconcile(children, obl_structs, [2026])

    # наивная: линейная экстраполяция итога 2009-2019 на 2026 (те же периметры)
    p09 = sub.load_sub_structures(2009)
    p19 = sub.load_sub_structures(2019)
    naive_raw = {}
    for t in p19:
        t09 = sum(p09[t]["m"].values()) + sum(p09[t]["f"].values())
        t19 = sum(p19[t]["m"].values()) + sum(p19[t]["f"].values())
        naive_raw[t] = max(t19 + (t19 - t09) / 10 * 7, 0.0)
    # нормировка наивной к тем же областным итогам
    naive = {}
    for o in obl_structs:
        kids = [t for t in naive_raw if obl[t] == o]
        target = sum(jump[o][s][g] for s in ("m", "f") for g in jump[o][s])
        ssum = sum(naive_raw[t] for t in kids)
        for t in kids:
            naive[t] = naive_raw[t] * target / ssum

    rows = []
    for t in sorted(model):
        fact = official[t]
        rows.append({
            "territory_id": t,
            "fact_2026": round(fact),
            "model_2026": round(model[t][2026]),
            "naive_2026": round(naive[t]),
            "ape_model": round(_ape(model[t][2026], fact), 2),
            "ape_naive": round(_ape(naive[t], fact), 2),
        })
    mape_m = sum(r["ape_model"] for r in rows) / len(rows)
    mape_n = sum(r["ape_naive"] for r in rows) / len(rows)
    med = sorted(r["ape_model"] for r in rows)[len(rows) // 2]
    return {
        "n": len(rows),
        "mape_model": round(mape_m, 2),
        "mape_naive": round(mape_n, 2),
        "median_ape_model": round(med, 2),
        "gate_beats_naive": mape_m < mape_n,
        "rows": rows,
    }


def backtest_cities() -> dict:
    """Логистическая доля (обучение <=2009) -> город-2019 против переписи."""
    data = json.loads((OUT / "data.json").read_text())["territories"]
    cmap = sub.city_raion_map()
    sub_ids = set(sub.load_sub_structures(2019))

    rows = []
    for c, r in sorted(cmap.items()):
        if c in sub_ids:
            continue
        cpop, rpop = data[c]["pop"], data[r]["pop"]
        if "2019" not in cpop or "2019" not in rpop:
            continue
        fit = sub.fit_city_share(cpop, rpop, year_to=2009)
        if not fit or "2009" not in cpop or "2009" not in rpop:
            continue
        fact = cpop["2019"][0]
        raion_fact = rpop["2019"][0]
        model = sub.share_at(fit, 2019) * raion_fact
        share09 = cpop["2009"][0] / rpop["2009"][0]
        naive = share09 * raion_fact
        rows.append({
            "city_id": c,
            "fact_2019": fact,
            "model_2019": round(model),
            "naive_2019": round(naive),
            "ape_model": round(_ape(model, fact), 2),
            "ape_naive": round(_ape(naive, fact), 2),
        })
    mape_m = sum(r["ape_model"] for r in rows) / len(rows)
    mape_n = sum(r["ape_naive"] for r in rows) / len(rows)
    med = sorted(r["ape_model"] for r in rows)[len(rows) // 2]
    return {
        "n": len(rows),
        "mape_model": round(mape_m, 2),
        "mape_naive": round(mape_n, 2),
        "median_ape_model": round(med, 2),
        "gate_not_worse_than_naive": mape_m <= mape_n,
        "rows": rows,
    }


def main() -> None:
    raions = backtest_raions()
    cities = backtest_cities()
    NOTES.mkdir(parents=True, exist_ok=True)
    (NOTES / "backtest_sub.json").write_text(json.dumps(
        {"raions_2026": raions, "cities_2019": cities},
        ensure_ascii=False, indent=1))
    print(f"районы (2019->2026, {raions['n']} терр.): "
          f"MAPE модели {raions['mape_model']}% против наивной "
          f"{raions['mape_naive']}% (медиана {raions['median_ape_model']}%) "
          f"-> гейт {'OK' if raions['gate_beats_naive'] else 'FAIL'}")
    print(f"города (доля <=2009 -> 2019, {cities['n']} городов): "
          f"MAPE модели {cities['mape_model']}% против наивной "
          f"{cities['mape_naive']}% (медиана {cities['median_ape_model']}%) "
          f"-> гейт {'OK' if cities['gate_not_worse_than_naive'] else 'FAIL'}")


if __name__ == "__main__":
    main()
