"""INF-06 `monotowns`: моногорода и градообразующие предприятия.

Вопрос: насколько траектория моногорода определяется состоянием
градообразующего предприятия; какие города в зоне риска при негативном
сценарии?

Данные: реестр 49 пар «город - предприятие» (ручная курация по открытым
источникам, data/raw/monotowns/registry.json; построчные источники,
санкционная экспозиция EU/US/UK/Canada с датами) + ряды городов проекта.

Метод: типология по отрасли; matched comparison - траектория каждого
моногорода (индекс к 1989=100) против медианы «обычных» городов того же
размера (k ближайших по населению-1989, не моногорода и не облцентры);
полоса риска = моно-зависимость x санкционная экспозиция.

Ограничение: занятость оценочная, санкции меняются (поле «актуально на
дату»), причинность не доказуема - только ассоциации.

Запуск: python -m etl.monotowns -> web/public/data/monotowns.json
"""
from __future__ import annotations

import json
import math
import statistics

from .common import ROOT, OUT

RAW = ROOT / "data" / "raw" / "monotowns"
VERSION = "1.0.0"

BASELINE = 1989
GRID = [1959, 1970, 1979, 1989, 1999, 2009, 2019, 2026]
IDX_GRID = [1989, 1999, 2009, 2019, 2026]   # окно индекса (после 1989)
OBL_CENTERS = {"c-minsk", "c-homiel", "c-viciebsk", "c-mahilou",
               "c-hrodna", "c-brest"}
K_CONTROLS = 8
# калипер размера: контроль допустим, если |ln(население-1989)| в пределах
# CALIPER (~фактор 2); города без >= MIN_CONTROLS сопоставимых по размеру
# «типовых» соседей не сравниваются (gap=None) - крупные моногорода в
# Беларуси не с чем матчить (все большие города - облцентры или моногорода)
CALIPER = 0.70
MIN_CONTROLS = 4
DEP_WEIGHT = {"high": 2, "medium": 1, "low": 0}


def _pop(v: dict, year: int) -> float | None:
    p = v["pop"].get(str(year))
    return float(p[0]) if p else None


def _index(v: dict) -> dict[str, float] | None:
    base = _pop(v, BASELINE)
    if not base:
        return None
    return {str(y): round(_pop(v, y) / base * 100, 1)
            for y in IDX_GRID if _pop(v, y) is not None}


def risk_band(dep: str, n_sanctions: int) -> tuple[int, str]:
    score = DEP_WEIGHT[dep] + (1 if n_sanctions else 0)
    band = ("высокий" if score >= 3 else "повышенный" if score == 2
            else "умеренный" if score == 1 else "низкий")
    return score, band


def build() -> dict:
    data = json.loads((OUT / "data.json").read_text())["territories"]
    reg = json.loads((RAW / "registry.json").read_text())
    mono_ids = {p["city_id"] for p in reg}

    # пул контролей: города не-моно, не облцентры, с населением во всех
    # годах окна индекса (1989-2026)
    controls = []
    for v in data.values():
        if v["level"] != "city" or v["id"] in mono_ids or v["id"] in OBL_CENTERS:
            continue
        if all(_pop(v, y) for y in IDX_GRID):
            controls.append(v)

    def matched(town_v: dict) -> tuple[list[str], dict[str, float]]:
        """До k контролей В ПРЕДЕЛАХ КАЛИПЕРА по ln(населения-1989) + их
        медианный индекс. Если сопоставимых < MIN_CONTROLS - ([], {})
        (крупные моногорода не с чем матчить по размеру)."""
        lp = math.log(_pop(town_v, BASELINE))
        within = [c for c in controls
                  if abs(math.log(_pop(c, BASELINE)) - lp) <= CALIPER]
        if len(within) < MIN_CONTROLS:
            return [], {}
        near = sorted(within,
                      key=lambda c: abs(math.log(_pop(c, BASELINE)) - lp))[:K_CONTROLS]
        idxs = [_index(c) for c in near]
        med = {}
        for y in IDX_GRID:
            vals = [ix[str(y)] for ix in idxs if str(y) in ix]
            if vals:
                med[str(y)] = round(statistics.median(vals), 1)
        return [c["id"] for c in near], med

    towns = []
    for p in reg:
        v = data[p["city_id"]]
        idx = _index(v)
        ctrl_ids, ctrl_med = matched(v)
        gap = (round(idx["2026"] - ctrl_med["2026"], 1)
               if idx and "2026" in idx and "2026" in ctrl_med else None)
        score, band = risk_band(p["mono_dependence"], len(p.get("sanctions", [])))
        towns.append({
            "id": p["city_id"], "ru": v["ru"],
            "lat": v.get("lat"), "lon": v.get("lon"),
            "enterprise": p["enterprise_ru"],
            "enterpriseEn": p.get("enterprise_en", ""),
            "industry": p["industry"], "founded": p.get("founded", ""),
            "employment": p.get("employment_est", ""),
            "employmentYear": p.get("employment_year", ""),
            "dep": p["mono_dependence"],
            "sanctions": p.get("sanctions", []),
            "nSanctions": len(p.get("sanctions", [])),
            "riskScore": score, "risk": band,
            "pop": {str(y): _pop(v, y) for y in GRID if _pop(v, y)},
            "index": idx, "controls": ctrl_ids, "ctrlIndex": ctrl_med,
            "gap": gap,
            "nSources": len(p.get("sources", [])),
        })

    # типология по отрасли
    typ = {}
    for t in towns:
        typ.setdefault(t["industry"], []).append(t["id"])
    typology = {k: {"n": len(v), "ids": v} for k, v in
                sorted(typ.items(), key=lambda kv: -len(kv[1]))}

    # агрегат matched comparison: медианный gap по полосам риска
    def agg(subset):
        gaps = [t["gap"] for t in subset if t["gap"] is not None]
        idx26 = [t["index"]["2026"] for t in subset if t["index"] and "2026" in t["index"]]
        return {"n": len(subset), "nMatched": len(gaps),
                "medianGap": round(statistics.median(gaps), 1) if gaps else None,
                "medianIndex2026": round(statistics.median(idx26), 1) if idx26 else None}
    by_risk = {b: agg([t for t in towns if t["risk"] == b])
               for b in ("высокий", "повышенный", "умеренный", "низкий")}
    by_dep = {dp: agg([t for t in towns if t["dep"] == dp])
              for dp in ("high", "medium", "low")}

    return {"baselineYear": BASELINE, "grid": GRID, "idxGrid": IDX_GRID,
            "towns": towns, "typology": typology,
            "aggregate": {"all": agg(towns), "byRisk": by_risk, "byDep": by_dep}}


def main() -> None:
    b = build()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "monotowns.json").write_text(json.dumps(
        {"version": VERSION, **b}, ensure_ascii=False))

    a = b["aggregate"]
    unmatched = [t["ru"] for t in b["towns"] if t["gap"] is None]
    print(f"OK: monotowns.json ({len(b['towns'])} моногородов, "
          f"{len(b['typology'])} отраслей)")
    print("  отрасли:", ", ".join(f"{k} {v['n']}" for k, v in
                                   list(b["typology"].items())[:6]))
    print(f"  медианный индекс 1989->2026 (все моногорода): {a['all']['medianIndex2026']}")
    print("  gap к типовым по ЗАВИСИМОСТИ (только сопоставимые по размеру, "
          "АССОЦИАЦИЯ):")
    for dp, ru in (("high", "высокая"), ("medium", "средняя"), ("low", "низкая")):
        r = a["byDep"][dp]
        print(f"    зависимость {ru:8s}: сопоставимо {r['nMatched']:2d}/{r['n']:2d} "
              f"медиана gap={r['medianGap']}")
    print(f"  без сопоставимых по размеру (gap=None): {len(unmatched)} "
          f"крупнейших - {', '.join(unmatched[:6])}…")
    hi = [t for t in b["towns"] if t["risk"] == "высокий"]
    print("  зона высокого риска (реестр):", ", ".join(t["ru"] for t in hi))


if __name__ == "__main__":
    main()
