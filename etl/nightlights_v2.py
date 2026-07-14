"""INF-08 v2 «Беларусь из космоса, 1992-2075»: финальный набор (stdlib).

Собирает web/public/data/nightlights_v2.json из:
  - гармонизированного ряда 1992-2024 (etl/nightlights_harmonize):
    ретро 1992-2011 calDMSP в радианс-эквиваленте, 2012-2024 VNL;
  - населения зон (web/public/data/data.json, поле pop);
  - модельной светимости 2030-2075 (etl/nightlights_model):
    3 сценария x 2 стартовых ряда, узлы шага 5 лет.

Главная метрика, как в v1, - ДОЛИ зоны в национальном свете и населении
(гасят калибровочный дрейф и смену продуктов). Уровни ретро-сегмента -
радианс-эквивалент по калибровке стыка (маркируются «ретро, грубее»).
Будущий сегмент - МОДЕЛЬ (не измерение и не прогноз света): везде
отдаётся под ключом model, фронт обязан маркировать (ТЗ T-13).

v1-индекс расхождения div (окно тренда 2015-2019, шок 2022-2023)
пересчитывается тем же методом по ряду VNL - непрерывность с v1.

Запуск: python -m etl.nightlights_v2 -> web/public/data/nightlights_v2.json
"""
from __future__ import annotations

import json
import math

from .common import ROOT, OUT
from . import nightlights_harmonize as H
from . import nightlights_model as M
from .nightlights import TREND_YEARS, SHOCK_YEARS, _ratio

VERSION = "2.0.0"


def _pop(data, zid, year):
    v = data.get(zid)
    if not v:
        return None
    p = v["pop"].get(str(year))
    return float(p[0]) if p else None


def build() -> dict:
    assump = M.load_assumptions()
    dmsp, vnl = H.load_dmsp(), H.load_vnl()
    harm = H.harmonized(dmsp, vnl)
    series, source = harm["series"], harm["source"]
    zs = H.zones(dmsp)
    years_obs = sorted(source)
    data = json.loads((OUT / "data.json").read_text())["territories"]

    nat_light = {y: sum(series[z].get(y, 0.0) for z in zs)
                 for y in years_obs}
    pop_years = [y for y in years_obs
                 if _pop(data, "BY-HM", y) is not None]
    nat_pop = {y: sum(_pop(data, z, y) or 0.0 for z in zs)
               for y in pop_years}

    fut = M.future_light(assump)
    nodes = fut["nodes"]
    fpop = M.future_pop(assump)
    nat_fut = {j: {s: {t: sum(fut["light"][j][s][z][t] for z in zs)
                       for t in nodes}
                   for s in M.SCENARIOS} for j in M.JUMPOFFS}
    nat_fpop = {j: {s: {t: sum(fpop[j][s][z][t] for z in zs)
                        for t in nodes}
                    for s in M.SCENARIOS} for j in M.JUMPOFFS}

    rows = []
    for z in zs:
        lshare = {y: series[z].get(y, 0.0) / nat_light[y]
                  for y in years_obs if nat_light[y] > 0}
        pshare = {y: (_pop(data, z, y) or 0.0) / nat_pop[y]
                  for y in pop_years if nat_pop[y]}
        # v1-метрика по ряду VNL (те же окна тренда и шока)
        vnl_share = {y: vnl[z].get(y, 0.0)
                     / sum(vnl[q].get(y, 0.0) for q in zs)
                     for y in range(2012, 2025)}
        vnl_pshare = {y: pshare[y] for y in pshare if y >= 2012}
        lr, pr = _ratio(vnl_share), _ratio(vnl_pshare)
        div = round(math.log(lr) - math.log(pr), 4) if lr and pr else None
        fut_z = {}
        for j in M.JUMPOFFS:
            fut_z[j] = {}
            for s in M.SCENARIOS:
                fut_z[j][s] = {
                    str(t): {
                        "l": round(fut["light"][j][s][z][t], 1),
                        "ls": round(fut["light"][j][s][z][t]
                                    / nat_fut[j][s][t], 5),
                        "ps": round(fpop[j][s][z][t] / nat_fpop[j][s][t], 5),
                    } for t in nodes}
        rows.append({
            "id": z,
            "lshare": {str(y): round(v, 5) for y, v in lshare.items()},
            "pshare": {str(y): round(v, 5) for y, v in pshare.items()},
            "light": {str(y): round(series[z].get(y, 0.0), 1)
                      for y in years_obs},
            "lightRatio": round(lr, 4) if lr else None,
            "popRatio": round(pr, 4) if pr else None,
            "div": div,
            "model": fut_z,
        })

    m = harm["bridge"]
    return {
        "version": VERSION,
        "segments": {"dmsp": [years_obs[0], H.DMSP_LAST],
                     "vnl": [2012, 2024],
                     "model": [nodes[0], nodes[-1]]},
        "yearsObs": years_obs,
        "nodes": nodes,
        "scenarios": M.SCENARIOS,
        "jumpoffs": M.JUMPOFFS,
        "trendYears": [TREND_YEARS[0], TREND_YEARS[-1]],
        "shockYears": SHOCK_YEARS,
        "mapping": {"aBar": round(m["a_bar"], 4), "b": round(m["b"], 4),
                    "f18": round(harm["f18"], 4), "r2": round(m["r2"], 4)},
        "source": {str(y): s for y, s in source.items()},
        "natLight": {str(y): round(v, 1) for y, v in nat_light.items()},
        "natPop": {str(y): round(v) for y, v in nat_pop.items()},
        "natModel": {j: {s: {str(t): round(nat_fut[j][s][t], 1)
                             for t in nodes}
                         for s in M.SCENARIOS} for j in M.JUMPOFFS},
        "rows": rows,
    }


def main() -> None:
    b = build()
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "nightlights_v2.json"
    p.write_text(json.dumps(b, ensure_ascii=False, separators=(",", ":")))
    kb = p.stat().st_size / 1024
    print(f"OK: nightlights_v2.json ({len(b['rows'])} зон, "
          f"{b['yearsObs'][0]}-{b['yearsObs'][-1]} наблюдения + "
          f"{b['nodes'][0]}-{b['nodes'][-1]} модель, {kb:.0f} КБ)")
    nl = b["natLight"]
    y0, ym, y1 = b["yearsObs"][0], H.DMSP_LAST, b["yearsObs"][-1]
    print(f"  нац. свет (радианс-экв.): {y0} {nl[str(y0)] / 1e3:.0f}К, "
          f"{ym} {nl[str(ym)] / 1e3:.0f}К, {y1} {nl[str(y1)] / 1e3:.0f}К")


if __name__ == "__main__":
    main()
