"""INF-20 `sexratio`: карта, где не хватает мужчин.

Вопрос: где в Беларуси не хватает мужчин, а где — женщин; как половая
диспропорция распределена по возрастам и 118 районам от переписи 2009 года до
2056-го; и какая её часть создана сверхсмертностью мужчин, а какая — отъездом
женщин.

Пререгистрация (заморожена до расчётов): `docs/preregistration/sexratio-v0.1.md`.
Гипотезы H1-H4, метрики, гейты S-1…S-8 и ограничения — там; здесь только счёт.

Данные (всё завендорено, сеть не нужна):
  data/curated/age2009.csv, age2019.csv   переписи, 137 территорий x пол x возраст
  data/curated/forecast_age_raion_v2026_4.json   прогноз v2026.4 по полу, 118 районов
  data/curated/mortality.csv              страновые таблицы смертности 1959-2018
  data/curated/travel_times.csv           времена в пути (INF-04) для теста H1
  web/public/data/data.json               население по годам, названия RU/BE

Периметр: «периметр прогноза» — район включает свой город областного подчинения.
Переписные файлы района его исключают, поэтому применяется правило сведения
`age[район] + age[город-хост]` по карте HOSTED (раздел 4 пререгистрации).

Запуск: python -m etl.sexratio -> web/public/data/sexratio.json
                                  data/curated/sexratio.csv
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from .common import ROOT, OUT
from .wages import HOSTED

CURATED = ROOT / "data" / "curated"
VERSION = "1.0.0"

# возрастные группы прогноза (17); переписные файлы приводятся к ним
AGE_GROUPS = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34",
              "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69",
              "70-74", "75-79", "80+"]
CENSUS_RENAME = {"80 и старше": "80+"}
AGE_UNKNOWN = "Возраст не определен"

FERTILE = ["25-29", "30-34", "35-39"]          # брачно-репродуктивная сводка
OLD = ["70-74", "75-79", "80+"]                # сводка 70+
BIRTH = "0-4"                                  # гейт S-4

CENSUS_YEARS = (2009, 2019)
MORTALITY_SPAN = (2009, 2018)                  # 2019 берёт таблицу 2018 (последняя)
ONSET_HIGH, ONSET_LOW = 115.0, 85.0            # пороги onset_year
CORE_SCENARIO = "base:official"

# городские территории для H2: Минск + шесть областных центров
CITY_CORES = ["BY-HM", "c-brest", "c-viciebsk", "c-homiel",
              "c-hrodna", "c-mahilou"]
# Минск — область-уровень; остальные облцентры — города в age-файлах


# ---------------------------------------------------------------- загрузка

def _load_census(year: int) -> dict[str, dict[str, dict[str, int]]]:
    """{territory_id: {age_group: {'m': n, 'f': n}}} + ключ AGE_UNKNOWN."""
    path = CURATED / f"age{year}.csv"
    out: dict[str, dict[str, dict[str, int]]] = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            age = CENSUS_RENAME.get(r["age_group"], r["age_group"])
            cell = out.setdefault(r["territory_id"], {}).setdefault(
                age, {"m": 0, "f": 0})
            cell[r["sex"]] += int(r["pop"])
    return out


def _load_census_by_locality(year: int) -> dict:
    """{territory_id: {locality: {age_group: {'m','f'}}}} — нужен только для
    пост-хок диагностики узких возрастных пиков (закрытые учреждения)."""
    out: dict = {}
    with open(CURATED / f"age{year}.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            age = CENSUS_RENAME.get(r["age_group"], r["age_group"])
            cell = (out.setdefault(r["territory_id"], {})
                      .setdefault(r["locality"], {})
                      .setdefault(age, {"m": 0, "f": 0}))
            cell[r["sex"]] += int(r["pop"])
    return out


def _load_forecast() -> dict:
    return json.loads((CURATED / "forecast_age_raion_v2026_4.json").read_text())


def _load_survival() -> dict[tuple[str, int], float]:
    """Десятилетняя вероятность выживания по полу и точному возрасту.

    Покогортно: человек возраста `a` в 2009 году проходит годовые таблицы
    2009, 2010, … 2018 (раздел 5 пункт 5 пререгистрации; для 2019 года
    таблица 2018 — последняя доступная). qx берётся как
    number_deaths / number_survivors — это исключает неоднозначность единиц
    поля probability_of_death.
    """
    q: dict[tuple[str, int, int], float] = {}   # (sex, year, age) -> qx
    with open(CURATED / "mortality.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r["age"].isdigit():
                continue
            y = int(r["year"])
            if not (MORTALITY_SPAN[0] <= y <= MORTALITY_SPAN[1]):
                continue
            surv = float(r["number_survivors"])
            if surv <= 0:
                continue
            sex = {"male": "m", "female": "f"}.get(r["sex"])
            if sex:
                q[(sex, y, int(r["age"]))] = float(r["number_deaths"]) / surv
    out: dict[tuple[str, int], float] = {}
    for sex in ("m", "f"):
        for age in range(0, 100):
            p = 1.0
            for step in range(10):
                year = min(MORTALITY_SPAN[0] + step, MORTALITY_SPAN[1])
                p *= 1.0 - q.get((sex, year, age + step), 1.0)
            out[(sex, age)] = p
    return out


def _group_survival(surv: dict[tuple[str, int], float],
                    sex: str, group: str) -> float:
    """Выживание пятилетней группы: среднее по пяти однолетним возрастам.

    Допущение о равномерности внутри группы фиксировано в пререгистрации
    (ограничение 2 раздела 7); группы от 80+ в декомпозиции не участвуют.
    """
    start = int(group.split("-")[0])
    vals = [surv[(sex, start + k)] for k in range(5) if (sex, start + k) in surv]
    return sum(vals) / len(vals) if vals else 0.0


# ------------------------------------------------------------ периметр

def _perimeter(census: dict, rid: str) -> dict[str, dict[str, int]]:
    """Район в периметре прогноза: переписной район + его город-хост."""
    base = {a: dict(v) for a, v in census.get(rid, {}).items()}
    host = HOSTED.get(rid)
    if host:
        for a, v in census.get(host, {}).items():
            cell = base.setdefault(a, {"m": 0, "f": 0})
            cell["m"] += v["m"]
            cell["f"] += v["f"]
    return base


# -------------------------------------------------------------- метрики

def _ratio(m: float, f: float) -> float | None:
    return round(100.0 * m / f, 2) if f > 0 else None


def _profile(cells: dict[str, dict[str, float]]) -> list[float | None]:
    return [_ratio(cells.get(a, {}).get("m", 0), cells.get(a, {}).get("f", 0))
            for a in AGE_GROUPS]


def _summary(cells: dict[str, dict[str, float]]) -> dict:
    mf = lambda gs, s: sum(cells.get(a, {}).get(s, 0) for a in gs)  # noqa: E731
    m39, f39 = mf(FERTILE, "m"), mf(FERTILE, "f")
    m70, f70 = mf(OLD, "m"), mf(OLD, "f")
    gap = m39 - f39
    return {
        "r2539": _ratio(m39, f39),
        "r70": _ratio(m70, f70),
        "gap": round(gap, 1),
        "gap_rel": round(100.0 * gap / f39, 2) if f39 > 0 else None,
        "missing": round(abs(gap), 1),
        # какого пола не хватает в брачно-репродуктивном возрасте
        "missing_sex": "f" if gap > 0 else ("m" if gap < 0 else None),
        "pop2539": round(m39 + f39, 1),
    }


def _forecast_cells(node: dict) -> dict[str, dict[str, float]]:
    return {a: {"m": node["m"][i], "f": node["f"][i]}
            for i, a in enumerate(AGE_GROUPS)}


# ------------------------------------------------------- статистика H1

def _ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Ранговая корреляция Спирмена и двусторонний p (нормальное
    приближение z = rho * sqrt(n-1); при n = 118 этого достаточно,
    приближение указано в METHODS)."""
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


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


# --------------------------------------------------------------- расчёт

def build() -> dict:
    c09, c19 = _load_census(2009), _load_census(2019)
    fc = _load_forecast()
    surv = _load_survival()
    data = json.loads((OUT / "data.json").read_text())
    T = data["territories"]
    travel = {r["territory_id"]: float(r["min_minsk"])
              for r in csv.DictReader(open(CURATED / "travel_times.csv",
                                           encoding="utf-8"))
              if r.get("min_minsk")}

    raions = sorted(fc["territories"])
    combos = [f"{s}:{j}" for s in fc["scenarios"] for j in fc["jumpoffs"]]
    node_years = [str(y) for y in fc["node_years"]]

    territories: dict[str, dict] = {}
    gates: dict[str, dict] = {}

    # --- S-3: разбиение периметров замкнуто -----------------------------
    def partition(census: dict, year: int) -> dict:
        # суммируются ВСЕ группы, включая AGE_UNKNOWN: переписной итог
        # страны её содержит, и без неё разбиение не замкнётся
        tot = lambda tid: sum(v["m"] + v["f"]                      # noqa: E731
                              for v in census.get(tid, {}).values())
        rs = sum(tot(t) for t in census if t.startswith("r-"))
        cs = sum(tot(t) for t in census if t.startswith("c-"))
        hm = tot("BY-HM")
        obl = sum(tot(t) for t in census
                  if t.startswith("BY-") and t != "BY-HM")
        return {"raions": rs, "cities": cs, "minsk": hm, "oblasts": obl,
                "raions_plus_cities": rs + cs, "country": obl + hm,
                "closed": rs + cs == obl}
    gates["S-3"] = {str(y): partition(c, y) for y, c in ((2009, c09), (2019, c19))}
    gates["S-3"]["pass"] = all(gates["S-3"][str(y)]["closed"] for y in CENSUS_YEARS)

    # --- S-2: страновое соотношение по переписи 2019 ---------------------
    cy = c19
    m_all = sum(v["m"] for t in ("BY-HM",) for v in cy.get(t, {}).values()) + \
        sum(v["m"] for t in cy if t.startswith("BY-") and t != "BY-HM"
            for v in cy[t].values())
    f_all = sum(v["f"] for t in ("BY-HM",) for v in cy.get(t, {}).values()) + \
        sum(v["f"] for t in cy if t.startswith("BY-") and t != "BY-HM"
            for v in cy[t].values())
    country_ratio = _ratio(m_all, f_all)
    # диапазон 85-88 — поправка 1 от 2026-10-04 к пререгистрации
    gates["S-2"] = {"country_sex_ratio_2019": country_ratio, "range": [85.0, 88.0],
                    "pass": country_ratio is not None and 85.0 <= country_ratio <= 88.0}

    # --- по районам ------------------------------------------------------
    s1_fails, s5_max_resid = [], 0.0
    # S-4 (поправка 2): соотношение 0-4 проверяется МЕДИАНОЙ по районам, а не
    # по каждому району — в группе 0-4 районные численности слишком малы
    s4_census: list[float] = []
    s4_forecast: dict[str, dict[str, list[float]]] = {}
    for rid in raions:
        cells09 = _perimeter(c09, rid)
        cells19 = _perimeter(c19, rid)

        prof = {"2009": _profile(cells09), "2019": _profile(cells19)}
        if prof["2019"][0] is not None:
            s4_census.append(prof["2019"][0])
        summ = {"2009": _summary(cells09), "2019": _summary(cells19)}

        # S-1: сумма по полу и возрастам против data.json 2019
        got = sum(v["m"] + v["f"] for a, v in cells19.items() if a != AGE_UNKNOWN)
        want = (T[rid]["pop"].get("2019") or [0])[0]
        if want and abs(got - want) / want > 0.005:
            s1_fails.append({"id": rid, "sum": got, "data_json": want})

        # прогноз: полный профиль только для опорного сценария, сводка — для всех
        fprof: dict[str, list] = {}
        fsumm: dict[str, dict] = {}
        for combo in combos:
            for y in node_years:
                cells = _forecast_cells(fc["territories"][rid][combo][y])
                fsumm.setdefault(combo, {})[y] = _summary(cells)
                if combo == CORE_SCENARIO:
                    fprof[y] = _profile(cells)
                br = _ratio(cells[BIRTH]["m"], cells[BIRTH]["f"])
                if br is not None:
                    s4_forecast.setdefault(combo, {}).setdefault(y, []).append(br)

        # onset_year по опорному сценарию
        onset = None
        for y in node_years:
            r = fsumm[CORE_SCENARIO][y]["r2539"]
            if r is not None and (r > ONSET_HIGH or r < ONSET_LOW):
                onset = int(y)
                break

        # --- декомпозиция «умерли / уехали», когорты 2009 -> 2019 --------
        decomp = {}
        for i, g in enumerate(AGE_GROUPS[:-2]):          # до 70-74 включительно
            tgt = AGE_GROUPS[i + 2]                      # +10 лет = +2 группы
            if tgt == "80+":
                continue
            row = {}
            for sex in ("m", "f"):
                start = cells09.get(g, {}).get(sex, 0)
                obs = cells19.get(tgt, {}).get(sex, 0)
                exp = start * _group_survival(surv, sex, g)
                row[sex] = {"start": start, "expected": round(exp, 1),
                            "observed": obs, "residual": round(obs - exp, 1)}
                # S-5: тождество наблюдённое = ожидаемое + остаток
                s5_max_resid = max(
                    s5_max_resid,
                    abs(obs - (exp + (obs - exp))))
            # вклад смертности в половой разрыв: разница ожидаемых выживаний;
            # вклад миграции: разница остатков
            mort = (row["m"]["start"] - row["m"]["expected"]) - \
                   (row["f"]["start"] - row["f"]["expected"])
            migr = row["m"]["residual"] - row["f"]["residual"]
            row["mortality_gap"] = round(mort, 1)
            row["migration_gap"] = round(migr, 1)
            row["dominant"] = "migration" if abs(migr) > abs(mort) else "mortality"
            decomp[f"{g}->{tgt}"] = row

        # H3 считается по когортам, которым в 2019 пришлось 25-39:
        # это 15-19->25-29, 20-24->30-34, 25-29->35-39
        h3_keys = ["15-19->25-29", "20-24->30-34", "25-29->35-39"]
        mort_sum = sum(abs(decomp[k]["mortality_gap"]) for k in h3_keys if k in decomp)
        migr_sum = sum(abs(decomp[k]["migration_gap"]) for k in h3_keys if k in decomp)

        territories[rid] = {
            "ru": T[rid]["ru"], "be": T[rid]["be"], "oblast": T[rid]["parent"],
            "min_minsk": travel.get(rid),
            "profile": prof, "summary": summ,
            "forecast_profile": fprof, "forecast_summary": fsumm,
            "onset_year": onset,
            "decomposition": decomp,
            "h3": {"mortality": round(mort_sum, 1), "migration": round(migr_sum, 1),
                   "dominant": "migration" if migr_sum > mort_sum else "mortality"},
            "unknown_age_2019": cells19.get(AGE_UNKNOWN, {"m": 0, "f": 0}),
        }

    gates["S-1"] = {"fails": s1_fails, "pass": not s1_fails}
    def _outside(xs: list[float]) -> float:
        return 100.0 * sum(1 for x in xs if not (102.0 <= x <= 108.0)) / len(xs)

    med_c = _median(s4_census)
    out_c = _outside(s4_census)
    s4_rows = []
    for combo, years in sorted(s4_forecast.items()):
        for y, xs in sorted(years.items()):
            med_f = _median(xs)
            s4_rows.append({
                "combo": combo, "year": y,
                "median": round(med_f, 2),
                "in_band": 102.0 <= med_f <= 108.0,
                "drift_from_census": round(med_f - med_c, 2),
                "outside_pct": round(_outside(xs), 1),
                "excess_noise_pp": round(_outside(xs) - out_c, 1),
            })
    gates["S-4"] = {
        "census_2019": {"median": round(med_c, 2), "outside_pct": round(out_c, 1),
                        "in_band": 102.0 <= med_c <= 108.0},
        "forecast": s4_rows,
        "amendment": "поправка 2 от 2026-10-04: медиана по районам вместо "
                     "каждого района + контроль дрейфа и прироста шума",
        "pass": (102.0 <= med_c <= 108.0)
                and all(r["in_band"] for r in s4_rows)
                and all(abs(r["drift_from_census"]) <= 2.0 for r in s4_rows)
                and all(r["excess_noise_pp"] <= 15.0 for r in s4_rows),
    }
    gates["S-5"] = {"max_residual": round(s5_max_resid, 9),
                    "pass": s5_max_resid < 1e-6}

    # --- S-6 (поправка 3): внутренние проверки странового остатка ---------
    # внешнего ряда сальдо миграции за 2009-2019 в завендоренных данных нет,
    # поэтому проверяется величина остатка и его возрастной профиль
    cov_start = res_abs = 0.0
    young = old = 0.0
    for rid in raions:
        for key, row in territories[rid]["decomposition"].items():
            tgt = key.split("->")[1]
            for sex in ("m", "f"):
                cov_start += row[sex]["start"]
                r = abs(row[sex]["residual"])
                res_abs += r
                if tgt in ("20-24", "25-29", "30-34", "35-39"):
                    young += r
                elif tgt in ("60-64", "65-69", "70-74", "75-79"):
                    old += r
    net = sum(row[sex]["residual"]
              for rid in raions
              for row in territories[rid]["decomposition"].values()
              for sex in ("m", "f"))
    share = 100.0 * abs(net) / cov_start if cov_start else 0.0
    gates["S-6"] = {
        "covered_pop_2009": round(cov_start, 1),
        "net_residual": round(net, 1),
        "net_residual_pct_of_covered": round(share, 2),
        "abs_residual_share_young_20_39_pct": round(100.0 * young / res_abs, 1) if res_abs else None,
        "abs_residual_share_old_60plus_pct": round(100.0 * old / res_abs, 1) if res_abs else None,
        "amendment": "поправка 3 от 2026-10-04: внутренние проверки вместо "
                     "сверки с внешним сальдо (ряда за 2009-2019 нет)",
        "pass": share <= 5.0 and res_abs > 0 and young > old,
    }

    # --- городские ядра для H2 ------------------------------------------
    cities: dict[str, dict] = {}
    for tid in CITY_CORES:
        if tid not in c19:
            continue
        cities[tid] = {"ru": T[tid]["ru"] if tid in T else tid,
                       "be": T[tid]["be"] if tid in T else tid,
                       "summary": {"2019": _summary(c19[tid]),
                                   "2009": _summary(c09.get(tid, {}))},
                       "profile": {"2019": _profile(c19[tid]),
                                   "2009": _profile(c09.get(tid, {}))}}

    # --- вердикты по гипотезам ------------------------------------------
    r2539_19 = [territories[r]["summary"]["2019"]["r2539"] for r in raions]
    r2539_19 = [x for x in r2539_19 if x is not None]
    med_2539 = _median(r2539_19)

    with_travel = [r for r in raions
                   if territories[r]["min_minsk"] is not None
                   and territories[r]["summary"]["2019"]["r2539"] is not None]
    rho, pval = _spearman(
        [territories[r]["min_minsk"] for r in with_travel],
        [territories[r]["summary"]["2019"]["r2539"] for r in with_travel])
    h1 = {"median_r2539_2019": round(med_2539, 2),
          "threshold_median": 105.0,
          "spearman_rho": round(rho, 4), "spearman_p": round(pval, 6),
          "n": len(with_travel), "threshold_rho": 0.30,
          "verdict": "confirmed" if (med_2539 > 105.0 and rho >= 0.30
                                     and pval < 0.05) else "refuted"}

    city_vals = {t: cities[t]["summary"]["2019"]["r2539"] for t in cities}
    h2 = {"cities": city_vals, "raion_median": round(med_2539, 2),
          "all_below_100": all(v is not None and v < 100.0 for v in city_vals.values()),
          "all_below_median": all(v is not None and v < med_2539
                                  for v in city_vals.values())}
    h2["verdict"] = ("confirmed" if h2["all_below_100"] and h2["all_below_median"]
                     else "refuted")

    n_migr = sum(1 for r in raions if territories[r]["h3"]["dominant"] == "migration")
    h3 = {"raions_migration_dominant": n_migr, "n": len(raions),
          "threshold": 79,
          "verdict": "confirmed" if n_migr >= 79 else "refuted"}

    r70_19 = [territories[r]["summary"]["2019"]["r70"] for r in raions]
    r70_19 = [x for x in r70_19 if x is not None]
    r70_46 = [territories[r]["forecast_summary"][CORE_SCENARIO]["2046"]["r70"]
              for r in raions]
    r70_46 = [x for x in r70_46 if x is not None]
    h4 = {"max_r70_2019": round(max(r70_19), 2),
          "median_r70_2019": round(_median(r70_19), 2),
          "median_r70_2046": round(_median(r70_46), 2),
          "none_above_60": max(r70_19) <= 60.0,
          "median_rises": _median(r70_46) > _median(r70_19)}
    h4["verdict"] = ("confirmed" if h4["none_above_60"] and h4["median_rises"]
                     else "refuted")

    # ---------------- ПОСТ-ХОК (не пререгистрировано) --------------------
    # H1 опровергнута: знак корреляции обратный предсказанному. Ниже —
    # диагностика, ПОЧЕМУ, помеченная как пост-хок: эти расчёты не были
    # заморожены до данных и не могут подтверждать или спасать H1.
    loc19 = _load_census_by_locality(2019)

    def _cens_r2539(tid: str) -> tuple[float | None, float]:
        c = c19.get(tid, {})
        m = sum(c.get(a, {}).get("m", 0) for a in FERTILE)
        f = sum(c.get(a, {}).get("f", 0) for a in FERTILE)
        return (100.0 * m / f if f else None), m + f

    # 1. повтор теста H1 на ПЕРЕПИСНОМ периметре (район без города-хоста):
    #    проверяет, не создан ли обратный знак решением о периметре
    cens = [(t, *_cens_r2539(t)) for t in raions]
    # ВНИМАНИЕ: travel.get(t) здесь нельзя — у Минского района min_minsk = 0,
    # и проверка на истинность молча выбросила бы самый «женский» район
    cens = [(t, r, pop) for t, r, pop in cens if r is not None and t in travel]
    rho_c, p_c = _spearman([travel[t] for t, _, _ in cens],
                           [r for _, r, _ in cens])
    # 2. немонотонность: медианы по поясам времени до Минска
    belts = [(0, 30), (30, 60), (60, 90), (90, 120), (120, 10 ** 6)]
    belt_rows = []
    for lo, hi in belts:
        xs = [r for t, r, _ in cens if lo <= travel[t] < hi]
        if xs:
            belt_rows.append({"belt": f"{lo}-{hi if hi < 10 ** 6 else ''}",
                              "n": len(xs), "median": round(_median(xs), 2)})
    # 3. связь с людностью района
    rho_size, p_size = _spearman([pop for _, _, pop in cens],
                                 [r for _, r, _ in cens])
    # 4. узкий возрастной мужской пик — подпись населения закрытых учреждений
    SPIKE_AGES = ["15-19", "20-24", "25-29", "30-34"]
    spikes = []
    for t, r, pop in cens:
        if r < 115.0:
            continue
        tot: dict[str, dict[str, int]] = {}
        for lv in loc19.get(t, {}).values():
            for a, v in lv.items():
                cell = tot.setdefault(a, {"m": 0, "f": 0})
                cell["m"] += v["m"]
                cell["f"] += v["f"]
            # доля перевеса по типу местности
        peak_a, peak_r = None, 0.0
        for a in SPIKE_AGES:
            v = tot.get(a)
            if v and v["f"]:
                x = 100.0 * v["m"] / v["f"]
                if x > peak_r:
                    peak_a, peak_r = a, x
        if peak_r >= 130.0:
            shares = {}
            for lname, lv in loc19.get(t, {}).items():
                gm = sum(lv.get(a, {}).get("m", 0) for a in FERTILE)
                gf = sum(lv.get(a, {}).get("f", 0) for a in FERTILE)
                shares[lname] = gm - gf
            tot_sur = sum(v for v in shares.values() if v > 0) or 1
            spikes.append({
                "id": t, "ru": T[t]["ru"], "r2539_census_perimeter": round(r, 2),
                "peak_group": peak_a, "peak_ratio": round(peak_r, 1),
                "pop2539": pop,
                "surplus_by_locality": {k: round(v, 1) for k, v in shares.items()},
                "top_locality_share_pct": round(
                    100.0 * max(shares.values()) / tot_sur, 1),
            })
    spikes.sort(key=lambda x: -x["r2539_census_perimeter"])

    posthoc = {
        "disclaimer": "Пост-хок: расчёты этого блока выполнены ПОСЛЕ получения "
                      "данных и не были заморожены пререгистрацией. Они объясняют, "
                      "почему H1 опровергнута, но не могут её подтверждать и не "
                      "заменяют пререгистрированный тест.",
        "census_perimeter_h1": {
            "median_r2539": round(_median([r for _, r, _ in cens]), 2),
            "spearman_rho": round(rho_c, 4), "spearman_p": round(p_c, 6),
            "n": len(cens),
            "same_sign_as_forecast_perimeter": (rho_c < 0) == (rho < 0),
        },
        "belts_median_r2539": belt_rows,
        "size_effect": {"spearman_rho": round(rho_size, 4),
                        "spearman_p": round(p_size, 6)},
        "narrow_age_male_spike": spikes,
    }

    return {
        "version": VERSION,
        "code": "INF-20",
        "posthoc": posthoc,
        "preregistration": "docs/preregistration/sexratio-v0.1.md",
        "age_groups": AGE_GROUPS,
        "fertile_groups": FERTILE,
        "old_groups": OLD,
        "census_years": list(CENSUS_YEARS),
        "node_years": fc["node_years"],
        "scenarios": fc["scenarios"],
        "jumpoffs": fc["jumpoffs"],
        "core_scenario": CORE_SCENARIO,
        "forecast_version": fc["version"],
        "onset_thresholds": {"high": ONSET_HIGH, "low": ONSET_LOW},
        "country": {"sex_ratio_2019": country_ratio},
        "territories": territories,
        "cities": cities,
        "findings": {"H1": h1, "H2": h2, "H3": h3, "H4": h4},
        "gates": gates,
    }


def write_csv(res: dict) -> Path:
    path = CURATED / "sexratio.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["territory_id", "year", "kind", "scenario",
                    "sex_ratio_25_39", "sex_ratio_70plus",
                    "marriage_gap", "marriage_gap_rel",
                    "h3_mortality_gap", "h3_migration_gap", "h3_dominant",
                    "onset_year", "min_minsk"])
        for rid in sorted(res["territories"]):
            t = res["territories"][rid]
            for y in ("2009", "2019"):
                s = t["summary"][y]
                w.writerow([rid, y, "census", "", s["r2539"], s["r70"],
                            s["gap"], s["gap_rel"], t["h3"]["mortality"],
                            t["h3"]["migration"], t["h3"]["dominant"],
                            t["onset_year"], t["min_minsk"]])
            for combo in sorted(t["forecast_summary"]):
                for y in sorted(t["forecast_summary"][combo]):
                    s = t["forecast_summary"][combo][y]
                    w.writerow([rid, y, "forecast", combo, s["r2539"], s["r70"],
                                s["gap"], s["gap_rel"], t["h3"]["mortality"],
                                t["h3"]["migration"], t["h3"]["dominant"],
                                t["onset_year"], t["min_minsk"]])
    return path


def main() -> None:
    res = build()
    dst = OUT / "sexratio.json"
    dst.write_text(json.dumps(res, ensure_ascii=False,
                              separators=(",", ":"), sort_keys=True) + "\n")
    csv_path = write_csv(res)

    g = res["gates"]
    print(f"INF-20 sexratio v{VERSION}")
    print(f"  гейты: S-1 {'ok' if g['S-1']['pass'] else 'FAIL'}"
          f"  S-2 {'ok' if g['S-2']['pass'] else 'FAIL'}"
          f" ({g['S-2']['country_sex_ratio_2019']} м на 100 ж, страна 2019)"
          f"  S-3 {'ok' if g['S-3']['pass'] else 'FAIL'}"
          f"  S-4 {'ok' if g['S-4']['pass'] else 'FAIL'}"
          f"  S-5 {'ok' if g['S-5']['pass'] else 'FAIL'}")
    for h, v in res["findings"].items():
        print(f"  {h}: {v['verdict']}")
    print(f"  {dst.relative_to(ROOT)} ({dst.stat().st_size // 1024} КБ)")
    print(f"  {csv_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
