"""INF-12 «Цена пустеющей карты»: метрики материального навеса городов.

Конвейер на стандартной библиотеке поверх вендоренных агрегатов:
  - data/curated/urban/city_registry.csv, exclusions.csv (etl.urban_registry)
  - data/raw/urban/morph_city_epoch.csv, morph_fixed.csv, morph_flows.csv
    (etl.urban_morph, GHS-BUILT-S R2023A, 9 сценариев порог x замыкание)
  - data/raw/urban/city_light.csv (etl.urban_light, DMSP/VNL по маскам)
  - data/raw/urban/city_roads.csv, city_poi.csv, admin_built.csv,
    admin_areas.csv (etl.urban_osm, снимок OSM)
  - web/public/data/data.json (население; переписи 'c', оценки 'e')

Показатели (пререгистрация v0.1): BPC=B/P, MOR=BGR-PGR (лог-годовые темпы),
edge_expansion_share, компактность, UBI=R/B, SUG=gB-gR, CEUR/IHS ядро-край,
дороги на 1000 жителей. Главный интервал 1990-2020. Знак MOR публикуется
только с интервалом сценарной неопределённости и MDC.

Выходы:
  web/public/data/urban_overhang.json          - story JSON сайта
  data/raw/urban/final/city_metrics.csv        - город x эпоха (осн. сценарий)
  data/raw/urban/final/city_interval_metrics.csv
  data/raw/urban/final/city_typology.csv
  data/raw/urban/final/computed_results.json   - канонические числа

Запуск: python -m etl.urban
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

VERSION = "1.0.0"

try:
    # внутри репозитория BY_maps: python -m etl.urban
    from .common import OUT, ROOT
    from .urban_registry import URBAN_CURATED
    RAW = ROOT / "data" / "raw" / "urban"
    FINAL = RAW / "final"
    MONOTOWNS = ROOT / "data" / "curated" / "monotowns.csv"
    PKG = None
except ImportError:
    # автономный запуск внутри пакета артефактов: python3 code/build.py
    PKG = Path(__file__).resolve().parent.parent
    RAW = PKG / "sources" / "raw"
    URBAN_CURATED = RAW
    FINAL = PKG / "data" / "final"
    OUT = FINAL          # story.json кладётся в data/final
    MONOTOWNS = RAW / "monotowns.csv"

EPOCHS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020]
PRIMARY_SC = "t10_c1"
SCENARIOS = [f"t{t:02d}_c{c}" for t in (5, 10, 20) for c in (0, 1, 2)]
MAIN_INTERVAL = (1990, 2020)
CHART_INTERVALS = [(1975, 1990), (1990, 2020), (2000, 2020), (2010, 2020)]

# Пороги классификации (assumptions)
PGR_EPS = 0.001          # 1/год: полоса «стабильности» населения
REL_ERR = [(10.0, 0.05), (1.0, 0.10), (0.0, 0.20)]  # (км² 2020, отн. ошибка B)
AGREEMENT_MIN = 0.75     # доля сценариев с тем же типом
EES_SPRAWL = 0.5         # порог «периферийности» новой застройки
EPS_R, EPS_B = 1.0, 10_000.0   # эпсилоны CEUR (нВт-сумма; м² = 1 ячейка)

# Matching (H-1)
TREAT_PGR = -0.002       # сокращающиеся
CONTROL_PGR = -0.001     # стабильные/растущие
CALIPER_LNPOP = 0.7      # урок INF-06: не сравнивать города разных порядков


# ---------------------------------------------------------------- загрузка

def load_registry() -> list[dict]:
    with (URBAN_CURATED / "city_registry.csv").open() as f:
        return list(csv.DictReader(f))


def load_population() -> dict[str, dict[int, tuple[int, str]]]:
    if PKG is not None:
        # пакет: вендоренный экстракт рядов (city_id,year,population,status)
        res: dict[str, dict[int, tuple[int, str]]] = {}
        with (RAW / "city_population.csv").open() as f:
            for r in csv.DictReader(f):
                res.setdefault(r["city_id"], {})[int(r["year"])] = (
                    int(r["population"]), r["status"])
        return res
    data = json.loads((OUT / "data.json").read_text())
    res = {}
    for cid, t in data["territories"].items():
        if t.get("level") != "city":
            continue
        res[cid] = {int(y): (pv[0], pv[1]) for y, pv in t["pop"].items()
                    if isinstance(pv, list) and pv[0]}
    return res


def load_morph() -> tuple[dict, dict, dict]:
    """-> (dyn[(sc,cid,epoch)], fixed[(sc,cid,epoch)], flows[(sc,cid,e1,e2)])."""
    dyn, fixed, flows = {}, {}, {}
    with (RAW / "morph_city_epoch.csv").open() as f:
        for r in csv.DictReader(f):
            dyn[(r["scenario"], r["city_id"], int(r["epoch"]))] = {
                "seed": int(r["seed_found"]),
                "cells": int(r["footprint_cells"]),
                "built": float(r["built_dyn_m2"]),
                "perimeter": int(r["perimeter_edges"]),
                "merged": r["merged_with"],
            }
    with (RAW / "morph_fixed.csv").open() as f:
        for r in csv.DictReader(f):
            fixed[(r["scenario"], r["city_id"], int(r["epoch"]))] = {
                "fixed_cells": int(r["fixed_cells"]),
                "core_cells": int(r["core_cells"]),
                "built": float(r["built_fixed_m2"]),
                "core": float(r["built_core_m2"]),
                "edge": float(r["built_edge_m2"]),      # строго entry>=2
                "buffer": float(r.get("built_buffer_m2", 0) or 0),
            }
    with (RAW / "morph_flows.csv").open() as f:
        for r in csv.DictReader(f):
            flows[(r["scenario"], r["city_id"],
                   int(r["epoch_start"]), int(r["epoch_end"]))] = {
                "infill": float(r["infill_m2"]),
                "edge": float(r["edge_m2"]),
                "negative": float(r["negative_m2"]),
            }
    return dyn, fixed, flows


def load_light() -> dict:
    """-> light[(sensor, year, cid)] = {total, core, edge, buffer}."""
    res = {}
    with (RAW / "city_light.csv").open() as f:
        for r in csv.DictReader(f):
            res[(r["sensor"], int(r["year"]), r["city_id"])] = {
                k: float(r[f"light_{k}"]) if r[f"light_{k}"] != "" else None
                for k in ("total", "core", "edge", "buffer")
            }
    return res


def load_csv_map(path: Path, key_fields: list[str]) -> dict:
    if not path.exists():
        return {}
    res = {}
    with path.open() as f:
        for r in csv.DictReader(f):
            res[tuple(r[k] for k in key_fields)] = r
    return res


# ---------------------------------------------------------- население

def pop_at(series: dict[int, tuple[int, str]], year: int,
           ) -> tuple[float | None, str]:
    """Население на год: точное значение или линейная интерполяция.

    Статус: census/estimate (точный год), interpolated (между точками),
    None вне наблюдаемого диапазона (экстраполяции нет).
    """
    if year in series:
        v, st = series[year]
        return float(v), "census" if st == "c" else "estimate"
    years = sorted(series)
    prev = max((y for y in years if y < year), default=None)
    nxt = min((y for y in years if y > year), default=None)
    if prev is None or nxt is None:
        return None, "missing"
    v0, v1 = series[prev][0], series[nxt][0]
    w = (year - prev) / (nxt - prev)
    return v0 + (v1 - v0) * w, "interpolated"


def g_rate(x1: float, x2: float, dt: float) -> float | None:
    if not x1 or not x2 or x1 <= 0 or x2 <= 0 or dt <= 0:
        return None
    return (math.log(x2) - math.log(x1)) / dt


def built_at(fx: dict, sc: str, cid: str, year: float) -> float | None:
    """Застройка фикс-рамки, линейно интерполированная между эпохами.

    После 2020 - заморозка на уровне 2020 (наблюдений нет) [MODEL].
    """
    if year >= 2020:
        rec = fx.get((sc, cid, 2020))
        return rec["built"] if rec else None
    if year <= 1975:
        rec = fx.get((sc, cid, 1975))
        return rec["built"] if rec else None
    e0 = max(e for e in EPOCHS if e <= year)
    e1 = min(e for e in EPOCHS if e >= year)
    r0, r1 = fx.get((sc, cid, e0)), fx.get((sc, cid, e1))
    if not r0 or not r1:
        return None
    if e0 == e1:
        return r0["built"]
    w = (year - e0) / (e1 - e0)
    return r0["built"] + (r1["built"] - r0["built"]) * w


def core_edge_at(fx: dict, sc: str, cid: str, year: float,
                 ) -> tuple[float, float] | None:
    """(built_core, built_edge) фикс-рамки, интерполяция между эпохами.

    После 2020 - заморозка на уровне 2020 [MODEL].
    """
    yy = min(max(year, 1975), 2020)
    e0 = max(e for e in EPOCHS if e <= yy)
    e1 = min(e for e in EPOCHS if e >= yy)
    r0, r1 = fx.get((sc, cid, e0)), fx.get((sc, cid, e1))
    if not r0 or not r1:
        return None
    if e0 == e1:
        return r0["core"], r0["edge"]
    w = (yy - e0) / (e1 - e0)
    return (r0["core"] + (r1["core"] - r0["core"]) * w,
            r0["edge"] + (r1["edge"] - r0["edge"]) * w)


MIN_ZONE_M2 = 50_000.0   # 5 га: минимальный размер зоны для CEUR/IHS


def rel_err_for(b2020_m2: float) -> float:
    km2 = b2020_m2 / 1e6
    for lim, err in REL_ERR:
        if km2 >= lim:
            return err
    return REL_ERR[-1][1]


# ------------------------------------------------------------- метрики

def interval_metrics(sc: str, cid: str, y1: int, y2: int,
                     pop: dict, fixed: dict, flows: dict) -> dict | None:
    p1, st1 = pop_at(pop[cid], y1)
    p2, st2 = pop_at(pop[cid], y2)
    b1 = fixed.get((sc, cid, y1), {}).get("built")
    b2 = fixed.get((sc, cid, y2), {}).get("built")
    if None in (p1, p2, b1, b2) or 0 in (p1, p2) or b1 <= 0 or b2 <= 0:
        return None
    dt = y2 - y1
    pgr = g_rate(p1, p2, dt)
    bgr = g_rate(b1, b2, dt)
    inf_sum = edge_sum = 0.0
    for i in range(len(EPOCHS) - 1):
        e1, e2 = EPOCHS[i], EPOCHS[i + 1]
        if e1 >= y1 and e2 <= y2:
            fl = flows.get((sc, cid, e1, e2))
            if fl:
                inf_sum += fl["infill"]
                edge_sum += fl["edge"]
    total_new = inf_sum + edge_sum
    ees = edge_sum / total_new if total_new > 0 else None
    return {
        "pgr": pgr, "bgr": bgr, "mor": bgr - pgr,
        "ees": ees, "new_built_m2": total_new,
        "pop_status": f"{st1}/{st2}",
        "p1": p1, "p2": p2, "b1": b1, "b2": b2,
    }


def classify(m: dict | None, mdc_b: float, mor_lo: float, mor_hi: float,
             mdc_mor: float, merged_grow_satellite: bool) -> str:
    """Правиловая типология T1-TX по интервалу 1990-2020.

    Гейт ТЗ §10.3: содержательный класс присваивается только при устойчивом
    знаке MOR (одинаков во всех сценариях границ и выше MDC); иначе TX
    (для сокращающихся - T5 «без надёжного сигнала фонда»).
    """
    if m is None:
        return "TX"
    pgr, bgr, mor, ees = m["pgr"], m["bgr"], m["mor"], m["ees"]
    mor_robust = (((mor_lo > 0 and mor_hi > 0) or (mor_lo < 0 and mor_hi < 0))
                  and abs(mor) > mdc_mor)
    decline = pgr < -PGR_EPS
    grow = pgr > PGR_EPS
    if merged_grow_satellite and decline:
        return "T6"
    if decline:
        if not mor_robust:
            return "T5"
        if mor <= 0:
            return "TX"  # сокращение с уплотнением - вне базовой типологии
        if bgr > mdc_b:
            return "T4"
        if abs(bgr) <= mdc_b:
            return "T3"
        return "T5"      # bgr < -mdc_b: базовый GHSL не измеряет снос
    if not mor_robust:
        return "TX"      # рост/стабильность без устойчивого знака MOR
    if grow:
        if ees is not None and ees > EES_SPRAWL and bgr > mdc_b and mor > 0:
            return "T2"
        return "T1"
    # стабильное население
    if ees is not None and ees > EES_SPRAWL and bgr > mdc_b and mor > 0:
        return "T2"
    return "TX"


def light_window_mean(light: dict, sensor: str, years: list[int], cid: str,
                      field: str) -> float | None:
    vals = [light[(sensor, y, cid)][field] for y in years
            if (sensor, y, cid) in light
            and light[(sensor, y, cid)][field] is not None]
    return sum(vals) / len(vals) if vals else None


# ---------------------------------------------------------------- main

def build() -> dict:
    cities = load_registry()
    ids = [c["city_id"] for c in cities]
    byid = {c["city_id"]: c for c in cities}
    pop = load_population()
    dyn, fixed, flows = load_morph()
    light = load_light()
    roads = load_csv_map(RAW / "city_roads.csv", ["city_id", "class_group"])
    poi = load_csv_map(RAW / "city_poi.csv", ["city_id", "category"])
    admin_built = load_csv_map(RAW / "admin_built.csv", ["city_id", "epoch"])
    admin_areas = load_csv_map(RAW / "admin_areas.csv", ["city_id"])
    mono = {}
    if MONOTOWNS.exists():
        with MONOTOWNS.open() as f:
            for r in csv.DictReader(f):
                mono[r.get("city_id", "")] = r.get("mono_dependence", "")

    y1, y2 = MAIN_INTERVAL
    dt_main = y2 - y1

    # --- пер-город: интервал 1990-2020 по всем сценариям + admin-рамке
    per_city: dict[str, dict] = {}
    for cid in ids:
        mains = {}
        for sc in SCENARIOS:
            mains[sc] = interval_metrics(sc, cid, y1, y2, pop, fixed, flows)
        prim = mains[PRIMARY_SC]
        mors = [m["mor"] for m in mains.values() if m]
        mor_lo, mor_hi = (min(mors), max(mors)) if mors else (None, None)
        # admin-рамка
        ab1 = admin_built.get((cid, str(y1)))
        ab2 = admin_built.get((cid, str(y2)))
        mor_admin = None
        if prim and ab1 and ab2:
            b1a, b2a = float(ab1["built_admin_m2"]), float(ab2["built_admin_m2"])
            if b1a > 0 and b2a > 0:
                mor_admin = g_rate(b1a, b2a, dt_main) - prim["pgr"]
        # MDC
        b2020 = fixed.get((PRIMARY_SC, cid, 2020), {}).get("built", 0.0)
        rel = rel_err_for(b2020)
        mdc_mor = math.sqrt(2) * rel / dt_main
        mdc_b = mdc_mor
        # обратная интерполяция: фонд к переписным датам 1989/2019
        alt = None
        if prim:
            b89 = built_at(fixed, PRIMARY_SC, cid, 1989)
            b19 = built_at(fixed, PRIMARY_SC, cid, 2019)
            p89 = pop[cid].get(1989)
            p19 = pop[cid].get(2019)
            if b89 and b19 and p89 and p19:
                alt = (g_rate(b89, b19, 30) or 0) - (g_rate(p89[0], p19[0], 30) or 0)
        time_sensitive = (alt is not None and prim is not None
                          and (alt > 0) != (prim["mor"] > 0))
        # типы по сценариям -> agreement
        merged2020 = dyn.get((PRIMARY_SC, cid, 2020), {}).get("merged", "")
        t6_flag = False
        if merged2020 and prim:
            for other in merged2020.split("|"):
                mo = interval_metrics(PRIMARY_SC, other, y1, y2,
                                      pop, fixed, flows)
                if mo and mo["pgr"] > PGR_EPS and prim["pgr"] < -PGR_EPS:
                    pk_self = int(byid[cid]["population_peak_value"])
                    pk_other = int(byid[other]["population_peak_value"])
                    if pk_self > pk_other:
                        t6_flag = True
        # типы по сценариям: метрики - сценарные, устойчивость знака MOR -
        # ГЛОБАЛЬНАЯ (общие mor_lo/mor_hi + MDC), чтобы agreement сравнивал
        # содержательные ветви, а не вырожденные локальные интервалы
        types = {}
        for sc in SCENARIOS:
            m = mains[sc]
            types[sc] = classify(m, mdc_b, mor_lo or 0, mor_hi or 0,
                                 mdc_mor, t6_flag) if m else "TX"
        primary_type = classify(prim, mdc_b, mor_lo or 0, mor_hi or 0,
                                mdc_mor, t6_flag)
        same = sum(1 for sc in SCENARIOS if types[sc] == types[PRIMARY_SC])
        agreement = same / len(SCENARIOS)
        robust_sign = (prim is not None and mor_lo is not None
                       and ((mor_lo > 0 and mor_hi > 0)
                            or (mor_lo < 0 and mor_hi < 0))
                       and abs(prim["mor"]) > mdc_mor)
        seeds_ok = all(dyn.get((sc, cid, e), {}).get("seed", 0) == 1
                       for sc in SCENARIOS for e in (y1, y2))
        per_city[cid] = {
            "main": prim, "mains": mains, "mor_lo": mor_lo, "mor_hi": mor_hi,
            "mor_admin": mor_admin, "mdc_mor": mdc_mor,
            "robust_sign": robust_sign, "agreement": agreement,
            "primary_type": primary_type, "types": types,
            "time_sensitive": time_sensitive, "merged": merged2020,
            "seeds_ok": seeds_ok, "rel_err": rel,
        }

    # --- классы качества
    for cid in ids:
        pc = per_city[cid]
        cls = "A"
        reasons = []
        prim = pc["main"]
        if prim is None:
            cls = "C"
            reasons.append("нет метрик главного интервала")
        else:
            if "interpolated" in prim["pop_status"]:
                pass  # 1990/2020 всегда интерполяция между 1989/1991 и 2019/2021
            missing_bench = [y for y in (1970, 1979, 1989, 1999, 2009, 2019)
                             if y not in pop[cid]]
            if missing_bench:
                cls = "C"
                reasons.append(f"нет опорных точек {missing_bench}")
            if not pc["seeds_ok"]:
                cls = "C" if cls == "C" else "B"
                reasons.append("seed теряется в части сценариев")
            if pc["merged"]:
                cls = "C" if cls == "C" else "B"
                reasons.append(f"слившийся контур: {pc['merged']}")
            if pc["agreement"] < AGREEMENT_MIN:
                cls = "C" if cls in ("B", "C") else "B"
                reasons.append("тип чувствителен к границе")
        pc["quality"] = cls
        pc["quality_reasons"] = "; ".join(reasons)

    # --- световые метрики (VNL 2012-2024, ядро/край)
    early_y, late_y = [2012, 2013, 2014], [2022, 2023, 2024]
    for cid in ids:
        pc = per_city[cid]
        r_e = light_window_mean(light, "vnl", early_y, cid, "total")
        r_l = light_window_mean(light, "vnl", late_y, cid, "total")
        rn_e = light_window_mean(light, "vnl", early_y, "__national__", "total")
        rn_l = light_window_mean(light, "vnl", late_y, "__national__", "total")
        b13 = built_at(fixed, PRIMARY_SC, cid, 2013)
        b20 = built_at(fixed, PRIMARY_SC, cid, 2020)
        sug = sug_share = None
        if r_e and r_l and b13 and b20:
            g_r = g_rate(r_e, r_l, 10)          # свет: центры окон 2013->2023
            g_b = g_rate(b13, b20, 7)           # фонд: наблюдаемые 2013->2020
            if g_r is not None and g_b is not None:
                sug = g_b - g_r
            if rn_e and rn_l:
                g_rs = g_rate(r_e / rn_e, r_l / rn_l, 10)
                if g_rs is not None and g_b is not None:
                    sug_share = g_b - g_rs
        # ядро/край
        rc_e = light_window_mean(light, "vnl", early_y, cid, "core")
        rc_l = light_window_mean(light, "vnl", late_y, cid, "core")
        re_e = light_window_mean(light, "vnl", early_y, cid, "edge")
        re_l = light_window_mean(light, "vnl", late_y, cid, "edge")
        ihs = ceur_e = ceur_l = None
        ce13 = core_edge_at(fixed, PRIMARY_SC, cid, 2013)
        ce23 = core_edge_at(fixed, PRIMARY_SC, cid, 2023)
        if (None not in (rc_e, rc_l, re_e, re_l) and ce13 and ce23
                and min(ce13[0], ce23[0], ce13[1], ce23[1]) >= MIN_ZONE_M2):
            u_core_e = (rc_e + EPS_R) / (ce13[0] + EPS_B)
            u_edge_e = (re_e + EPS_R) / (ce13[1] + EPS_B)
            u_core_l = (rc_l + EPS_R) / (ce23[0] + EPS_B)
            u_edge_l = (re_l + EPS_R) / (ce23[1] + EPS_B)
            ceur_e = u_core_e / u_edge_e
            ceur_l = u_core_l / u_edge_l
            ihs = -(math.log(ceur_l) - math.log(ceur_e))
        ubi = (r_l / built_at(fixed, PRIMARY_SC, cid, 2023)
               if r_l and built_at(fixed, PRIMARY_SC, cid, 2023) else None)
        pc["light"] = {
            "sug": sug, "sug_share": sug_share, "ihs": ihs,
            "ceur_early": ceur_e, "ceur_late": ceur_l, "ubi_2023": ubi,
            "r_early": r_e, "r_late": r_l,
        }

    # --- дороги и POI (современный срез)
    for cid in ids:
        pc = per_city[cid]
        p_now, _ = pop_at(pop[cid], 2026)
        b2020 = fixed.get((PRIMARY_SC, cid, 2020), {}).get("built")
        rd = {}
        for grp in ("major", "local"):
            r = roads.get((cid, grp))
            rd[grp] = float(r["length_km"]) if r else None
        rd["all"] = (rd["major"] + rd["local"]
                     if None not in (rd["major"], rd["local"]) else None)
        pc["roads"] = {
            "km": rd,
            "per_1000": {k: (v / (p_now / 1000)
                             if v is not None and p_now else None)
                         for k, v in rd.items()},
            "per_built_km2": {k: (v / (b2020 / 1e6)
                                  if v is not None and b2020 else None)
                              for k, v in rd.items()},
        }
        cats = {}
        for cat in ("grocery", "pharmacy", "primary_care", "school",
                    "kindergarten", "transport_stop", "admin_service",
                    "emergency"):
            r = poi.get((cid, cat))
            cnt = int(r["count"]) if r else None
            cats[cat] = {
                "count": cnt,
                "per_10k": (cnt / (p_now / 10_000)
                            if cnt is not None and p_now else None),
            }
        pc["poi"] = cats
        pc["pop_now"] = p_now

    # --- matching (H-1)
    def feat(cid: str) -> list[float] | None:
        p90, _ = pop_at(pop[cid], 1990)
        f90 = fixed.get((PRIMARY_SC, cid, 1990))
        d90 = dyn.get((PRIMARY_SC, cid, 1990))
        if not p90 or not f90 or not d90 or d90["cells"] == 0:
            return None
        c = byid[cid]
        dist_minsk = haversine(float(c["lat"]), float(c["lon"]),
                               53.902246, 27.561837)
        return [math.log(p90), f90["built"] / p90,
                p90 / (d90["cells"] / 100.0),
                math.log(1 + dist_minsk)]

    feats = {cid: feat(cid) for cid in ids}
    valid = [cid for cid in ids if feats[cid] and per_city[cid]["main"]]
    means, sds = [], []
    for k in range(4):
        vals = [feats[c][k] for c in valid]
        mu = sum(vals) / len(vals)
        sd = math.sqrt(sum((v - mu) ** 2 for v in vals) / len(vals)) or 1.0
        means.append(mu)
        sds.append(sd)

    def z(cid):
        return [(feats[cid][k] - means[k]) / sds[k] for k in range(4)]

    treated = [c for c in valid if per_city[c]["main"]["pgr"] < TREAT_PGR
               and per_city[c]["quality"] in ("A", "B")]
    controls = [c for c in valid if per_city[c]["main"]["pgr"] > CONTROL_PGR
                and per_city[c]["quality"] in ("A", "B")]
    pairs = []
    for t in sorted(treated):
        zt = z(t)
        p90t = feats[t][0]
        best, best_d = None, None
        for c in controls:
            if abs(feats[c][0] - p90t) > CALIPER_LNPOP:
                continue
            zc = z(c)
            d = math.sqrt(sum((zt[k] - zc[k]) ** 2 for k in range(4)))
            if best_d is None or d < best_d:
                best, best_d = c, d
        if best:
            pairs.append({
                "treated": t, "control": best,
                "distance": round(best_d, 3),
                "mor_treated": per_city[t]["main"]["mor"],
                "mor_control": per_city[best]["main"]["mor"],
            })

    # баланс пар: стандартизованная разность средних (SMD) до/после подбора
    feat_names = ["ln_pop_1990", "built_pc_1990", "density_1990",
                  "ln_dist_minsk"]
    matched_t = [p["treated"] for p in pairs]
    matched_c = [p["control"] for p in pairs]   # с возвращением

    def smd(group_a: list[str], group_b: list[str], k: int) -> float | None:
        if not group_a or not group_b:
            return None
        za = [z(c)[k] for c in group_a]
        zb = [z(c)[k] for c in group_b]
        return (sum(za) / len(za)) - (sum(zb) / len(zb))

    balance = {}
    for k, name in enumerate(feat_names):
        balance[name] = {
            "smd_before": rnd(smd(treated, controls, k), 3),
            "smd_after": rnd(smd(matched_t, matched_c, k), 3),
        }

    # двусторонний знаковый тест разрыва MOR в парах (биномиальный, p=0.5)
    gaps = [p["mor_treated"] - p["mor_control"] for p in pairs]
    n_pos = sum(1 for g in gaps if g > 0)
    n_eff = sum(1 for g in gaps if g != 0)
    sign_p = None
    if n_eff:
        k_ext = max(n_pos, n_eff - n_pos)
        tail = sum(math.comb(n_eff, j) for j in range(k_ext, n_eff + 1))
        sign_p = min(1.0, 2 * tail / (2 ** n_eff))

    # --- сводки: национальная панель = только классы A/B (ТЗ §4.3: класс C -
    # карточка и приложение, в рейтинги и заголовки не входит)
    panel = [c for c in valid if per_city[c]["quality"] in ("A", "B")]
    declining = [c for c in panel if per_city[c]["main"]["pgr"] < -PGR_EPS]
    growing = [c for c in panel if per_city[c]["main"]["pgr"] > PGR_EPS]
    stable = [c for c in panel if c not in declining and c not in growing]
    med = lambda xs: (sorted(xs)[len(xs) // 2]
                      if len(xs) % 2 else
                      sum(sorted(xs)[len(xs) // 2 - 1:len(xs) // 2 + 1]) / 2) \
        if xs else None
    mor_declining = [per_city[c]["main"]["mor"] for c in declining]
    overhang_pos = [c for c in declining
                    if per_city[c]["main"]["mor"] > 0
                    and per_city[c]["robust_sign"]]
    type_counts = defaultdict(int)
    for c in panel:
        type_counts[per_city[c]["primary_type"]] += 1
    pop_now_total = sum(per_city[c]["pop_now"] or 0 for c in panel)
    pop_in_overhang = sum(per_city[c]["pop_now"] or 0 for c in overhang_pos)

    national = {
        "n_cities": len(panel),
        "n_quality_c": len(valid) - len(panel),
        "n_declining": len(declining),
        "n_growing": len(growing),
        "n_stable": len(stable),
        "median_mor_declining": med(mor_declining),
        "median_mor_growing": med([per_city[c]["main"]["mor"]
                                   for c in growing]),
        "n_overhang_robust": len(overhang_pos),
        "share_declining_with_overhang":
            len(overhang_pos) / len(declining) if declining else None,
        "type_counts": dict(sorted(type_counts.items())),
        "pop_share_in_overhang":
            pop_in_overhang / pop_now_total if pop_now_total else None,
        "median_bpc_1990": med([per_city[c]["main"]["b1"] /
                                per_city[c]["main"]["p1"] for c in panel]),
        "median_bpc_2020": med([per_city[c]["main"]["b2"] /
                                per_city[c]["main"]["p2"] for c in panel]),
        "matching": {
            "n_pairs": len(pairs),
            "median_mor_gap": med(gaps),
            "sign_test_p": rnd(sign_p, 4),
            "n_gap_positive": n_pos,
            "balance": balance,
        },
    }

    return {
        "cities": per_city, "ids": ids, "byid": byid, "pop": pop,
        "dyn": dyn, "fixed": fixed, "flows": flows, "light": light,
        "pairs": pairs, "national": national, "mono": mono,
        "admin_areas": admin_areas,
    }


def haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ------------------------------------------------------------ выборка кейсов

def select_cases(ctx: dict) -> list[dict]:
    """Детерминированный алгоритм выбора сюжетов (пререгистрация §11.4)."""
    pc = ctx["cities"]
    byid = ctx["byid"]
    mono = ctx["mono"]
    used: set[str] = set()
    cases = []

    def ok(c, need_quality=("A", "B")):
        return (c not in used and pc[c]["main"]
                and pc[c]["quality"] in need_quality)

    ids = [c for c in ctx["ids"] if pc[c]["main"]]

    # 1. Спутник Минска: <40 км, растёт
    cand = [c for c in ids if ok(c)
            and haversine(float(byid[c]["lat"]), float(byid[c]["lon"]),
                          53.902246, 27.561837) < 40
            and pc[c]["main"]["pgr"] > PGR_EPS and c != "c-minsk"]
    if cand:
        c = max(cand, key=lambda x: pc[x]["main"]["pgr"])
        cases.append({"role": "satellite", "city_id": c})
        used.add(c)

    # 2. Промышленный моногород (INF-06 high) с выраженным навесом
    cand = [c for c in ids if ok(c) and mono.get(c) == "high"
            and pc[c]["main"]["pgr"] < -PGR_EPS]
    if cand:
        c = max(cand, key=lambda x: pc[x]["main"]["mor"])
        cases.append({"role": "monotown", "city_id": c})
        used.add(c)

    # 3. Малый райцентр (население 2020 10-25 тыс., сокращается)
    cand = [c for c in ids if ok(c)
            and 10_000 <= (pc[c]["main"]["p2"] or 0) <= 25_000
            and pc[c]["main"]["pgr"] < -PGR_EPS
            and "raionCenter" in byid[c]["flags"]]
    if cand:
        c = max(cand, key=lambda x: pc[x]["main"]["mor"])
        cases.append({"role": "small_center", "city_id": c})
        used.add(c)

    # 4. Северо-восток: Витебская/Могилёвская, макс потеря населения
    cand = [c for c in ids if ok(c)
            and byid[c]["parent_region_id"] in ("BY-VI", "BY-MA")
            and pc[c]["main"]["pgr"] < -PGR_EPS]
    if cand:
        c = min(cand, key=lambda x: pc[x]["main"]["pgr"])
        cases.append({"role": "northeast", "city_id": c})
        used.add(c)

    # 5. Кластер: устойчиво слившиеся контуры
    cand = [c for c in ids if ok(c, ("A", "B", "C")) and pc[c]["merged"]]
    if cand:
        c = max(cand, key=lambda x: pc[x]["main"]["p2"] or 0)
        cases.append({"role": "cluster", "city_id": c,
                      "cluster_with": pc[c]["merged"]})
        used.add(c)

    # 6. Контрпример: сокращается, но навес НЕ положителен/не устойчив.
    # Если строгого контрпримера в данных нет (само по себе результат) -
    # берём слабейший навес среди сокращающихся и помечаем это явно.
    cand = [c for c in ids if ok(c)
            and pc[c]["main"]["pgr"] < -PGR_EPS
            and (pc[c]["main"]["mor"] <= 0 or not pc[c]["robust_sign"])]
    strict = bool(cand)
    if not cand:
        cand = [c for c in ids if ok(c) and pc[c]["main"]["pgr"] < -PGR_EPS]
    if cand:
        c = min(cand, key=lambda x: pc[x]["main"]["mor"])
        cases.append({"role": "counterexample", "city_id": c,
                      "strict": strict})
        used.add(c)

    return cases


# ------------------------------------------------------------------ экспорт

def rnd(x, nd=4):
    return None if x is None else round(x, nd)


def export(ctx: dict) -> None:
    FINAL.mkdir(parents=True, exist_ok=True)
    pc = ctx["cities"]
    byid = ctx["byid"]
    pop = ctx["pop"]
    fixed, dyn, flows = ctx["fixed"], ctx["dyn"], ctx["flows"]
    light = ctx["light"]
    cases = select_cases(ctx)

    # -- city_metrics.csv (основной сценарий)
    rows = []
    for cid in ctx["ids"]:
        for e in EPOCHS:
            p, st = pop_at(pop[cid], e)
            fx = fixed.get((PRIMARY_SC, cid, e))
            dn = dyn.get((PRIMARY_SC, cid, e))
            if not fx or not dn:
                continue
            fp_km2 = dn["cells"] / 100.0
            per_m = dn["perimeter"] * 100.0
            rows.append({
                "city_id": cid, "year": e, "frame_id": "MORPH_FIXED_FRAME",
                "population": rnd(p, 1), "population_status": st,
                "built_surface_m2": rnd(fx["built"], 1),
                "built_core_m2": rnd(fx["core"], 1),
                "built_edge_m2": rnd(fx["edge"], 1),
                "footprint_area_km2": rnd(fp_km2, 4),
                "built_surface_pc_m2": rnd(fx["built"] / p, 2) if p else None,
                "morph_population_density": rnd(p / fp_km2, 1)
                    if p and fp_km2 else None,
                "built_coverage_ratio": rnd(
                    dn["built"] / (dn["cells"] * 10_000), 4)
                    if dn["cells"] else None,
                "compactness": rnd(4 * math.pi * (dn["cells"] * 10_000)
                                   / (per_m ** 2), 4) if per_m else None,
                "seed_found": dn["seed"],
                "quality_class": pc[cid]["quality"],
            })
    with (FINAL / "city_metrics.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # -- city_interval_metrics.csv
    irows = []
    for cid in ctx["ids"]:
        for (a, b) in CHART_INTERVALS:
            m = interval_metrics(PRIMARY_SC, cid, a, b, pop, fixed, flows)
            if not m:
                continue
            main = (a, b) == MAIN_INTERVAL
            irows.append({
                "city_id": cid, "year_start": a, "year_end": b,
                "frame_id": "MORPH_FIXED_FRAME",
                "pgr_annual": rnd(m["pgr"], 5),
                "bgr_annual": rnd(m["bgr"], 5),
                "material_overhang_rate_annual": rnd(m["mor"], 5),
                "edge_expansion_share": rnd(m["ees"], 4),
                "infill_share": rnd(1 - m["ees"], 4)
                    if m["ees"] is not None else None,
                "lower_bound": rnd(pc[cid]["mor_lo"], 5) if main else "",
                "upper_bound": rnd(pc[cid]["mor_hi"], 5) if main else "",
                "minimum_detectable_change":
                    rnd(pc[cid]["mdc_mor"], 5) if main else "",
                "robust_sign": int(pc[cid]["robust_sign"]) if main else "",
                "mor_admin_frame": rnd(pc[cid]["mor_admin"], 5)
                    if main else "",
                "time_alignment_sensitive":
                    int(pc[cid]["time_sensitive"]) if main else "",
                "stock_use_gap_annual": rnd(pc[cid]["light"]["sug"], 5)
                    if main else "",
                "inner_hollowing_shift": rnd(pc[cid]["light"]["ihs"], 5)
                    if main else "",
            })
    with (FINAL / "city_interval_metrics.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(irows[0].keys()))
        w.writeheader()
        w.writerows(irows)

    # -- city_typology.csv
    trows = []
    for cid in ctx["ids"]:
        alt_types = sorted({t for t in pc[cid]["types"].values()
                            if t != pc[cid]["primary_type"]})
        trows.append({
            "city_id": cid, "period": f"{MAIN_INTERVAL[0]}-{MAIN_INTERVAL[1]}",
            "primary_type": pc[cid]["primary_type"],
            "agreement_score": rnd(pc[cid]["agreement"], 3),
            "alternative_types": "|".join(alt_types),
            "boundary_sensitive": int(pc[cid]["agreement"] < AGREEMENT_MIN),
            "time_sensitive": int(pc[cid]["time_sensitive"]),
            "quality_class": pc[cid]["quality"],
            "quality_reasons": pc[cid]["quality_reasons"],
        })
    with (FINAL / "city_typology.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(trows[0].keys()))
        w.writeheader()
        w.writerows(trows)

    # -- story JSON
    story_cities = {}
    for cid in ctx["ids"]:
        c = byid[cid]
        m = pc[cid]["main"]
        series = []
        for e in EPOCHS:
            p, st = pop_at(pop[cid], e)
            fx = fixed.get((PRIMARY_SC, cid, e))
            dn = dyn.get((PRIMARY_SC, cid, e))
            if not fx:
                continue
            series.append({
                "year": e,
                "pop": rnd(p, 0), "popStatus": st,
                "built": rnd(fx["built"] / 1e6, 3),      # км²
                "builtCore": rnd(fx["core"] / 1e6, 3),
                "builtEdge": rnd(fx["edge"] / 1e6, 3),
                "footprint": rnd(dn["cells"] / 100.0, 2) if dn else None,
                "bpc": rnd(fx["built"] / p, 1) if p else None,
            })
        vnl = []
        for yr in range(2012, 2025):
            rec = light.get(("vnl", yr, cid))
            nat = light.get(("vnl", yr, "__national__"))
            if rec and rec["total"] is not None:
                vnl.append({
                    "year": yr,
                    "total": rnd(rec["total"], 1),
                    "core": rnd(rec["core"], 1),
                    "edge": rnd(rec["edge"], 1),
                    "share": rnd(rec["total"] / nat["total"], 6)
                        if nat and nat["total"] else None,
                })
        story_cities[cid] = {
            "id": cid, "ru": c["name_ru"], "be": c["name_be"],
            "region": c["parent_region_id"],
            "lat": float(c["lat"]), "lon": float(c["lon"]),
            "flags": c["flags"].split("|") if c["flags"] else [],
            "quality": pc[cid]["quality"],
            "qualityReasons": pc[cid]["quality_reasons"],
            "type": pc[cid]["primary_type"],
            "agreement": rnd(pc[cid]["agreement"], 3),
            "merged": pc[cid]["merged"] or None,
            "series": series,
            "vnl": vnl,
            "main": None if not m else {
                "pgr": rnd(m["pgr"], 5), "bgr": rnd(m["bgr"], 5),
                "mor": rnd(m["mor"], 5),
                "morLo": rnd(pc[cid]["mor_lo"], 5),
                "morHi": rnd(pc[cid]["mor_hi"], 5),
                "morAdmin": rnd(pc[cid]["mor_admin"], 5),
                "mdc": rnd(pc[cid]["mdc_mor"], 5),
                "robust": pc[cid]["robust_sign"],
                "timeSensitive": pc[cid]["time_sensitive"],
                "ees": rnd(m["ees"], 4),
                "p1990": rnd(m["p1"], 0), "p2020": rnd(m["p2"], 0),
                "b1990": rnd(m["b1"] / 1e6, 3), "b2020": rnd(m["b2"] / 1e6, 3),
                "bpc1990": rnd(m["b1"] / m["p1"], 1),
                "bpc2020": rnd(m["b2"] / m["p2"], 1),
            },
            "lightMetrics": {k: rnd(v, 5) for k, v
                             in pc[cid]["light"].items()
                             if k in ("sug", "sug_share", "ihs", "ubi_2023")},
            "roads": {
                "per1000": {k: rnd(v, 2) for k, v
                            in pc[cid]["roads"]["per_1000"].items()},
                "km": {k: rnd(v, 1) for k, v
                       in pc[cid]["roads"]["km"].items()},
            },
            "poi": {cat: {"count": d["count"],
                          "per10k": rnd(d["per_10k"], 2)}
                    for cat, d in pc[cid]["poi"].items()},
            "popNow": rnd(pc[cid]["pop_now"], 0),
        }

    national = ctx["national"]
    story = {
        "research_id": "INF-12",
        "version": VERSION,
        "data_cutoff": "2026-07-16",
        "mainInterval": list(MAIN_INTERVAL),
        "epochs": EPOCHS,
        "national": {k: (rnd(v, 5) if isinstance(v, float) else v)
                     for k, v in national.items()},
        "cases": cases,
        "pairs": ctx["pairs"][:40],
        "cities": story_cities,
    }
    story_path = (FINAL / "story.json") if PKG is not None \
        else (OUT / "urban_overhang.json")
    story_path.write_text(
        json.dumps(story, ensure_ascii=False, separators=(",", ":")))

    # -- computed_results.json: плоский список метрик (формат стандарта
    # пакетов: [{metric, value}]; строки-кейсы фиксируются инвариантами)
    metrics = [
        ("n_cities", national["n_cities"]),
        ("n_declining", national["n_declining"]),
        ("n_growing", national["n_growing"]),
        ("n_overhang_robust", national["n_overhang_robust"]),
        ("share_declining_with_overhang",
         rnd(national["share_declining_with_overhang"], 4)),
        ("median_mor_declining", rnd(national["median_mor_declining"], 5)),
        ("median_bpc_1990", rnd(national["median_bpc_1990"], 2)),
        ("median_bpc_2020", rnd(national["median_bpc_2020"], 2)),
        ("matching_pairs", national["matching"]["n_pairs"]),
        ("matching_median_mor_gap",
         rnd(national["matching"]["median_mor_gap"], 5)),
        ("matching_sign_test_p", rnd(national["matching"]["sign_test_p"], 4)),
        ("median_mor_growing", rnd(national["median_mor_growing"], 5)),
        ("pop_share_in_overhang", rnd(national["pop_share_in_overhang"], 4)),
    ]
    for t in ("T1", "T2", "T3", "T4", "T5", "T6", "TX"):
        metrics.append((f"type_counts.{t}",
                        national["type_counts"].get(t, 0)))
    computed = [{"metric": k, "value": v} for k, v in metrics]
    (FINAL / "computed_results.json").write_text(
        json.dumps(computed, ensure_ascii=False, indent=1))
    print(json.dumps({"cases": {c["role"]: c["city_id"] for c in cases},
                      **{k: v for k, v in metrics}},
                     ensure_ascii=False, indent=1))


def main() -> None:
    ctx = build()
    export(ctx)


if __name__ == "__main__":
    main()
