#!/usr/bin/env python3
"""«Шов на карте»: разрывы на пяти границах Беларуси (стандартная библиотека).

Копия логики etl/seam.py проекта, адаптированная к путям пакета.

Вход:  sources/raw/cells.csv.gz (ячейки 1 км в полосе ±52 км у границы;
       строится тяжёлым шагом etl/seam_extract.py проекта из глобальных растров).
Выход (по умолчанию в data/final/):
  seam.json              - ровно тот файл, что читает страница /research/seam
                           (при параметрах по умолчанию совпадает побайтно
                           с web/public/data/seam.json проекта);
  seam_results.md        - сводная таблица основной спецификации и вердикты;
  estimates.csv          - все 660 оценок: 16 исходов x 5 участков x спецификации;
  computed_results.json  - плоский список {metric, value} (только числа) для
                           сверки с checks/expected_results.json.

Методика и гипотезы зафиксированы ДО расчёта: PREREGISTRATION.md.

Основная спецификация - строго по пререгистрации: локальная линейная
регрессия по знаковому расстоянию d (сосед > 0), треугольное ядро, h = 25 км,
бублик 2 км, без городских ядер и Чернобыля, ошибки кластеризованы по блокам
25x25 км. Проверки устойчивости, добавленные ПОСЛЕ фиксации по итогам
методического обзора (подучастки 1°x1° как у Pinkovskiy, ложные границы ±30 км,
бублик 10 км для DMSP, контроль только застройкой для I), помечены added=True.

Запуск:  python3 code/build.py                      # воспроизвести data/final/
         python3 code/build.py --out /tmp/s --h 15  # стресс допущений (AGENT.md, задача 3)
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from collections import defaultdict
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
CELLS = PKG / "sources" / "raw" / "cells.csv.gz"
OUT_DIR = PKG / "data" / "final"

SEGS = ["PL", "LT", "LV", "RU", "UA"]
SEG_RU = {"PL": "Польша", "LT": "Литва", "LV": "Латвия", "RU": "Россия", "UA": "Украина"}
SOVIET = ["LT", "LV", "RU", "UA"]           # до 1991 г. — внутрисоюзные границы
H_MAIN = 25.0
H_ALT = (15.0, 50.0)
DONUT = 2.0
DONUT_DMSP = 10.0
CITY_KM = 5.0
CHERN_KM = 35.0
FLARES = [(28.750, 55.457), (29.342, 51.891)]   # Нафтан, Мозырский НПЗ (как в INF-08)
FLARE_KM = 2.5
BLOCK_M = 25000.0
PLACEBO_KM = 30.0
BIN_KM = 2.0
ALPHA = 0.05


def _f(v: str) -> float:
    return float(v) if v != "" else float("nan")


def ln1(x: float) -> float:
    return math.log1p(max(x, 0.0))


# ------------------------------------------------------------------ исходы
# код: (подпись, функция y(r), семейство, использует DMSP)
OUTCOMES = {
    "B_9015": ("Рост застройки WSF, 1990→2015, Δln", lambda r: ln1(r["wsf_2015"]) - ln1(r["wsf_1990"]), "B", False),
    "B_9000": ("Рост застройки WSF, 1990→2000, Δln", lambda r: ln1(r["wsf_2000"]) - ln1(r["wsf_1990"]), "B", False),
    "B_0015": ("Рост застройки WSF, 2000→2015, Δln", lambda r: ln1(r["wsf_2015"]) - ln1(r["wsf_2000"]), "B", False),
    "G_7590": ("Рост застройки GHSL, 1975→1990, Δln (до 1991)", lambda r: ln1(r["built_1990"]) - ln1(r["built_1975"]), "B", False),
    "G_9015": ("Рост застройки GHSL, 1990→2015, Δln", lambda r: ln1(r["built_2015"]) - ln1(r["built_1990"]), "B", False),
    "L_9212": ("Огни DMSP, 1992→2012, Δln(1+DN)", lambda r: ln1(r["li_2012"]) - ln1(r["li_1992"]), "L", True),
    "L_9204": ("Огни DMSP, 1992→2004, Δln(1+DN)", lambda r: ln1(r["li_2004"]) - ln1(r["li_1992"]), "L", True),
    "L_0412": ("Огни DMSP, 2004→2012, Δln(1+DN)", lambda r: ln1(r["li_2012"]) - ln1(r["li_2004"]), "L", True),
    "L_1419": ("Огни (VIIRS-ряд Li), 2014→2019, Δln(1+DN)", lambda r: ln1(r["li_2019"]) - ln1(r["li_2014"]), "L", False),
    "L_1924": ("Огни (VIIRS-ряд Li), 2019→2024, Δln(1+DN)", lambda r: ln1(r["li_2024"]) - ln1(r["li_2019"]), "L", False),
    "C_0319": ("Доля пашни GLAD, 2003→2019, п.п.", lambda r: 100.0 * (r["crop_2019"] - r["crop_2003"]), "C", False),
    "I_2019": ("Огни VIIRS 2019, ln(0,1+нВт) при равной застройке", lambda r: math.log(0.1 + max(r["vnl_2019"], 0.0)), "I", False),
    # уровни — контекст, не гипотезы
    "lvl_crop19": ("Уровень: доля пашни 2019, %", lambda r: 100.0 * r["crop_2019"], "level", False),
    "lvl_wsf15": ("Уровень: застройка WSF 2015, ln(1+м²)", lambda r: ln1(r["wsf_2015"]), "level", False),
    "lvl_vnl19": ("Уровень: огни VIIRS 2019, ln(0,1+нВт)", lambda r: math.log(0.1 + max(r["vnl_2019"], 0.0)), "level", False),
    "lvl_pop20": ("Уровень: GHS-POP 2020, ln(1+чел.) — механический, только контекст", lambda r: ln1(r["pop_2020"]), "level", False),
}
CONTROLS = {
    "I_2019": [lambda r: ln1(r["wsf_2015"]), lambda r: ln1(r["pop_2020"])],   # как в пререгистрации
}
CONTROLS_ADDED = {
    "I_2019": [lambda r: ln1(r["wsf_2015"])],                                # только застройка
}


# ------------------------------------------------------------------ данные
def hav_km(lon1, lat1, lon2, lat2):
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2 +
         math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742.0 * math.asin(math.sqrt(a))


def load_cells(path: Path = CELLS):
    num = None
    out = []
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        rd_ = csv.DictReader(fh)
        for r in rd_:
            if num is None:
                num = [k for k in r if k not in ("cell", "side", "seg", "subseg", "city")]
            row = {k: _f(r[k]) for k in num}
            row["side"], row["seg"], row["subseg"] = r["side"], r["seg"], r["subseg"]
            row["cl"] = f'{int(row["x3035"] // BLOCK_M)}_{int(row["y3035"] // BLOCK_M)}'
            row["flare"] = any(hav_km(row["lon"], row["lat"], lo, la) < FLARE_KM for lo, la in FLARES)
            out.append(row)
    return out


def base_ok(r, *, cities=True, chern=True):
    if cities and r["city_km"] < CITY_KM:
        return False
    if chern and r["chern_km"] < CHERN_KM:
        return False
    if r["flare"]:
        return False
    return True


# ------------------------------------------------------------------ регрессия
def _solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda i: abs(M[i][c]))
        if abs(M[p][c]) < 1e-12:
            raise ValueError("вырожденная матрица")
        M[c], M[p] = M[p], M[c]
        for i in range(n):
            if i != c:
                f = M[i][c] / M[c][c]
                if f:
                    for j in range(c, n + 1):
                        M[i][j] -= f * M[c][j]
    return [M[i][n] / M[i][i] for i in range(n)]


def _inv(A):
    n = len(A)
    cols = [_solve(A, [1.0 if i == j else 0.0 for i in range(n)]) for j in range(n)]
    return [[cols[j][i] for j in range(n)] for i in range(n)]


def norm_p(t: float) -> float:
    return math.erfc(abs(t) / math.sqrt(2.0))


def rd(rows, ycode, *, h=None, donut=None, kernel="tri", at=0.0, side=None,
       controls=None, fe=False):
    """Локальная линейная RDD. rows — отфильтрованные ячейки одного участка.

    h/donut по умолчанию - текущие H_MAIN/DONUT (читаются в момент вызова,
    чтобы флаги --h/--donut работали). at — положение (ложной) границы;
    side — 'BY'/'NB' ограничивает выборку одной стороной (для ложных границ).
    fe — поглощение эффектов подучастков.
    """
    h = H_MAIN if h is None else h
    donut = DONUT if donut is None else donut
    fy = OUTCOMES[ycode][1]
    ctr = controls or []
    data = []
    for r in rows:
        d = r["d_km"]
        if abs(d) < donut:
            continue
        if side == "BY" and d >= 0:
            continue
        if side == "NB" and d <= 0:
            continue
        dd = d - at
        if abs(dd) > h:
            continue
        w = (1.0 - abs(dd) / h) if kernel == "tri" else 1.0
        if w <= 0:
            continue
        y = fy(r)
        if not math.isfinite(y):
            continue
        D = 1.0 if dd > 0 else 0.0
        x = [1.0, D, dd, dd * D] + [f(r) for f in ctr]
        data.append((x, y, w, r["cl"], r["subseg"]))
    nl = sum(1 for x, *_ in data if x[1] == 0.0)
    nr = len(data) - nl
    if nl < 30 or nr < 30:
        return None
    if fe:   # взвешенное вычитание средних по подучасткам (Фриш–Во)
        grp = defaultdict(lambda: [0.0, None, 0.0])
        for x, y, w, cl, sg in data:
            g = grp[sg]
            g[0] += w
            g[1] = [w * v for v in x] if g[1] is None else [a + w * v for a, v in zip(g[1], x)]
            g[2] += w * y
        new = []
        for x, y, w, cl, sg in data:
            g = grp[sg]
            mx = [v / g[0] for v in g[1]]
            new.append(([v - m for v, m in zip(x, mx)][1:], y - g[2] / g[0], w, cl, sg))
        data = new
    k = len(data[0][0])
    XtX = [[0.0] * k for _ in range(k)]
    Xty = [0.0] * k
    for x, y, w, *_ in data:
        for i in range(k):
            wx = w * x[i]
            Xty[i] += wx * y
            row = XtX[i]
            for j in range(i, k):
                row[j] += wx * x[j]
    for i in range(k):
        for j in range(i):
            XtX[i][j] = XtX[j][i]
    try:
        beta = _solve(XtX, Xty)
        Binv = _inv(XtX)
    except ValueError:
        return None
    meat_s = defaultdict(lambda: [0.0] * k)
    for x, y, w, cl, sg in data:
        e = y - sum(b * v for b, v in zip(beta, x))
        s = meat_s[cl]
        for i in range(k):
            s[i] += w * x[i] * e
    G = len(meat_s)
    meat = [[0.0] * k for _ in range(k)]
    for s in meat_s.values():
        for i in range(k):
            for j in range(k):
                meat[i][j] += s[i] * s[j]
    n = len(data)
    corr = (G / max(G - 1, 1)) * ((n - 1) / max(n - k, 1))
    ti = 0 if fe else 1     # при fe константа поглощена, D — первый регрессор
    var = corr * sum(Binv[ti][a] * meat[a][b] * Binv[b][ti] for a in range(k) for b in range(k))
    tau = beta[ti]
    se = math.sqrt(max(var, 0.0))
    # средние у линии (2–10 км), описательно
    near = defaultdict(list)
    for r in rows:
        d = r["d_km"]
        if donut <= abs(d) <= max(donut, 2.0) + 8.0 and side is None:
            y = fy(r)
            if math.isfinite(y):
                near["NB" if d > 0 else "BY"].append(y)
    m = lambda v: (sum(v) / len(v)) if v else None
    return {"tau": tau, "se": se, "p": norm_p(tau / se) if se > 0 else None,
            "n_by": nl, "n_nb": nr, "clusters": G,
            "mean_by": m(near["BY"]), "mean_nb": m(near["NB"])}


def profile(rows, ycode, lim=50.0, step=None):
    step = BIN_KM if step is None else step
    fy = OUTCOMES[ycode][1]
    acc = defaultdict(lambda: [0.0, 0])
    for r in rows:
        d = r["d_km"]
        if abs(d) > lim or abs(d) < DONUT:
            continue
        y = fy(r)
        if not math.isfinite(y):
            continue
        b = math.floor(d / step) * step + step / 2
        a = acc[round(b, 1)]
        a[0] += y
        a[1] += 1
    return [{"d": b, "y": round(s / n, 5), "n": n} for b, (s, n) in sorted(acc.items())]


def rnd(x, nd=4):
    return None if x is None else round(x, nd)


def pack(res):
    if res is None:
        return None
    return {k: (rnd(v, 5) if isinstance(v, float) else v) for k, v in res.items()}


# ------------------------------------------------------------------ официальные ряды (H5)
UNITS_DIR = PKG / "sources" / "raw" / "units"
# окна «перепись к переписи», подобранные по соседу; Беларусь — ближайшие свои переписи
WIN_NB = {"PL": (1988, 2021), "LT": (2001, 2021), "LV": (1990, 2021), "RU": (1989, 2021), "UA": (1989, 2020)}
WIN_BY = {"PL": (1989, 2019), "LT": (1999, 2019), "LV": (1989, 2019), "RU": (1989, 2019), "UA": (1989, 2019)}
CITY_LEVELS = {"city", "town", "gorsovet", "miasto", "city_municipality", "state_city", "urban_okrug",
               "savivaldybe_city", "republic_city", "raion_admin_unused"}
# Беларусь: ряд «raion» в data.json — полигон района ВМЕСТЕ с городами обл. подчинения
# (периметр проекта). Для сравнения с соседями (где города исключены) берётся
# административный район без города (unit_id с суффиксом «#admin»). У Оршанского и
# Полоцкого в «#admin» разрыв периметра (с переписи 2019 город в составе района) —
# исключены.
BY_PERIMETER_BREAK = {"r-arshanski", "r-polacki"}


def _cell_index(cells):
    idx = defaultdict(list)
    for r in cells:
        idx[(round(r["lon"] * 10), round(r["lat"] * 10))].append((r["lon"], r["lat"], r["d_km"], r["seg"]))
    return idx


def _locate(idx, lon, lat, max_km=8.0):
    best = None
    k0, k1 = round(lon * 10), round(lat * 10)
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            for c in idx.get((k0 + dx, k1 + dy), ()):
                dd = hav_km(lon, lat, c[0], c[1])
                if best is None or dd < best[0]:
                    best = (dd, c)
    if best is None or best[0] > max_km:
        return None
    return best[1][2], best[1][3]


def _median(v):
    v = sorted(v)
    n = len(v)
    if not n:
        return None
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def units_block(cells):
    """Описательное сравнение официального населения единиц в полосе 0–50 км.

    Темп — средний годовой лог-прирост, % в год, в окне «перепись к переписи».
    Городские единицы (города ≥50 тыс., горсоветы) исключены, как ядра в сетке.
    """
    pf, gf = UNITS_DIR / "units_population.csv", UNITS_DIR / "units_geo.csv"
    if not (pf.exists() and gf.exists()):
        return None
    pops, meta = defaultdict(dict), {}
    for r in csv.DictReader(open(pf, encoding="utf-8")):
        try:
            y, v = int(r["year"]), float(r["population"])
        except (ValueError, TypeError, KeyError):
            continue
        k = (r["country"].strip(), r["unit_id"].strip())
        pops[k][y] = v
        meta[k] = (r.get("unit_name", ""), (r.get("unit_level") or "").strip().lower())
    geo = {}
    for r in csv.DictReader(open(gf, encoding="utf-8")):
        try:
            geo[(r["country"].strip(), r["unit_id"].strip())] = (float(r["lon"]), float(r["lat"]))
        except (ValueError, TypeError, KeyError):
            continue
    idx = _cell_index(cells)
    admin_hosts = {uid.split("#")[0] for (cc, uid) in pops if cc == "BY" and uid.endswith("#admin")}
    units = []
    for k, ser in pops.items():
        cc, uid = k
        level = meta[k][1]
        base_uid = uid.split("#")[0]
        if cc == "BY":
            if base_uid in BY_PERIMETER_BREAK:
                continue
            if level == "raion" and uid in admin_hosts:
                continue                       # есть вариант без обл. города — берём его
        elif level in CITY_LEVELS:
            continue
        if level == "gmina_urban" and max(ser.values()) > 50_000:
            continue
        if len(ser) < 2:
            continue
        gk = k if k in geo else (cc, base_uid)
        if gk not in geo:
            continue
        lon, lat = geo[gk]
        if hav_km(lon, lat, 30.099, 51.389) < CHERN_KM:
            continue                           # Чернобыльская зона, как в сетке
        loc = _locate(idx, lon, lat)
        if loc is None or abs(loc[0]) > 50:
            continue
        units.append({"country": k[0], "unit_id": k[1], "name": meta[k][0], "level": meta[k][1],
                      "d_km": round(loc[0], 1), "seg": loc[1],
                      "series": {str(y): v for y, v in sorted(ser.items())}})

    def rate(u, w):
        s = {int(a): b for a, b in u["series"].items()}
        a, b = w
        if s.get(a, 0) > 0 and s.get(b, 0) > 0:
            return 100.0 * (math.log(s[b]) - math.log(s[a])) / (b - a)
        return None

    comp = {}
    for sg in SEGS:
        nb = [x for x in (rate(u, WIN_NB[sg]) for u in units if u["country"] == sg and u["seg"] == sg) if x is not None]
        by = [x for x in (rate(u, WIN_BY[sg]) for u in units if u["country"] == "BY" and u["seg"] == sg) if x is not None]
        comp[sg] = {"win_nb": WIN_NB[sg], "win_by": WIN_BY[sg], "n_nb": len(nb), "n_by": len(by),
                    "nb_median": rnd(_median(nb), 3), "by_median": rnd(_median(by), 3)}
    ok = {}
    for sg, want_faster in (("LT", True), ("LV", True), ("RU", True), ("PL", False)):
        c = comp[sg]
        if c["nb_median"] is None or c["by_median"] is None:
            ok[sg] = None
        else:
            ok[sg] = (c["nb_median"] < c["by_median"]) if want_faster else (c["nb_median"] > c["by_median"])
    held = sum(1 for v in ok.values() if v)
    known = sum(1 for v in ok.values() if v is not None)
    verdict = ("подтверждена (описательно)" if known == 4 and held == 4 else
               "частично (описательно)" if held >= 2 else "не подтверждена (описательно)")
    twins = []
    tf = UNITS_DIR / "twins.csv"
    if tf.exists():
        for r in csv.DictReader(open(tf, encoding="utf-8")):
            if r.get("population"):
                try:
                    twins.append({"group": r["twin_group"], "country": r["country"], "unit": r["unit_name"],
                                  "year": int(r["year"]), "pop": float(r["population"]), "source": r.get("source", "")})
                except ValueError:
                    pass
    return {"units": units, "comparison": comp, "checks": ok, "verdict": verdict, "twins": twins,
            "note": "Темп — % в год (средний лог-прирост) в окне «перепись к переписи»; определения населения у стран разные."}


# ------------------------------------------------------------------ сборка
VERDICT_SCORE = {"подтверждена": 1.0, "частично": 0.5, "не подтверждена": 0.0}


def verdict_score(v: str):
    """Вердикт -> число для computed_results (1 / 0,5 / 0); «нет данных» -> None."""
    return VERDICT_SCORE.get(v.replace(" (описательно)", "").strip())


def compute(cells_path: Path = CELLS):
    """Весь расчёт: возвращает (out, get) - структуру seam.json и поиск оценки."""
    cells = load_cells(cells_path)
    by_seg = {s: [r for r in cells if r["seg"] == s and base_ok(r)] for s in SEGS}
    by_seg_all = {s: [r for r in cells if r["seg"] == s and not r["flare"]] for s in SEGS}
    est = []

    def add(ycode, seg, spec, res, **extra):
        rec = {"outcome": ycode, "seg": seg, "spec": spec, **extra}
        rec.update(pack(res) or {"tau": None})
        est.append(rec)

    for s in SEGS:
        rows = by_seg[s]
        for y, (_, _, fam, dmsp) in OUTCOMES.items():
            ctr = CONTROLS.get(y)
            add(y, s, "main", rd(rows, y, controls=ctr), added=False)
            for h in H_ALT:
                add(y, s, f"h{int(h)}", rd(rows, y, h=h, controls=ctr), added=False)
            add(y, s, "uniform", rd(rows, y, kernel="uni", controls=ctr), added=False)
            add(y, s, "with_cities", rd(by_seg_all[s], y, controls=ctr), added=False)
            add(y, s, "fe_subseg", rd(rows, y, controls=ctr, fe=True), added=True)
            add(y, s, "placebo_by", rd(rows, y, at=-PLACEBO_KM, side="BY", controls=ctr), added=True)
            add(y, s, "placebo_nb", rd(rows, y, at=PLACEBO_KM, side="NB", controls=ctr), added=True)
            if dmsp:
                add(y, s, "donut10", rd(rows, y, donut=DONUT_DMSP, controls=ctr), added=True)
            if y in CONTROLS_ADDED:
                add(y, s, "built_only", rd(rows, y, controls=CONTROLS_ADDED[y]), added=True)

    def get(y, s, spec="main"):
        for e in est:
            if e["outcome"] == y and e["seg"] == s and e["spec"] == spec:
                return e
        return None

    def sig_neg(e):
        return e and e.get("tau") is not None and e["tau"] < 0 and e["p"] is not None and e["p"] < ALPHA

    # ---------------- вердикты по пререгистрации
    h1_sig = [s for s in SEGS if (e := get("B_9015", s)) and e.get("p") is not None and e["p"] < ALPHA]
    h1_did = {}
    for s in SOVIET:
        pre, post = get("G_7590", s), get("G_9015", s)
        if pre and post and pre.get("tau") is not None and post.get("tau") is not None:
            h1_did[s] = {"pre": pre["tau"], "post": post["tau"],
                         "raw": abs(post["tau"]) > abs(pre["tau"]),
                         "annual": abs(post["tau"]) / 25 > abs(pre["tau"]) / 15}
    did_raw = sum(v["raw"] for v in h1_did.values())
    did_ann = sum(v["annual"] for v in h1_did.values())
    h1 = {"sig_segments": h1_sig, "did": h1_did,
          "verdict": ("подтверждена" if len(h1_sig) >= 3 and did_raw >= 3 else
                      "частично" if len(h1_sig) >= 3 or did_raw >= 3 else "не подтверждена")}
    h2_neg = [s for s in ["RU", "LT", "LV", "UA"] if sig_neg(get("C_0319", s))]
    pl = get("C_0319", "PL")
    h2 = {"neg_segments": h2_neg, "pl_tau": pl and pl.get("tau"),
          "verdict": ("подтверждена" if len(h2_neg) >= 3 and pl and pl.get("tau") is not None and abs(pl["tau"]) < 2 else
                      "частично" if len(h2_neg) >= 2 else "не подтверждена")}
    h3_neg = [s for s in SEGS if sig_neg(get("I_2019", s))]
    h3_neg_b = [s for s in SEGS if sig_neg(get("I_2019", s, "built_only"))]
    h3 = {"neg_segments": h3_neg, "neg_segments_built_only": h3_neg_b,
          "verdict": "подтверждена" if len(h3_neg) >= 4 else ("частично" if len(h3_neg) >= 2 else "не подтверждена")}
    ua = get("L_1924", "UA")
    h4 = {"ua": ua, "verdict": "подтверждена" if sig_neg(ua) else "не подтверждена"}
    ub = units_block(cells)
    h5 = {"verdict": ub["verdict"], "checks": ub["checks"]} if ub else {"verdict": "нет данных"}

    profiles ={y: {s: profile(by_seg[s], y) for s in SEGS}
                for y in ["B_9015", "G_7590", "G_9015", "L_9212", "L_1924", "C_0319", "lvl_crop19",
                          "lvl_vnl19", "lvl_wsf15", "lvl_pop20", "I_2019"]}
    counts = {s: {"by": sum(1 for r in by_seg[s] if r["d_km"] < 0),
                  "nb": sum(1 for r in by_seg[s] if r["d_km"] > 0)} for s in SEGS}
    out = {
        "meta": {
            "title": "Шов на карте: разрывы на пяти границах Беларуси",
            "prereg": "docs/preregistration/seam-v0.1.md",
            "h_main_km": H_MAIN, "donut_km": DONUT, "city_km": CITY_KM, "chern_km": CHERN_KM,
            "flare_km": FLARE_KM, "block_km": BLOCK_M / 1000, "alpha": ALPHA,
            "sign": "tau = сосед минус Беларусь у самой линии",
            "cells_total": len(cells), "cells_by_segment": counts,
            "outcomes": {k: {"label": v[0], "family": v[2]} for k, v in OUTCOMES.items()},
            "segments": SEG_RU,
        },
        "hypotheses": {"H1": h1, "H2": h2, "H3": h3, "H4": h4, "H5": h5},
        "units": ub,
        "estimates": est,
        "profiles": profiles,
    }
    return out, get


def write_md(out, get, path: Path):
    L = ["# «Шов на карте»: результаты (генерируется etl/seam.py)", "",
         f"τ = сосед минус Беларусь у самой линии; основная спецификация: h = {H_MAIN:g} км, бублик {DONUT:g} км,",
         f"без городских ядер ({CITY_KM:g} км от городов ≥50 тыс.) и Чернобыля ({CHERN_KM:g} км), "
         f"ошибки по блокам {BLOCK_M / 1000:g} км.", ""]
    hdr = "| Исход | " + " | ".join(SEG_RU[s] for s in SEGS) + " |"
    L += ["## Основная спецификация", "", hdr, "|---|" + "---|" * len(SEGS)]
    for y, (lab, *_rest) in OUTCOMES.items():
        cells = []
        for s in SEGS:
            e = get(y, s)
            if not e or e.get("tau") is None:
                cells.append("—")
                continue
            star = "**" if e["p"] is not None and e["p"] < ALPHA else ""
            cells.append(f"{star}{e['tau']:+.3f}{star} ({e['se']:.3f})")
        L.append(f"| {lab} | " + " | ".join(cells) + " |")
    L += ["", "Жирным — p < 0,05. В скобках — кластерная ошибка.", ""]
    ub = out.get("units")
    if ub:
        L += ["## Официальное население единиц в полосе 0–50 км (описательно)", "",
              "| Участок | Окно соседа | Медиана соседа, %/год | n | Окно Беларуси | Медиана Беларуси, %/год | n |",
              "|---|---|---|---|---|---|---|"]
        for s in SEGS:
            c = ub["comparison"][s]
            fm = lambda v: "—" if v is None else f"{v:+.2f}"
            L.append(f"| {SEG_RU[s]} | {c['win_nb'][0]}→{c['win_nb'][1]} | {fm(c['nb_median'])} | {c['n_nb']} | "
                     f"{c['win_by'][0]}→{c['win_by'][1]} | {fm(c['by_median'])} | {c['n_by']} |")
        L += ["", ub["note"], ""]
    L += ["## Гипотезы", ""]
    for k, v in out["hypotheses"].items():
        L.append(f"- **{k}** — {v['verdict']}")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


EST_COLS = ["outcome", "label", "family", "seg", "spec", "added", "tau", "se", "p", "sig",
            "n_by", "n_nb", "clusters", "mean_by", "mean_nb"]


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, float):
        return f"{v:.5f}"
    return str(v)


def write_estimates(out, path: Path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(EST_COLS)
        for e in out["estimates"]:
            lab, _, fam, _ = OUTCOMES[e["outcome"]]
            p = e.get("p")
            sig = None if p is None else (p < ALPHA)
            rec = {**e, "label": lab, "family": fam, "sig": sig}
            w.writerow([_fmt(rec.get(c)) for c in EST_COLS])


def computed_metrics(out, get):
    """Плоский список {metric, value}: ТОЛЬКО числа (валидатор берёт abs())."""
    res = [{"metric": "cells_total", "value": out["meta"]["cells_total"]}]
    for s in SEGS:
        c = out["meta"]["cells_by_segment"][s]
        res.append({"metric": f"cells_analysis_{s}_by", "value": c["by"]})
        res.append({"metric": f"cells_analysis_{s}_nb", "value": c["nb"]})
    for y in OUTCOMES:
        for s in SEGS:
            e = get(y, s)
            if not e or e.get("tau") is None:
                continue
            res.append({"metric": f"tau_{y}_{s}", "value": e["tau"]})
            res.append({"metric": f"se_{y}_{s}", "value": e["se"]})
            if e.get("p") is not None:
                res.append({"metric": f"p_{y}_{s}", "value": e["p"]})
    hyp = out["hypotheses"]
    for k in ("H1", "H2", "H3", "H4", "H5"):
        sc = verdict_score(hyp[k]["verdict"])
        if sc is not None:          # H5 без таблиц единиц - «нет данных», числа нет
            res.append({"metric": f"verdict_{k}", "value": sc})
    ub = out.get("units")
    if ub:       # H5 (описательно): медианы годового темпа, %/год, и число единиц по участкам
        res.append({"metric": "units_n", "value": len(ub["units"])})
        for s in SEGS:
            c = ub["comparison"][s]
            for key in ("nb_median", "by_median", "n_nb", "n_by"):
                if c.get(key) is not None:
                    res.append({"metric": f"h5_{key}_{s}", "value": c[key]})
    res.append({"metric": "H1_sig_segments_n", "value": len(hyp["H1"]["sig_segments"])})
    res.append({"metric": "H2_neg_segments_n", "value": len(hyp["H2"]["neg_segments"])})
    res.append({"metric": "H3_neg_segments_n", "value": len(hyp["H3"]["neg_segments"])})
    res.append({"metric": "H3_neg_segments_built_only_n",
                "value": len(hyp["H3"]["neg_segments_built_only"])})
    assert all(isinstance(r["value"], (int, float)) and not isinstance(r["value"], bool)
               for r in res), "computed_results: допустимы только числа"
    return res


def main() -> None:
    global H_MAIN, DONUT, DONUT_DMSP, CITY_KM, CHERN_KM, BLOCK_M, PLACEBO_KM, UNITS_DIR
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cells", type=Path, default=CELLS, help="таблица ячеек (csv.gz)")
    ap.add_argument("--units-dir", type=Path, default=UNITS_DIR,
                    help="папка таблиц официальных единиц для H5 (units_population.csv, units_geo.csv)")
    ap.add_argument("--out", type=Path, default=OUT_DIR,
                    help="папка результатов (для стресс-прогонов укажите другую, чтобы не "
                         "перезаписать data/final/)")
    ap.add_argument("--h", type=float, default=H_MAIN, help="ширина окна основной спецификации, км (25)")
    ap.add_argument("--donut", type=float, default=DONUT, help="бублик у линии, км (2)")
    ap.add_argument("--donut-dmsp", type=float, default=DONUT_DMSP, help="бублик проверки DMSP, км (10)")
    ap.add_argument("--city-km", type=float, default=CITY_KM, help="радиус исключения городских ядер, км (5)")
    ap.add_argument("--chern-km", type=float, default=CHERN_KM, help="радиус исключения вокруг ЧАЭС, км (35)")
    ap.add_argument("--block-km", type=float, default=BLOCK_M / 1000, help="сторона блока кластеров, км (25)")
    ap.add_argument("--placebo-km", type=float, default=PLACEBO_KM, help="сдвиг ложных границ, км (30)")
    a = ap.parse_args()
    H_MAIN, DONUT, DONUT_DMSP = a.h, a.donut, a.donut_dmsp
    CITY_KM, CHERN_KM, BLOCK_M, PLACEBO_KM = a.city_km, a.chern_km, a.block_km * 1000, a.placebo_km
    UNITS_DIR = a.units_dir

    out, get = compute(a.cells)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "seam.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")),
                                     encoding="utf-8")
    write_md(out, get, a.out / "seam_results.md")
    write_estimates(out, a.out / "estimates.csv")
    (a.out / "computed_results.json").write_text(
        json.dumps(computed_metrics(out, get), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("OK", a.out, "оценок:", len(out["estimates"]))
    for k, v in out["hypotheses"].items():
        print(k, v["verdict"])


if __name__ == "__main__":
    main()
