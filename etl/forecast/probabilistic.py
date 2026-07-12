"""Вероятностный слой прогноза: Монте-Карло траектории СКР/ОПЖ -> веер.

Заменяет прежний ПРОПОРЦИОНАЛЬНЫЙ перенос 80% PI WPP (q10 = база x
WPP_low/WPP_med) настоящей симуляцией: для каждой из N реализаций
сэмплируются персистентные (сохраняющиеся по горизонту) отклонения
траекторий СКР и ОПЖ от медианы WPP, прогоняется CCMPP, и по ансамблю
берутся эмпирические квантили. В отличие от переноса, веер проходит
через возрастную структуру и уровни 0-1 (каждая область прогоняется через
свой CCMPP) и позволяет вероятностные утверждения на СТРАНОВОМ уровне:
P(убыли), P(население < X).

ВАЖНО: шок СКР/ОПЖ - один общий на страну (см. ниже), поэтому области
делят общий национальный фактор. Областные полосы отражают лишь эту
общую компоненту; идиосинкратическая областная неопределённость (своя
СКР/ОПЖ/миграция) НЕ сэмплируется, поэтому областные интервалы - нижняя
оценка истинной. Вероятностные утверждения даются только по стране, где
ширина откалибрована по WPP.

Модель отклонений (персистентный «режим» + мягкий рост неопределённости):
  СКР_d(y) = медиана(y) + z_tfr * A_TFR * (1 + G*(y-2026)/49)
  ОПЖ_d(y) = медиана(y) + z_e0  * A_E0  * (1 + G*(y-2026)/49)
z_tfr, z_e0 ~ N(0,1) - по одному персистентному шоку на реализацию,
общему для всех областей (СКР и ОПЖ страны - устойчивые режимы).
Константы КАЛИБРОВАНЫ так, что 80% интервал населения страны совпадает
с 80% PI WPP-2024 на 2050 и 2075 (гейт в тестах); т.е. на страновом
уровне ширина 80%-полосы по построению ~ WPP, а самостоятельная новизна
веера - в декомпозиции (возраст, области) и вероятностных утверждениях,
а не в независимой оценке ширины. Миграция оставлена детерминированной -
её неопределённость коммуницируется отдельным рядом adjusted (WP-F3);
шоки СКР и ОПЖ независимы (историческая корреляция не наложена).

Канонический выход слоя - блок `probabilistic` в web/public/data/forecast.json
(его формирует etl.forecast.run). Прямой запуск модуля - только
калибровочная проверка: печатает веер и пишет отладочную копию в
docs/notes/probabilistic.json (сайт не потребляет её).

Запуск: python -m etl.forecast.probabilistic
"""
from __future__ import annotations

import json
import random

from ..common import ROOT
from . import TERRITORIES
from .data import wpp_total_variants
from .run import load_scenarios, run_scenario, EXPORT_YEARS

# калибровка: 80% интервал BY совпадает с WPP-2024 на 2050 (~7,1%) и 2075 (~16,3%)
A_TFR = 0.235         # СД отклонения СКР при горизонте 0
A_E0 = 2.0            # СД отклонения ОПЖ (лет)
G = 0.30              # рост неопределённости к горизонту 2075
N_DRAWS = 600
SEED = 20260712
QUANTILES = [5, 10, 25, 50, 75, 90, 95]
HORIZON = 2075 - 2026
LEVEL1 = TERRITORIES + ["BY"]


def _weight(y: int) -> float:
    return 1 + G * (max(0, y - 2026) / HORIZON)


def _perturb(base: dict, z_tfr: float, z_e0: float) -> dict:
    scen = dict(base)
    scen["tfr"] = {k: max(0.5, v + z_tfr * A_TFR * _weight(int(k)))
                   for k, v in base["tfr"].items()}
    for key in ("e0_male", "e0_female"):
        scen[key] = {k: v + z_e0 * A_E0 * _weight(int(k))
                     for k, v in base[key].items()}
    return scen


def _interp(pts: dict[int, float], y: int) -> float:
    if y in pts:
        return pts[y]
    lo = max(x for x in pts if x <= y)
    hi = min(x for x in pts if x >= y)
    return pts[lo] + (y - lo) / (hi - lo) * (pts[hi] - pts[lo])


def ensemble(n: int = N_DRAWS, seed: int = SEED,
             jumpoff: dict | None = None) -> dict[str, dict[int, list]]:
    """{terr: {year: [значения по реализациям]}} на EXPORT_YEARS.
    jumpoff - альтернативный старт (ряд adjusted, WP-F3); по умолчанию
    официальные структуры 01.01.2026."""
    base = load_scenarios()["base"]
    rng = random.Random(seed)
    ens = {t: {y: [] for y in EXPORT_YEARS} for t in LEVEL1}
    for _ in range(n):
        s = run_scenario(_perturb(base, rng.gauss(0, 1), rng.gauss(0, 1)),
                         jumpoff=jumpoff)
        for t in LEVEL1:
            for y in EXPORT_YEARS:
                ens[t][y].append(_interp(s[t], y))
    return ens


def _q(vals: list[float], p: int) -> float:
    v = sorted(vals)
    idx = min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))
    return v[idx]


def quantile_fan(ens: dict) -> dict:
    """{terr: {'q05':[...], ..., 'q95':[...]}} по EXPORT_YEARS."""
    out = {}
    for t in LEVEL1:
        out[t] = {f"q{p:02d}": [round(_q(ens[t][y], p)) for y in EXPORT_YEARS]
                  for p in QUANTILES}
    return out


def prob_statements(ens: dict) -> dict:
    """Вероятностные утверждения по стране (доля реализаций)."""
    n = len(ens["BY"][EXPORT_YEARS[0]])

    def share(year, thr, below=True):
        vals = ens["BY"][year]
        c = sum(1 for v in vals if (v < thr if below else v >= thr))
        return round(c / n, 3)

    start = ens["BY"][2026][0]  # старт детерминирован
    return {
        "n": n,
        "start2026": round(start),
        "pBelow8M_2041": share(2041, 8_000_000),
        "pBelow7M_2051": share(2051, 7_000_000),
        "pBelow6M_2075": share(2075, 6_000_000),
        "pDecline2051": round(sum(1 for i in range(n)
                                  if ens["BY"][2051][i] < start) / n, 3),
        "pGrowthAny": round(sum(1 for i in range(n)
                                if ens["BY"][2075][i] > start) / n, 3),
    }


def _wpp_halfwidth(year: int) -> float:
    """Полуширина 80% PI WPP-2024 к медиане на данный год (доля)."""
    v = wpp_total_variants()
    lo, hi, med = v["Lower 80 PI"][year], v["Upper 80 PI"][year], v["Medium"][year]
    return (hi - lo) / 2 / med


def wpp_validation(fan: dict) -> dict:
    """Гейт калибровки: полуширина 80% симуляции vs WPP на 2051 и 2075."""
    by = fan["BY"]
    out = {}
    for y, wy in ((2051, 2050), (2075, 2075)):
        i = EXPORT_YEARS.index(y)
        med = (by["q10"][i] + by["q90"][i]) / 2
        sim = (by["q90"][i] - by["q10"][i]) / 2 / med
        out[str(y)] = {"sim80": round(sim, 4), "wpp80": round(_wpp_halfwidth(wy), 4)}
    return out


def build() -> dict:
    ens = ensemble()
    fan = quantile_fan(ens)
    return {
        "exportYears": EXPORT_YEARS,
        "nDraws": len(ens["BY"][EXPORT_YEARS[0]]),
        "calibration": {"aTfr": A_TFR, "aE0": A_E0, "growth": G, "seed": SEED},
        "fan": fan,
        "stats": prob_statements(ens),
        "wppValidation": wpp_validation(fan),
    }


def main() -> None:
    b = build()
    notes = ROOT / "docs" / "notes"
    notes.mkdir(parents=True, exist_ok=True)
    (notes / "probabilistic.json").write_text(json.dumps(
        {"version": "1.0.0", **b}, ensure_ascii=False))

    f = b["fan"]["BY"]
    yi = EXPORT_YEARS.index
    print(f"OK: probabilistic.json ({b['nDraws']} реализаций)")
    for Y in (2050, 2075):
        i = yi(2051 if Y == 2050 else 2075)
        print(f"  BY {EXPORT_YEARS[i]}: медиана {f['q50'][i] / 1e6:.2f}М · "
              f"80% [{f['q10'][i] / 1e6:.2f}; {f['q90'][i] / 1e6:.2f}] · "
              f"90% [{f['q05'][i] / 1e6:.2f}; {f['q95'][i] / 1e6:.2f}]")
    st = b["stats"]
    print(f"  P(убыль к 2051) = {st['pDecline2051']:.0%}; "
          f"P(<7 млн к 2051) = {st['pBelow7M_2051']:.0%}; "
          f"P(<6 млн к 2075) = {st['pBelow6M_2075']:.0%}")
    for y, w in b["wppValidation"].items():
        print(f"  калибровка {y}: 80% симуляция {w['sim80']:.1%} vs WPP {w['wpp80']:.1%}")


if __name__ == "__main__":
    main()
