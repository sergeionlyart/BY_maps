"""Прогон прогноза 2026-2075 по трём сценариям (уровни 0-3).

Схема:
- jump-off: официальные структуры на 01.01.2026 (дата-портал Белстата);
  дополнительно ряд adjusted (WP-F3) - официальный старт минус центральная
  оценка незарегистрированного оттока 2020-2026 (etl.mirror);
- для каждой области и Минска - CCMPP шагом 5 лет: областные ASFR-профили
  2018 г., масштабируемые к сценарной национальной траектории СКР с
  сохранением областных дифференциалов; национальная смертность (HMD-2018),
  масштабируемая к сценарным e0(t); миграция - внутренняя матрица-2019 x
  centripetal + международное сценарное сальдо по ключам WP-F3;
- страна = сумма областей; районы и города - этап 5 (модуль sub, IPF);
- квантили q10/q90: относительная ширина 80% предиктивного интервала
  WPP 2024 (Lower/Upper 80 PI к Medium), применённая к базовой траектории;
  для областей - те же относительные коэффициенты (документированное
  упрощение MVP).

Запуск: python -m etl.forecast.run  ->  web/public/data/forecast.json
                                        data/curated/forecast_v2026_3.csv
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from ..common import ROOT
from . import TERRITORIES, AGE_GROUPS, FERTILE, STEP, VERSION
from .data import (jumpoff_2026, mortality_mx, asfr_profile,
                   wpp_total_variants, wpp_trajectory)
from .lifetable import scale_to_e0, survival_5y
from .ccmpp import project_step, total
from .migration import step_net_migration

SCEN_DIR = Path(__file__).parent / "scenarios"
OUT_WEB = ROOT / "web" / "public" / "data" / "forecast.json"
OUT_CSV = ROOT / "data" / "curated" / "forecast_v2026_3.csv"

STEP_YEARS = list(range(2026, 2077, STEP))  # 2026..2076
EXPORT_YEARS = [y for y in STEP_YEARS if y <= 2071] + [2075]

# национальный СКР 2018 (HFD): якорь для масштабирования областных профилей
TFR_NAT_2018 = 1.448


def _interp(targets: dict, year: int) -> float:
    """Линейная интерполяция сценарных таргетов {год: значение}."""
    pts = sorted((int(y), float(v)) for y, v in targets.items())
    if year <= pts[0][0]:
        return pts[0][1]
    if year >= pts[-1][0]:
        return pts[-1][1]
    for (y0, v0), (y1, v1) in zip(pts, pts[1:]):
        if y0 <= year <= y1:
            return v0 + (v1 - v0) * (year - y0) / (y1 - y0)
    return pts[-1][1]


def jumpoff_adjusted() -> tuple[dict, dict]:
    """Скорректированный старт 2026 (WP-F3): официальные структуры минус
    mid-поправка на незарегистрированный отток (data/curated/adjustment.csv),
    распределённая по возрастному профилю эмигранта и полу (etl.mirror).

    Возвращает (структуры, {'note': ...})."""
    import csv as _csv

    from ..mirror import AGE_PROFILE, MALE_SHARE

    adj = {}
    for r in _csv.DictReader(open(ROOT / "data/curated/adjustment.csv")):
        if r["year"] == "2026" and r["territory_id"] in TERRITORIES:
            adj[r["territory_id"]] = {k: float(r[k]) for k in ("low", "mid", "high")}
    out = {}
    for t, pop in jumpoff_2026().items():
        cut = adj.get(t, {}).get("mid", 0.0)
        new = {s: dict(v) for s, v in pop.items()}
        for g, share in AGE_PROFILE.items():
            take = cut * share
            for s, sex_share in (("m", MALE_SHARE), ("f", 1 - MALE_SHARE)):
                new[s][g] = max(new[s][g] - take * sex_share, 0.0)
        out[t] = new
    total_cut = sum(v["mid"] for v in adj.values())
    lo = sum(v["low"] for v in adj.values())
    hi = sum(v["high"] for v in adj.values())
    note = (f"официальный ряд минус центральная оценка незарегистрированного "
            f"оттока 2020–2026 ({total_cut / 1000:.0f} тыс.; интервал "
            f"{lo / 1000:.0f}–{hi / 1000:.0f} тыс., зеркальная статистика "
            f"ЕС/Польши/Литвы/Грузии — WP-F3)")
    return out, {"note": note}


def load_scenarios() -> dict[str, dict]:
    out = {}
    for p in sorted(SCEN_DIR.glob("*.yaml")):
        s = yaml.safe_load(p.read_text())
        if s.get("follow_wpp"):
            # траектории напрямую из WPP medium (годовые значения)
            s["tfr"] = {str(y): v for y, v in wpp_trajectory("TFR").items()}
            s["e0_male"] = {str(y): v for y, v in wpp_trajectory("LExMale").items()}
            s["e0_female"] = {str(y): v for y, v in wpp_trajectory("LExFemale").items()}
            s["intl_net_per_year"] = {str(y): v * 1000
                                      for y, v in wpp_trajectory("NetMigrations").items()
                                      if y >= 2024}
        out[s["id"]] = s
    return out


def run_scenario(scen: dict, keep_structures: bool = False,
                 jumpoff: dict | None = None) -> dict | tuple[dict, dict]:
    """Прогон сценария. Возвращает {terr: {year: pop_total}} (+ 'BY');
    при keep_structures - дополнительно {terr: {year: {sex: {age: pop}}}}
    (для IPF-согласования районов и городов, этап 5).
    jumpoff - альтернативные стартовые структуры (WP-F3: ряд adjusted);
    по умолчанию - официальные оценки на 01.01.2026."""
    mx0 = mortality_mx(2018)
    prof = asfr_profile(2018)
    start = jumpoff if jumpoff is not None else jumpoff_2026()
    pops = {t: {s: dict(v) for s, v in start[t].items()} for t in TERRITORIES}

    series: dict[str, dict[int, float]] = {t: {} for t in TERRITORIES + ["BY"]}
    structures: dict[str, dict[int, dict]] = {t: {} for t in TERRITORIES}
    for t in TERRITORIES:
        series[t][2026] = total(pops[t])
        structures[t][2026] = {s: dict(v) for s, v in pops[t].items()}
    series["BY"][2026] = sum(series[t][2026] for t in TERRITORIES)

    for y0 in STEP_YEARS[:-1]:
        y_mid = y0 + STEP // 2
        # смертность шага: национальные mx, масштабированные к e0(середина шага)
        surv = {}
        for sex, key in (("m", "e0_male"), ("f", "e0_female")):
            target = _interp(scen[key], y_mid)
            surv[sex] = survival_5y(scale_to_e0(mx0[sex], target))
        tfr_t = _interp(scen["tfr"], y_mid)
        for t in TERRITORIES:
            # областной ASFR: профиль-2018, масштаб к сценарной нац. траектории
            scale = tfr_t / TFR_NAT_2018
            asfr = {g: prof["asfr"][t].get(g, 0.0) * scale for g in FERTILE}
            net = step_net_migration(t, y0, scen)
            pops[t], _ = project_step(pops[t], surv, asfr, net)
            series[t][y0 + STEP] = total(pops[t])
            structures[t][y0 + STEP] = {s: dict(v) for s, v in pops[t].items()}
        series["BY"][y0 + STEP] = sum(series[t][y0 + STEP] for t in TERRITORIES)
    return (series, structures) if keep_structures else series


def pi_ratios() -> dict[str, dict[int, float]]:
    """Относительная ширина 80% PI WPP к медиане по годам."""
    v = wpp_total_variants()
    med, lo, hi = v["Medium"], v["Lower 80 PI"], v["Upper 80 PI"]
    years = sorted(set(med) & set(lo) & set(hi))
    return {
        "lo": {y: lo[y] / med[y] for y in years},
        "hi": {y: hi[y] / med[y] for y in years},
    }


def _pi_at(ratios: dict[int, float], year: int) -> float:
    ys = sorted(ratios)
    y = min(max(year, ys[0]), ys[-1])
    if y in ratios:
        return ratios[y]
    lo = max(x for x in ys if x <= y)
    hi = min(x for x in ys if x >= y)
    if lo == hi:
        return ratios[lo]
    t = (y - lo) / (hi - lo)
    return ratios[lo] + t * (ratios[hi] - ratios[lo])


def _series_entry(pts: dict, sid: str, ratios: dict) -> dict:
    years = EXPORT_YEARS

    def val(y: float) -> float:
        if y in pts:
            return pts[y]
        y0 = max(x for x in pts if x <= y)
        y1 = min(x for x in pts if x >= y)
        k = (y - y0) / (y1 - y0)
        return pts[y0] + k * (pts[y1] - pts[y0])

    entry = {"years": years, "pop": [round(val(y)) for y in years]}
    if sid == "base":
        entry["q10"] = [round(val(y) * _pi_at(ratios["lo"], y)) for y in years]
        entry["q90"] = [round(val(y) * _pi_at(ratios["hi"], y)) for y in years]
    return entry


def export(all_series: dict[str, dict], sub_series: dict[str, dict],
           adj_series: dict[str, dict] | None = None,
           adj_meta: dict | None = None) -> None:
    """all_series: уровни 0-1 ({sid: {terr: {year: pop}}});
    sub_series: уровни 2-3 после IPF ({sid: {terr: {year: pop}}});
    adj_series: уровни 0-1 со скорректированного старта (WP-F3)."""
    ratios = pi_ratios()
    terrs = {}
    for t in TERRITORIES + ["BY"]:
        terrs[t] = {}
        for sid, series in all_series.items():
            terrs[t][sid] = _series_entry(series[t], sid, ratios)

    # уровни 2-3: районы и города (сценарность - через IPF к области;
    # квантили не публикуются - неопределённость коммуницируется сценариями)
    for sid, series in sub_series.items():
        for t, pts in series.items():
            terrs.setdefault(t, {})[sid] = {
                "years": EXPORT_YEARS,
                "pop": [round(pts[y]) for y in EXPORT_YEARS],
            }
    # точка Минска на карте городов - зеркало BY-HM
    terrs["c-minsk"] = {sid: {"years": e["years"], "pop": e["pop"]}
                        for sid, e in terrs["BY-HM"].items()}

    # ряд adjusted (WP-F3): только уровни 0-1 - поправка территориально
    # обоснована лишь до уровня областей
    adjusted = {}
    if adj_series:
        for t in TERRITORIES + ["BY"]:
            adjusted[t] = {sid: _series_entry(series[t], sid, ratios)
                           for sid, series in adj_series.items()}

    scen_meta = {sid: {"name": s["name"], "description": s["description"].strip()}
                 for sid, s in load_scenarios().items()}
    OUT_WEB.write_text(json.dumps({
        "version": VERSION,
        "horizon": [2026, 2075],
        "scenarios": ["base", "optimistic", "negative"],
        "scenarioMeta": scen_meta,
        "jumpoff": ["official", "adjusted"] if adjusted else ["official"],
        **({"adjustedMeta": adj_meta} if adj_meta else {}),
        "dtype": "f",
        "territories": terrs,
        **({"adjusted": adjusted} if adjusted else {}),
    }, ensure_ascii=False))

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["territory_id", "scenario", "jumpoff", "year", "pop", "q10", "q90"])

        def dump(block: dict, jo: str) -> None:
            for t, scens_ in sorted(block.items()):
                for sid, e in sorted(scens_.items()):
                    for i, y in enumerate(e["years"]):
                        w.writerow([t, sid, jo, y, e["pop"][i],
                                    e.get("q10", [""] * len(e["years"]))[i],
                                    e.get("q90", [""] * len(e["years"]))[i]])
        dump(terrs, "official")
        if adjusted:
            dump(adjusted, "adjusted")
    print(f"OK: forecast.json + {OUT_CSV.name}")


def main() -> None:
    from . import sub

    scens = load_scenarios()
    all_series, all_structs = {}, {}
    for sid, s in scens.items():
        all_series[sid], all_structs[sid] = run_scenario(s, keep_structures=True)

    # уровни 2-3: одна CCR/CCMPP-проекция, сценарность - через IPF к области
    children = sub.project_children()
    official = sub.official_totals_2026()
    sub_series: dict[str, dict] = {}
    for sid in scens:
        totals = sub.reconcile(children, all_structs[sid], EXPORT_YEARS,
                               calibrate_2026=official)
        # экспортный периметр района-хоста = район (перепись) + его город
        export_units = {t: dict(v) for t, v in totals.items()}
        for host, city in sub.HOSTED.items():
            for y in EXPORT_YEARS:
                export_units[host][y] = totals[host][y] + totals[city][y]
        cities = sub.cities_forecast(export_units, set(children), EXPORT_YEARS)
        sub_series[sid] = {**export_units, **cities}

    # ряд adjusted (WP-F3): те же сценарии со скорректированного старта
    adj_jump, adj_meta = jumpoff_adjusted()
    adj_series = {sid: run_scenario(s, jumpoff=adj_jump) for sid, s in scens.items()}

    export(all_series, sub_series, adj_series, adj_meta)
    wpp = wpp_total_variants()
    for sid, series in sorted(all_series.items()):
        p50 = series["BY"][2051] / 1000
        p75 = series["BY"][2076] / 1000
        print(f"  {sid:12s}: узел 2051≈{p50:.0f} тыс. (WPP medium-2050 {wpp['Medium'][2050]:.0f}, "
              f"low {wpp['Low'][2050]:.0f}, high {wpp['High'][2050]:.0f}); узел 2076≈{p75:.0f} тыс.")
    n_sub = len(sub_series["base"])
    print(f"  уровни 2-3: {n_sub} территорий (районы, города) по 3 сценариям")
    print(f"  adjusted (WP-F3): старт {adj_series['base']['BY'][2026] / 1000:.0f} тыс. "
          f"(официальный {all_series['base']['BY'][2026] / 1000:.0f}); "
          f"base-2050 {adj_series['base']['BY'][2051] / 1000:.0f} тыс.")


if __name__ == "__main__":
    main()
