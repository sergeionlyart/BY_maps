"""Этап 5: субрегиональный прогноз - 118 районов, 12 городов областного
подчинения, ~200 городов и гп (уровни 2-3 ROADMAP_FORECAST §1).

Методы:
- районы и 5 необлцентровых городов обл. подчинения - Гамильтон-Перри
  (Орша и Полоцк к переписи-2019 вошли в районы и прогнозируются как
  доли уровня 3):
  коэффициенты когортного изменения (CCR) между переписями 2009 и 2019 по
  полу; интервал переписей 10 лет = сдвиг когорты на ДВЕ 5-летние группы,
  поэтому проекция идёт шагом 10 лет (2019 -> 2029 -> ... -> 2079), а
  экспортная сетка получается интерполяцией. Когорты 0-4 и 5-9 - через
  child-woman ratio (CWR04/CWR59: дети на женщину 15-49 на конец периода).
  Малые когорты сглаживаются к областному CCR-профилю (shrinkage
  w = n/(n+K), K=1000); чернобыльские районы классов 1-2 - принудительно
  w<=0.5 и нижний порог CCR (не экстраполируем постчернобыльское падение);
- 5 облцентров - собственные CCMPP шагом 5 лет: национальное дожитие
  (mx HMD-2018), рождения через CWR города, миграция - имплицированное
  возрастное сальдо 2009-2019 (невязка когортного изменения к дожитию)
  с линейным затуханием до 40% к 2060 г.;
- согласование (IPF): на каждый экспортный год по (пол x возрастная
  группа) районы + города обл. подчинения масштабируются к областному
  CCMPP выбранного сценария - суммы сходятся точно, сценарная динамика
  (рождаемость, смертность, миграция) приходит из уровня 1;
- ~200 городов и гп - доля города в населении района: логистический тренд
  logit(share) ~ год по ряду 1970-2026 (уровень якорится на последнем
  наблюдении, тренд даёт наклон), прогноз share x район(сценарий);
  привязка город-район - data/curated/city_raion.csv (native/pip/manual);
  гп без привязки или с рядом, оборванным до 2019, исключены явно.

Запускается из etl.forecast.run (общий экспорт forecast.json v2026.2).
"""
from __future__ import annotations

import csv
import json
import math

from ..common import ROOT, OUT
from . import AGE_GROUPS, STEP, TERRITORIES
from .data import census_structure, mortality_mx
from .lifetable import survival_5y

CURATED = ROOT / "data" / "curated"

K_SHRINK = 1000          # shrinkage: вес территории w = n_когорты / (n + K)
W_CAP_CHERNOBYL = 0.5    # классы 1-2 INF-07: не менее половины веса - область
CCR_FLOOR = 0.6          # нижний порог CCR относительно областного
CCR_CAP = 1.6            # защитный потолок (агломерационные выбросы малых когорт)
SHARE_CAP = 0.92         # максимум доли одного города в районе
SHARE_SUM_CAP = 0.95     # максимум суммы долей городов района
SLOPE_CAP = 0.03         # |наклон| логит-тренда доли, 1/год
OBL_CENTERS = {"c-brest": "BY-BR", "c-viciebsk": "BY-VI", "c-homiel": "BY-HO",
               "c-hrodna": "BY-HR", "c-mahilou": "BY-MA"}
MIG_DECAY_YEAR = 2060    # к этому году имплицированная миграция затухает...
MIG_DECAY_TO = 0.4       # ...до этой доли уровня 2009-2019

CCR_YEARS = list(range(2019, 2080, 10))    # сетка Гамильтона-Перри
CCMPP_YEARS = list(range(2019, 2080, 5))   # сетка CCMPP облцентров
WOMEN_1549 = ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49"]
N_G = len(AGE_GROUPS)  # 17

# Периметры. В переписном разрезе (age*.csv) районы НЕ включают города
# областного подчинения (дети области = районы + 12 городов), а в рядах
# data.json районы-хосты их ВКЛЮЧАЮТ. Экспортный ряд района-хоста =
# прогноз района (переписной периметр) + прогноз города.
HOSTED = {
    "r-babrujski": "c-babrujsk", "r-baranavicki": "c-baranavichy",
    "r-brescki": "c-brest", "r-homielski": "c-homiel",
    "r-hrodzienski": "c-hrodna", "r-mahilouski": "c-mahilou",
    "r-pinski": "c-pinsk", "r-polacki": "c-navapolack",
    "r-smalavicki": "c-zhodzina", "r-viciebski": "c-viciebsk",
}
# Орша и Полоцк к переписи-2019 вошли в состав районов (в age2019 их
# строки нулевые): для сопоставимости CCR их структуры-2009 вливаются
# в районы, прогноз самих городов - уровень 3 (доля в районе).
MERGED_2009 = {"c-orsha": "r-arshanski", "c-polack": "r-polacki"}


# ---------------------------------------------------------------- входы

def load_sub_structures(year: int) -> dict:
    """{terr: {sex: {age: pop}}} для районов и городов обл. подчинения.

    Орша/Полоцк вливаются в свои районы (периметр переписи-2019)."""
    out: dict = {}
    for r in csv.DictReader(open(CURATED / f"age{year}.csv")):
        t, s = r["territory_id"], r["sex"]
        if not t.startswith(("r-", "c-")):
            continue
        t = MERGED_2009.get(t, t)
        age = r["age_group"].replace("80 и старше", "80+")
        if age not in AGE_GROUPS:
            continue
        out.setdefault(t, {"m": dict.fromkeys(AGE_GROUPS, 0.0),
                           "f": dict.fromkeys(AGE_GROUPS, 0.0)})
        out[t][s][age] += int(r["pop"])
    return out


def oblast_of() -> dict[str, str]:
    return {r["territory_id"]: r["oblast"]
            for r in csv.DictReader(open(CURATED / "age2019.csv"))}


def _chernobyl_classes() -> set[str]:
    return {r["territory_id"]
            for r in csv.DictReader(open(CURATED / "chernobyl_zones.csv"))
            if r["class"] in ("1", "2")}


def city_raion_map() -> dict[str, str]:
    return {r["city_id"]: r["raion_id"]
            for r in csv.DictReader(open(CURATED / "city_raion.csv"))}


# ------------------------------------------------- Гамильтон-Перри (CCR)

def ccr_of(p09: dict, p19: dict) -> dict:
    """CCR за 10 лет: когорта группы i (2009) -> группа i+2 (2019).

    {'m'/'f': [r_0..r_14], 'open': {'m','f'}, 'cwr04'/'cwr59': {'m','f'}}
    r_i для i=0..13: P19[i+2]/P09[i]; открытый хвост: когорты 70-74, 75-79,
    80+ 2009 г. все в 80+ 2019 г. CWR: дети на женщину 15-49 в 2019 г."""
    out: dict = {"m": [], "f": [], "open": {}, "cwr04": {}, "cwr59": {}}
    for s in ("m", "f"):
        for i in range(N_G - 3):  # 0..13: приёмная группа i+2 <= 16 (80+ отдельно)
            num = p19[s][AGE_GROUPS[i + 2]]
            den = p09[s][AGE_GROUPS[i]]
            out[s].append(num / den if den > 0 else None)
        den = p09[s]["70-74"] + p09[s]["75-79"] + p09[s]["80+"]
        out["open"][s] = p19[s]["80+"] / den if den > 0 else None
    women19 = sum(p19["f"][g] for g in WOMEN_1549)
    for s in ("m", "f"):
        out["cwr04"][s] = p19[s]["0-4"] / women19 if women19 > 0 else 0.0
        out["cwr59"][s] = p19[s]["5-9"] / women19 if women19 > 0 else 0.0
    return out


def shrunk_ccr(terr_ccr: dict, obl_ccr: dict, p09: dict,
               chernobyl: bool) -> dict:
    """Сглаживание CCR территории к областному профилю + пороги."""
    out: dict = {"m": [], "f": [], "open": {}, "cwr04": {}, "cwr59": {}}

    def blend(r_t, r_o, n):
        if r_t is None or r_o is None:
            return r_o if r_o is not None else 1.0
        w = n / (n + K_SHRINK)
        if chernobyl:
            w = min(w, W_CAP_CHERNOBYL)
        r = w * r_t + (1 - w) * r_o
        return min(max(r, CCR_FLOOR * r_o), CCR_CAP * r_o)

    for s in ("m", "f"):
        for i in range(N_G - 3):
            out[s].append(blend(terr_ccr[s][i], obl_ccr[s][i],
                                p09[s][AGE_GROUPS[i]]))
        n_open = p09[s]["70-74"] + p09[s]["75-79"] + p09[s]["80+"]
        out["open"][s] = blend(terr_ccr["open"][s], obl_ccr["open"][s], n_open)
    women09 = sum(p09["f"][g] for g in WOMEN_1549)
    for key in ("cwr04", "cwr59"):
        for s in ("m", "f"):
            out[key][s] = blend(terr_ccr[key][s], obl_ccr[key][s], women09)
    return out


def ccr_step10(pop: dict, ccr: dict) -> dict:
    """Один шаг Гамильтона-Перри: t -> t+10 (сдвиг на две группы)."""
    new = {"m": dict.fromkeys(AGE_GROUPS, 0.0), "f": dict.fromkeys(AGE_GROUPS, 0.0)}
    for s in ("m", "f"):
        for i in range(N_G - 3):
            new[s][AGE_GROUPS[i + 2]] = pop[s][AGE_GROUPS[i]] * ccr[s][i]
        new[s]["80+"] += (pop[s]["70-74"] + pop[s]["75-79"] + pop[s]["80+"]) \
            * ccr["open"][s]
    women = sum(new["f"][g] for g in WOMEN_1549)
    for s in ("m", "f"):
        new[s]["0-4"] = women * ccr["cwr04"][s]
        new[s]["5-9"] = women * ccr["cwr59"][s]
    return new


# --------------------------------------------------- облцентры (CCMPP)

def implied_migration(p09: dict, p19: dict, surv: dict) -> dict:
    """Возрастное чистое сальдо на пятилетку как невязка когортного
    изменения 2009-2019 к чистому дожитию (rate на человека когорты).

    За 10 лет когорта i проходит две ступени дожития (S_i * S_{i+1});
    остаток относим к миграции и делим на 2 (пятилетний эквивалент)."""
    out = {"m": [0.0] * (N_G - 1), "f": [0.0] * (N_G - 1)}
    for s in ("m", "f"):
        S = surv[s]["S"]
        for i in range(N_G - 3):
            den = p09[s][AGE_GROUPS[i]]
            if den <= 0:
                continue
            obs = p19[s][AGE_GROUPS[i + 2]] / den
            expected = S[i] * S[i + 1] if i + 1 < len(S) else S[i] ** 2
            rate5 = (obs - expected) / 2
            # распределяем на две пятилетние ступени поровну
            out[s][i] += rate5 / 2
            out[s][i + 1] += rate5 / 2
        den = p09[s]["70-74"] + p09[s]["75-79"] + p09[s]["80+"]
        if den > 0:
            obs = p19[s]["80+"] / den
            expected = surv[s]["S_open"] ** 2
            out[s][N_G - 2] += (obs - expected) / 2
    return out


def ccmpp_city_step(pop: dict, surv: dict, mig_rate: dict, phi: float,
                    cwr04: dict) -> dict:
    """Шаг 5 лет для облцентра: дожитие + имплицированная миграция + CWR."""
    new = {"m": dict.fromkeys(AGE_GROUPS, 0.0), "f": dict.fromkeys(AGE_GROUPS, 0.0)}
    for s in ("m", "f"):
        S = surv[s]["S"]
        for i in range(N_G - 2):
            base = pop[s][AGE_GROUPS[i]]
            new[s][AGE_GROUPS[i + 1]] = max(
                base * (S[i] + phi * mig_rate[s][i]), 0.0)
        base = pop[s]["75-79"] + pop[s]["80+"]
        new[s]["80+"] = max(
            base * (surv[s]["S_open"] + phi * mig_rate[s][N_G - 2]), 0.0)
    women = sum(new["f"][g] for g in WOMEN_1549)
    for s in ("m", "f"):
        new[s]["0-4"] = women * cwr04[s]
    return new


# ------------------------------------------------------------ проекция

def project_children() -> dict:
    """Несогласованная проекция районов и городов обл. подчинения:
    {terr: {year: {sex: {age: pop}}}} (сетки CCR_YEARS / CCMPP_YEARS)."""
    p09, p19 = load_sub_structures(2009), load_sub_structures(2019)
    obl = oblast_of()
    chern = _chernobyl_classes()
    obl_ccr = {o: ccr_of(census_structure(2009)[o], census_structure(2019)[o])
               for o in TERRITORIES if o != "BY-HM"}
    mx0 = mortality_mx(2018)
    surv = {s: survival_5y(mx0[s]) for s in ("m", "f")}

    out: dict = {}
    for t in sorted(p19):
        cur = {s: dict(v) for s, v in p19[t].items()}
        traj = {2019: {s: dict(v) for s, v in cur.items()}}
        if t in OBL_CENTERS:
            mig = implied_migration(p09[t], p19[t], surv)
            cwr04 = ccr_of(p09[t], p19[t])["cwr04"]
            for y in CCMPP_YEARS[:-1]:
                k = min(max((y - 2019) / (MIG_DECAY_YEAR - 2019), 0.0), 1.0)
                phi = 1.0 - k * (1.0 - MIG_DECAY_TO)
                cur = ccmpp_city_step(cur, surv, mig, phi, cwr04)
                traj[y + STEP] = {s: dict(v) for s, v in cur.items()}
        else:
            ccr = shrunk_ccr(ccr_of(p09[t], p19[t]), obl_ccr[obl[t]],
                             p09[t], t in chern)
            for y in CCR_YEARS[:-1]:
                cur = ccr_step10(cur, ccr)
                traj[y + 10] = {s: dict(v) for s, v in cur.items()}
        out[t] = traj
    return out


def interp_struct(traj: dict, year: int) -> dict:
    """Структура на произвольный год линейной интерполяцией по сетке."""
    ys = sorted(traj)
    year = min(max(year, ys[0]), ys[-1])
    if year in traj:
        return {s: dict(v) for s, v in traj[year].items()}
    y0 = max(y for y in ys if y <= year)
    y1 = min(y for y in ys if y >= year)
    k = (year - y0) / (y1 - y0)
    return {s: {g: traj[y0][s][g] + k * (traj[y1][s][g] - traj[y0][s][g])
                for g in AGE_GROUPS} for s in ("m", "f")}


def official_totals_2026() -> dict[str, float]:
    """Официальные оценки на 01.01.2026 в переписном периметре модели:
    у районов-хостов вычитается город обл. подчинения (в data.json он
    входит в ряд района); при отсутствии 2026 - последняя оценка."""
    data = json.loads((OUT / "data.json").read_text())["territories"]

    def last_val(t: str) -> float:
        pops = data[t]["pop"]
        return float(pops.get("2026", pops[max(pops)])[0])

    out = {}
    for t in load_sub_structures(2019):
        v = last_val(t)
        if t in HOSTED:
            v -= last_val(HOSTED[t])
        out[t] = v
    return out


def reconcile(children: dict, obl_structures: dict,
              export_years: list[int],
              calibrate_2026: dict[str, float] | None = None) -> dict:
    """IPF-согласование: на каждый год по области, полу и группе дети
    (районы + города обл. подчинения) масштабируются к областному CCMPP.

    calibrate_2026: официальные итоги территорий на 2026 - каждая
    траектория умножается на константу official/model (стартовая
    калибровка: CCR 2009-2019 задаёт динамику, уровень 2026 - факт),
    после чего нормируется к областному итогу заново.

    Возвращает {terr: {year: total}} (согласованные итоги)."""
    obl = oblast_of()
    groups: dict[str, list[str]] = {}
    for t in children:
        groups.setdefault(obl[t], []).append(t)

    totals: dict[str, dict[int, float]] = {t: {} for t in children}
    obl_totals: dict[str, dict[int, float]] = {}
    for year in export_years:
        for o, kids in groups.items():
            target = interp_struct(obl_structures[o], year)
            structs = {t: interp_struct(children[t], year) for t in kids}
            for s in ("m", "f"):
                for g in AGE_GROUPS:
                    ssum = sum(structs[t][s][g] for t in kids)
                    f = target[s][g] / ssum if ssum > 0 else 0.0
                    for t in kids:
                        structs[t][s][g] *= f
            for t in kids:
                totals[t][year] = sum(structs[t]["m"].values()) + \
                    sum(structs[t]["f"].values())
            obl_totals.setdefault(o, {})[year] = sum(
                totals[t][year] for t in kids)

    if calibrate_2026:
        y0 = export_years[0]
        ratio = {t: calibrate_2026[t] / totals[t][y0]
                 for t in totals if totals[t][y0] > 0}
        for t in totals:
            r = ratio.get(t, 1.0)
            for y in export_years:
                totals[t][y] *= r
        # повторная нормировка к областным итогам (по тоталам: поправка
        # уровня не возрастная, структура согласована первым проходом)
        for o, kids in groups.items():
            for y in export_years:
                ssum = sum(totals[t][y] for t in kids)
                f = obl_totals[o][y] / ssum if ssum > 0 else 0.0
                for t in kids:
                    totals[t][y] *= f
    return totals


# ------------------------------------------------------- города (доли)

def _logit(x: float) -> float:
    x = min(max(x, 1e-4), 1 - 1e-4)
    return math.log(x / (1 - x))


def _sigmoid(z: float) -> float:
    return 1 / (1 + math.exp(-z))


def fit_city_share(city_pop: dict, raion_pop: dict,
                   year_from: int = 1970, year_to: int = 2026) -> dict | None:
    """Логистический тренд доли города в районе.

    OLS logit(share) ~ год; наклон ограничен |b| <= SLOPE_CAP; уровень
    якорится на последнем наблюдении (тренд задаёт только наклон).
    Возвращает {'a','b','last_year'} или None (нет пересечений рядов)."""
    pts = []
    for y_str, rec in city_pop.items():
        y = int(y_str)
        if year_from <= y <= year_to and y_str in raion_pop:
            v, rv = rec[0], raion_pop[y_str][0]
            if rv > 0 and v > 0:
                pts.append((y, _logit(v / rv)))
    if not pts:
        return None
    y_last = max(p[0] for p in pts)
    z_last = dict(pts)[y_last]
    if len(pts) < 3:
        return {"a": z_last, "b": 0.0, "last_year": y_last}
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    mz = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    sxz = sum((p[0] - mx) * (p[1] - mz) for p in pts)
    b = sxz / sxx if sxx else 0.0
    b = min(max(b, -SLOPE_CAP), SLOPE_CAP)
    return {"a": z_last - b * y_last, "b": b, "last_year": y_last}


def share_at(fit: dict, year: int) -> float:
    return min(_sigmoid(fit["a"] + fit["b"] * year), SHARE_CAP)


def cities_forecast(raion_totals: dict, sub_ids: set[str],
                    export_years: list[int],
                    year_to: int = 2026) -> dict:
    """Прогноз городов уровня 3: {city: {year: pop}} = share x район.

    sub_ids - территории уровня 2 (районы + города обл. подчинения):
    они прогнозируются напрямую и здесь пропускаются."""
    data = json.loads((OUT / "data.json").read_text())["territories"]
    cmap = city_raion_map()
    fits: dict[str, dict] = {}
    by_raion: dict[str, list[str]] = {}
    for c, r in sorted(cmap.items()):
        if c in sub_ids:
            continue
        pops = data[c]["pop"]
        if not pops or int(max(pops)) < 2019:
            continue  # ряд оборван до 2019 - без прогноза (см. методблок)
        fit = fit_city_share(pops, data[r]["pop"], year_to=year_to)
        if fit:
            fits[c] = fit
            by_raion.setdefault(r, []).append(c)

    out: dict[str, dict[int, float]] = {c: {} for c in fits}
    for r, cs in by_raion.items():
        for y in export_years:
            shares = {c: share_at(fits[c], y) for c in cs}
            ssum = sum(shares.values())
            if ssum > SHARE_SUM_CAP:
                shares = {c: v * SHARE_SUM_CAP / ssum for c, v in shares.items()}
            for c in cs:
                out[c][y] = shares[c] * raion_totals[r][y]
    return out
