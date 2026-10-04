"""INF-22 `sensors`: «Второй сенсор» — сходятся ли три измерения населения.

Вопрос: показывают ли официальная статистика, спутниковая модель расселения
GHS-POP и ночные огни одну и ту же географию убывания населения по 118 районам
Беларуси — и устроено ли расхождение систематически.

Пререгистрация (заморожена до расчётов): `docs/preregistration/sensors-v0.1.md`.
Гипотезы H1-H4, окна, гейты V-1…V-7 и ограничения — там; здесь только счёт.

Все сравнения — по ДОЛЯМ района в национальном итоге того же датчика: GHS-POP
распределяет общий национальный итог по застройке, свет зависит от калибровки
сенсора; доли гасят общий уровень обоих эффектов (раздел 5 пререгистрации).

Данные (всё завендорено, сеть не нужна):
  data/raw/grid/reconciliation.csv      official и сырой GHS-POP по эпохам (INF-15)
  web/public/data/data.json             годовой официальный ряд, названия RU/BE
  web/public/data/nightlights_v2.json   доли зон в национальном свете (INF-08)
  data/raw/nightlights/zonal_vnl.csv    сырые радиансы VIIRS — только для сверки
  data/curated/travel_times.csv         время в пути до облцентра (INF-04)

Запуск: python -m etl.sensors -> web/public/data/sensors.json
                                 data/curated/sensors.csv
"""
from __future__ import annotations

import csv
import json
import math

from .common import ROOT, OUT

CURATED = ROOT / "data" / "curated"
VERSION = "1.0.0"

MINSK = "BY-HM"
EPOCHS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020]

# окна заморожены в пререгистрации (раздел 5, пункт 4)
WIN_OG = (1990, 2020)            # H1, H3
WIN_OG_ROBUST = (2000, 2020)     # робастность H1
WIN_L_PRE = (2013, 2019)         # H2, H4 (до смены обработки VNL)
WIN_L_POST = (2021, 2024)        # H4 (после смены обработки VNL)
WIN_L_DMSP = (1992, 2011)        # робастность H2, внутри одного сенсора
# запрещённые стыки огней (пункт 5): сравнение не может их пересекать
LIGHT_SEAMS = [(2011, 2012), (2020, 2021)]

H1_RHO, H2_RHO, H3_RHO, H4_RATIO = 0.60, 0.40, 0.25, 1.25


# ------------------------------------------------------------- статистика
# Малые функции намеренно локальные: пакет sensors автономен.

def _ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """ρ Спирмена со средними рангами при связках; p — нормальное
    приближение z = |ρ|·√(n−1), двустороннее."""
    n = len(xs)
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    vy = math.sqrt(sum((b - my) ** 2 for b in ry))
    rho = cov / (vx * vy) if vx and vy else 0.0
    z = abs(rho) * math.sqrt(n - 1)
    p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2.0))))
    return rho, p


def median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def shares(values: dict[str, float]) -> dict[str, float]:
    tot = sum(values.values())
    return {k: v / tot for k, v in values.items()}


def dlog(s0: float, s1: float) -> float:
    return math.log(s1 / s0)


def crosses_seam(window: tuple[int, int]) -> bool:
    a, b = window
    return any(a <= lo and hi <= b for lo, hi in LIGHT_SEAMS)


# ---------------------------------------------------------------- загрузка

def load_reconciliation() -> tuple[dict, dict]:
    """official[t][zone], ghs[t][zone] по эпохам GHS."""
    off: dict[int, dict[str, float]] = {}
    ghs: dict[int, dict[str, float]] = {}
    with open(ROOT / "data" / "raw" / "grid" / "reconciliation.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = int(r["epoch"])
            # пустой official — Дрибинский район до 1991 (поправка 1):
            # INF-15 не экстраполирует официальный ряд за его пределы
            if r["official"]:
                off.setdefault(t, {})[r["raion"]] = float(r["official"])
            ghs.setdefault(t, {})[r["raion"]] = float(r["grid_sum"])
    return off, ghs


def load_light_shares() -> dict[int, dict[str, float]]:
    """Доли INF-08 (`lshare`), перенормированные к сумме 1 по 119 зонам:
    в JSON они округлены до 5 знаков, и сумма отличается от 1 на ошибку
    округления — перенормировка делает V-1 проверкой этого расчёта."""
    d = json.loads((OUT / "nightlights_v2.json").read_text())
    raw: dict[int, dict[str, float]] = {}
    for row in d["rows"]:
        for y, v in row["lshare"].items():
            if v is not None:
                raw.setdefault(int(y), {})[row["id"]] = float(v)
    return {y: shares(z) for y, z in raw.items()}


def load_vnl_raw_shares() -> dict[int, dict[str, float]]:
    """Доли из сырых радиансов VIIRS — сверка с перенормированными lshare."""
    raw: dict[int, dict[str, float]] = {}
    with open(ROOT / "data" / "raw" / "nightlights" / "zonal_vnl.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            z = r["zone_id"]
            if z.startswith("r-") or z == MINSK:
                raw.setdefault(int(r["year"]), {})[z] = float(r["radiance"])
    return {y: shares(z) for y, z in raw.items()}


def load_official_annual(T: dict) -> dict[int, dict[str, float]]:
    out: dict[int, dict[str, float]] = {}
    for tid, v in T.items():
        if v["level"] == "raion" or tid == MINSK:
            for y, rec in v["pop"].items():
                out.setdefault(int(y), {})[tid] = float(rec[0])
    return out


# ------------------------------------------------------------------- расчёт

def build() -> dict:
    data = json.loads((OUT / "data.json").read_text())
    T = data["territories"]
    off_e, ghs_e = load_reconciliation()
    light = load_light_shares()
    vnl_raw = load_vnl_raw_shares()
    off_y = load_official_annual(T)
    travel = {}
    with open(CURATED / "travel_times.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            travel[r["territory_id"]] = {
                "oblcenter": float(r["min_oblcenter"]) if r.get("min_oblcenter") else None,
                "minsk": float(r["min_minsk"]) if r.get("min_minsk") else None,
            }

    raions = sorted(z for z in off_e[2020] if z.startswith("r-"))
    zones = raions + [MINSK]
    gates: dict[str, dict] = {}

    # --- набор зон для окна O/G: районы с официальным значением на обоих
    # концах окна + Минск; доли ОБОИХ датчиков — по этому набору (поправка 1)
    def og_zones(w: tuple[int, int]) -> list[str]:
        return [z for z in zones if all(z in off_e[t] for t in w)]

    zones_og = og_zones(WIN_OG)
    zones_og_r = og_zones(WIN_OG_ROBUST)

    # --- V-5: покрытие по каждому окну -----------------------------------
    missing_og = sorted(set(zones) - set(zones_og))
    cover_light = {y: sorted(set(zones) - set(light.get(y, {})))
                   for y in (*WIN_L_PRE, *WIN_L_POST, *WIN_L_DMSP)}
    cover_off_y = {y: sorted(set(zones) - set(off_y.get(y, {})))
                   for y in (*WIN_L_PRE, *WIN_L_POST)}
    gates["V-5"] = {
        "n_raions": len(raions),
        "og_1990_2020_missing": missing_og,
        "og_2000_2020_missing": sorted(set(zones) - set(zones_og_r)),
        "ghs_missing": sorted(set(zones) - set(ghs_e[2020])),
        "light_missing": {str(k): v for k, v in cover_light.items() if v},
        "official_annual_missing": {str(k): v for k, v in cover_off_y.items() if v},
        "amendment": "поправка 1: окна O/G 1990-2020 — без Дрибинского района",
        "pass": (len(raions) == 118 and missing_og == ["r-drybinski"]
                 and set(zones) == set(zones_og_r) and set(zones) <= set(ghs_e[2020])
                 and not any(cover_light.values()) and not any(cover_off_y.values())),
    }

    # --- доли --------------------------------------------------------
    # для графиков: доля на каждую эпоху по зонам, где есть значение
    sO = {t: shares({z: off_e[t][z] for z in zones if z in off_e[t]}) for t in EPOCHS}
    sG = {t: shares({z: ghs_e[t][z] for z in zones}) for t in EPOCHS}
    # для тестов окон — согласованный набор зон на обоих концах
    def win_shares(src, w, zs):
        return {t: shares({z: src[t][z] for z in zs}) for t in w}
    sO_og, sG_og = win_shares(off_e, WIN_OG, zones_og), win_shares(ghs_e, WIN_OG, zones_og)
    sO_ogr = win_shares(off_e, WIN_OG_ROBUST, zones_og_r)
    sG_ogr = win_shares(ghs_e, WIN_OG_ROBUST, zones_og_r)
    sL = {y: {z: light[y][z] for z in zones} for y in light}
    sOy = {y: shares({z: off_y[y][z] for z in zones})
           for y in off_y if all(z in off_y[y] for z in zones)}

    # --- V-1: доли суммируются в 1 --------------------------------------
    worst = max(abs(sum(s.values()) - 1.0)
                for group in (sO, sG, sOy, sO_og, sG_og, sO_ogr, sG_ogr)
                for s in group.values())
    worst = max(worst, max(abs(sum(s.values()) - 1.0) for s in sL.values()))
    gates["V-1"] = {"max_abs_dev": worst, "pass": worst < 1e-9}

    # --- V-2: официальное значение 2020 = интерполяция 2019 -> 2021 ------
    v2 = []
    for z in zones:
        p19, p21 = off_y[2019][z], off_y[2021][z]
        exp = p19 + (p21 - p19) * 0.5
        v2.append(abs(off_e[2020][z] - exp) / exp * 100)
    gates["V-2"] = {"max_pct": round(max(v2), 4), "pass": max(v2) <= 0.1}

    # --- V-3: окна огней не пересекают стыки -----------------------------
    light_windows = {"H2": WIN_L_PRE, "H4_pre": WIN_L_PRE, "H4_post": WIN_L_POST,
                     "robust_dmsp": WIN_L_DMSP}
    gates["V-3"] = {"windows": {k: list(v) for k, v in light_windows.items()},
                    "seams": [list(s) for s in LIGHT_SEAMS],
                    "pass": not any(crosses_seam(w) for w in light_windows.values())}
    if not gates["V-3"]["pass"]:
        raise SystemExit("V-3: окно огней пересекает стык сенсоров — запрещено")

    # --- V-4: стабильность сенсора огней ---------------------------------
    r1819, _ = spearman([sL[2018][z] for z in raions], [sL[2019][z] for z in raions])
    gates["V-4"] = {"rho_2018_2019": round(r1819, 4), "pass": r1819 >= 0.95}

    # сверка перенормированных lshare с сырыми радиансами VIIRS
    vnl_check = {}
    for y in (2013, 2019, 2021, 2024):
        dev = max(abs(sL[y][z] / vnl_raw[y][z] - 1.0) for z in zones if vnl_raw[y][z] > 0)
        vnl_check[str(y)] = round(dev * 100, 3)

    # --- изменения долей по районам --------------------------------------
    def d_ep(s, w, z):
        return dlog(s[w[0]][z], s[w[1]][z]) if z in s[w[0]] else None

    rows = {}
    for z in raions:
        dO = d_ep(sO_og, WIN_OG, z)
        dG = d_ep(sG_og, WIN_OG, z)
        dO_pre = dlog(sOy[WIN_L_PRE[0]][z], sOy[WIN_L_PRE[1]][z])
        dL_pre = dlog(sL[WIN_L_PRE[0]][z], sL[WIN_L_PRE[1]][z])
        dO_post = dlog(sOy[WIN_L_POST[0]][z], sOy[WIN_L_POST[1]][z])
        dL_post = dlog(sL[WIN_L_POST[0]][z], sL[WIN_L_POST[1]][z])
        rows[z] = {
            "ru": T[z]["ru"], "be": T[z]["be"], "oblast": T[z]["parent"],
            "min_oblcenter": travel.get(z, {}).get("oblcenter"),
            "min_minsk": travel.get(z, {}).get("minsk"),
            "dO_9020": dO, "dG_9020": dG,
            "d_9020": (dO - dG) if dO is not None else None,
            "dO_0020": d_ep(sO_ogr, WIN_OG_ROBUST, z), "dG_0020": d_ep(sG_ogr, WIN_OG_ROBUST, z),
            "dO_1319": dO_pre, "dL_1319": dL_pre,
            "dO_2124": dO_post, "dL_2124": dL_post,
            "gap_pre": abs(dL_pre - dO_pre) / (WIN_L_PRE[1] - WIN_L_PRE[0]),
            "gap_post": abs(dL_post - dO_post) / (WIN_L_POST[1] - WIN_L_POST[0]),
            "dL_dmsp": dlog(sL[WIN_L_DMSP[0]][z], sL[WIN_L_DMSP[1]][z]),
            # ряды для графика района: доли каждого датчика
            "series": {
                "O": {str(t): sO[t][z] for t in EPOCHS if z in sO[t]},
                "G": {str(t): sG[t][z] for t in EPOCHS},
                "Oy": {str(y): sOy[y][z] for y in sorted(sOy) if y >= 2004},
                "L": {str(y): sL[y][z] for y in sorted(sL)},
            },
        }

    col = lambda k: [rows[z][k] for z in raions]  # noqa: E731
    og = [z for z in raions if rows[z]["dO_9020"] is not None]     # 117
    colog = lambda k: [rows[z][k] for z in og]  # noqa: E731

    # --- гипотезы ----------------------------------------------------------
    r1, p1 = spearman(colog("dO_9020"), colog("dG_9020"))
    h1 = {"rho": round(r1, 4), "p": round(p1, 6), "n": len(og),
          "threshold": H1_RHO, "window": list(WIN_OG),
          "verdict": "confirmed" if r1 >= H1_RHO else "refuted"}
    r1r, _ = spearman(col("dO_0020"), col("dG_0020"))
    h1["robust_2000_2020_rho"] = round(r1r, 4)

    r2, p2 = spearman(col("dO_1319"), col("dL_1319"))
    h2 = {"rho": round(r2, 4), "p": round(p2, 6), "threshold": H2_RHO, "window": list(WIN_L_PRE),
          "verdict": "confirmed" if r2 >= H2_RHO else "refuted"}
    # робастность на DMSP: официальный ряд по эпохам 1990 -> 2010 ближе всего
    # к окну 1992 -> 2011 (годового ряда 1992/2011 по районам нет)
    zd = og_zones((1990, 2010))
    sOd = win_shares(off_e, (1990, 2010), zd)
    sLd = {y: shares({z: sL[y][z] for z in zd}) for y in WIN_L_DMSP}
    rd = [z for z in raions if z in zd]
    r2r, _ = spearman([dlog(sOd[1990][z], sOd[2010][z]) for z in rd],
                      [dlog(sLd[WIN_L_DMSP[0]][z], sLd[WIN_L_DMSP[1]][z]) for z in rd])
    h2["robust_dmsp_rho"] = round(r2r, 4)
    h2["robust_dmsp_note"] = "официальный ряд 1990->2010 (эпохи), свет DMSP 1992->2011"

    with_t = [z for z in og if rows[z]["min_oblcenter"] is not None]
    r3, p3 = spearman([rows[z]["min_oblcenter"] for z in with_t],
                      [rows[z]["d_9020"] for z in with_t])
    h3 = {"rho": round(r3, 4), "p": round(p3, 6), "n": len(with_t), "threshold": H3_RHO,
          "verdict": "confirmed" if (r3 >= H3_RHO and p3 < 0.05) else "refuted"}

    m_pre, m_post = median(col("gap_pre")), median(col("gap_post"))
    ratio = m_post / m_pre if m_pre else float("inf")
    h4 = {"median_gap_pre": round(m_pre, 5), "median_gap_post": round(m_post, 5),
          "ratio": round(ratio, 3), "threshold": H4_RATIO,
          "verdict": "confirmed" if ratio >= H4_RATIO else "refuted"}

    # --- описательные сводки для страницы ---------------------------------
    agree = sum(1 for z in og
                if (rows[z]["dO_9020"] < 0) == (rows[z]["dG_9020"] < 0))
    summary = {
        "n_og": len(og),
        "sign_agree_OG": agree,
        "official_share_down_9020": sum(1 for z in og if rows[z]["dO_9020"] < 0),
        "ghs_share_down_9020": sum(1 for z in og if rows[z]["dG_9020"] < 0),
        "minsk_share": {
            "O": {"1990": sO_og[1990][MINSK], "2020": sO_og[2020][MINSK]},
            "G": {"1990": sG_og[1990][MINSK], "2020": sG_og[2020][MINSK]},
            "L": {"2013": sL[2013][MINSK], "2019": sL[2019][MINSK],
                  "2021": sL[2021][MINSK], "2024": sL[2024][MINSK]},
        },
        "vnl_raw_vs_lshare_max_pct": vnl_check,
    }

    # ---------------- ПОСТ-ХОК (не пререгистрировано) --------------------
    # H2 опровергнута: изменения света не следуют за изменениями населения.
    # Ниже — диагностика ПОЧЕМУ; расчёты сделаны после данных и не могут
    # подтверждать или спасать H2.
    lvl = {}
    for y in (2013, 2019, 2024):
        rl, _ = spearman([sL[y][z] for z in raions], [sOy[y][z] for z in raions])
        lvl[str(y)] = round(rl, 4)
    a = [dlog(sL[2013][z], sL[2016][z]) for z in raions]
    b2 = [dlog(sL[2016][z], sL[2019][z]) for z in raions]
    persist, _ = spearman(a, b2)
    conv, _ = spearman([sL[2013][z] for z in raions], col("dL_1319"))
    belts = []
    for lo, hi in ((0, 60), (60, 120), (120, 10 ** 6)):
        zs = [z for z in raions if rows[z]["min_minsk"] is not None
              and lo <= rows[z]["min_minsk"] < hi]
        belts.append({"belt": f"{lo}-{hi if hi < 10 ** 6 else ''}", "n": len(zs),
                      "median_dO": round(median([rows[z]["dO_1319"] for z in zs]), 4),
                      "median_dL": round(median([rows[z]["dL_1319"] for z in zs]), 4)})
    posthoc = {
        "disclaimer": "Пост-хок: расчёты этого блока выполнены ПОСЛЕ получения "
                      "данных и не были заморожены пререгистрацией. Они объясняют, "
                      "почему H2 опровергнута, но не могут её подтверждать.",
        "level_rho_light_vs_pop": lvl,
        "light_up_pop_down_1319": sum(1 for z in raions
                                      if rows[z]["dL_1319"] > 0 and rows[z]["dO_1319"] < 0),
        "median_dO_1319": round(median(col("dO_1319")), 4),
        "median_dL_1319": round(median(col("dL_1319")), 4),
        "light_change_persistence_rho": round(persist, 4),
        "light_change_vs_initial_share_rho": round(conv, 4),
        "belts_minsk": belts,
    }

    # округление только при выгрузке, статистика — на точных значениях
    for z in raions:
        r = rows[z]
        for k in list(r):
            if isinstance(r[k], float) and r[k] is not None:
                r[k] = round(r[k], 6)
        r["series"] = {k: {y: round(v, 7) for y, v in s.items()}
                       for k, s in r["series"].items()}

    return {
        "version": VERSION, "code": "INF-22",
        "preregistration": "docs/preregistration/sensors-v0.1.md",
        "epochs": EPOCHS,
        "windows": {"OG": list(WIN_OG), "OG_robust": list(WIN_OG_ROBUST),
                    "L_pre": list(WIN_L_PRE), "L_post": list(WIN_L_POST),
                    "L_dmsp": list(WIN_L_DMSP)},
        "seams": [list(s) for s in LIGHT_SEAMS],
        "territories": rows,
        "findings": {"H1": h1, "H2": h2, "H3": h3, "H4": h4},
        "summary": summary,
        "posthoc": posthoc,
        "gates": gates,
    }


def write_csv(res: dict):
    path = CURATED / "sensors.csv"
    keys = ["dO_9020", "dG_9020", "d_9020", "dO_0020", "dG_0020", "dO_1319", "dL_1319",
            "dO_2124", "dL_2124", "gap_pre", "gap_post", "dL_dmsp",
            "min_oblcenter", "min_minsk"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["territory_id", "name_ru"] + keys)
        for z in sorted(res["territories"]):
            r = res["territories"][z]
            w.writerow([z, r["ru"]] + ["" if r[k] is None else r[k] for k in keys])
    return path


def main() -> None:
    res = build()
    dst = OUT / "sensors.json"
    dst.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":"),
                              sort_keys=True) + "\n")
    p = write_csv(res)
    g = res["gates"]
    print(f"INF-22 sensors v{VERSION}")
    print("  гейты: " + "  ".join(f"{k} {'ok' if g[k]['pass'] else 'FAIL'}"
                                    for k in ("V-1", "V-2", "V-3", "V-4", "V-5")))
    for h, v in res["findings"].items():
        print(f"  {h}: {v['verdict']}")
    print(f"  {dst.relative_to(ROOT)} ({dst.stat().st_size // 1024} КБ)")
    print(f"  {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
