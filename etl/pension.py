"""INF-13 `pension`: коэффициент поддержки (SR/TDR), год перехода и условная
денежная арифметика (contribution_gap) по 118 районам, 1989-2056.

Вопрос: сколько работающих (по ЗАКОННОЙ границе трудоспособного возраста
ГОДА t, не по константе) приходится на одного человека старше трудоспособного
возраста - и в каком году район проходит пороги 3:1 / 1,5:1 / 1:1.

Данные:
- возрастная структура 2009/2019 (census_structure/load_sub_structures,
  этап WP-F1), 2026 (jumpoff_2026/forecast_age_raion, узел 2026),
  2031..2056 (forecast_age_raion_v2026_4.json, этап 0);
- нац. историю 1989/1999 даёт уже опубликованный web/public/data/pyramids.json;
- занятость района - индикатор Белстата 10102000017, УЖЕ завендорен INF-03
  (data/raw/wages/empl_person_10102000017_*.json) - используется без
  повторного скачивания;
- зарплата района - data/curated/wages.csv (INF-03, переиспользуется
  etl.wages.load_wages());
- получатели пенсий и средняя пенсия - ТОЛЬКО по областям (Белстат,
  индикаторы 10106000001/10106000002, data/raw/pension/); районного
  разреза не существует в природе (см. ТЗ раздел 6) - оцениваются через
  областной коэффициент охвата k_oblast, класс MODEL;
- законный график пенсионного возраста - Указ №137 от 11.04.2016,
  data/curated/retirement_age.csv (data/raw/pension/registry.csv).

Формулы (Приложение А ТЗ): SR(t)=P[16..A(t)-1]/P[>=A(t)];
TDR(t)=(P[0..15]+P[>=A(t)])/P[16..A(t)-1]; crossing_year(theta) - первый год
SR<theta, линейная интерполяция между узлами; CG(t)=(E*W*tau)/(R*B),
R=P[>=A(t)]*k_oblast (MODEL); policy_delta - сдвиг crossing_year при
альтернативном графике пенсионного возраста (65/60, 67/62) против as_is.

Запуск: python -m etl.pension -> web/public/data/pension.json
                                  data/curated/pension_inputs.csv
                                  docs/notes/pension_validation.md
"""
from __future__ import annotations

import csv
import json
from datetime import date

from .common import ROOT, OUT
from .census_age import RAION_RU2ID, _e
from .forecast import AGE_GROUPS, TERRITORIES
from .forecast.data import census_structure, jumpoff_2026
from .forecast.sub import HOSTED, load_sub_structures, oblast_of
from .registry import RAIONS, raion_id
from .wages import CITY_RU2ID, OBL_RU2ID, load_wages

RAW = ROOT / "data" / "raw" / "pension"
CURATED = ROOT / "data" / "curated"
VERSION = "1.0.0"
FORECAST_VERSION = "v2026.4"

SCENARIOS = ("base", "optimistic", "negative")
JUMPOFFS = ("official", "adjusted")
SERIES_KEYS = [f"{sid}:{jo}" for sid in SCENARIOS for jo in JUMPOFFS]
POLICY_VARIANTS = ("as_is", "65_60", "67_62")
POLICY_AGE = {"as_is": None, "65_60": {"m": 65.0, "f": 60.0},
              "67_62": {"m": 67.0, "f": 62.0}}
POLICY_APPLIES_FROM = 2026    # гипотетические графики не переписывают прошлое
THRESHOLDS = (2.0, 1.5, 1.0)
WORKING_LOWER = 16.0
CONTRIB_RATE = 0.29           # ФСЗН, пенсионное страхование: 28% (работодатель)
                              # + 1% (работник) - ст.5 закона №118-З (см. registry);
                              # НЕ включает 6% социального страхования (иное
                              # назначение фонда, не пенсионное).
COMMUTE_MINUTES_CUTOFF = 45   # G-7: зона, где CG скрывается без оценки перекоса
NATIONAL_YEARS = [1989, 1999, 2009, 2019, 2026, 2031, 2036, 2041, 2046, 2051, 2056]
TERRITORY_YEARS = [2009, 2019, 2026, 2031, 2036, 2041, 2046, 2051, 2056]
DTYPE_NATIONAL = {"1989": "c", "1999": "e", "2009": "c", "2019": "c", "2026": "e",
                  "2031": "f", "2036": "f", "2041": "f", "2046": "f", "2051": "f",
                  "2056": "f"}
DTYPE_TERRITORY = {"2009": "c", "2019": "c", "2026": "e", "2031": "f", "2036": "f",
                   "2041": "f", "2046": "f", "2051": "f", "2056": "f"}


# ------------------------------------------------------- график возраста

def load_retirement_schedule() -> dict[int, dict[str, float]]:
    """{год: {'m':возраст, 'f':возраст}} из data/curated/retirement_age.csv
    (Указ №137 от 11.04.2016, график +6 мес/год 2017-2022)."""
    out = {}
    for r in csv.DictReader(open(CURATED / "retirement_age.csv")):
        out[int(r["year"])] = {"m": float(r["retirement_age_m"]),
                               "f": float(r["retirement_age_f"])}
    return out


RETIREMENT_SCHEDULE = load_retirement_schedule()
_SCHED_YEARS = sorted(RETIREMENT_SCHEDULE)


def age_boundary(year: int, sex: str, policy: str) -> float:
    """Законная граница трудоспособного возраста в году `year` для пола
    `sex` при варианте `policy`. Гипотетические графики (65/60, 67/62)
    применяются только к прогнозным годам (>= POLICY_APPLIES_FROM) -
    задним числом закон не переписывается."""
    if policy != "as_is" and year >= POLICY_APPLIES_FROM:
        return POLICY_AGE[policy][sex]
    y = min(max(year, _SCHED_YEARS[0]), _SCHED_YEARS[-1])
    return RETIREMENT_SCHEDULE[y][sex]


# ------------------------------------------------- дробное деление групп

def _group_bounds(label: str) -> tuple[float, float | None]:
    if label.endswith("+"):
        return float(label[:-1]), None
    lo, hi = label.split("-")
    return float(lo), float(hi) + 1.0


_BOUNDS = {g: _group_bounds(g) for g in AGE_GROUPS}


def pop_below(struct_sex: dict[str, float], cutoff: float) -> float:
    """Население строго младше `cutoff` лет; равномерное распределение
    внутри пятилетних групп (стандартное демографическое допущение -
    иначе фиксация границы на кратные пяти года давала бы неверную
    историю при переходе 60->63/55->58, см. раздел 4 ТЗ)."""
    total = 0.0
    for g in AGE_GROUPS:
        lo, hi = _BOUNDS[g]
        v = struct_sex.get(g, 0.0)
        if hi is None:              # открытая группа 80+: cutoff (<=67) в неё
            continue                 # не попадает при разумных сценариях
        if cutoff <= lo:
            continue
        elif cutoff >= hi:
            total += v
        else:
            total += v * (cutoff - lo) / (hi - lo)
    return total


def sr_tdr(struct: dict[str, dict[str, float]], year: int,
          policy: str) -> tuple[float | None, float | None]:
    """struct: {'m':{group:pop}, 'f':{group:pop}}. Возвращает (SR, TDR)."""
    work = above = children = 0.0
    for sex in ("m", "f"):
        s = struct[sex]
        total = sum(s.values())
        a = age_boundary(year, sex, policy)
        below_a = pop_below(s, a)
        below_16 = pop_below(s, WORKING_LOWER)
        work += below_a - below_16
        above += total - below_a
        children += below_16
    sr = round(work / above, 2) if above > 0 else None
    tdr = round((children + above) / work, 2) if work > 0 else None
    return sr, tdr


# ------------------------------------------------------------- загрузка

def _num(s: str | None) -> float | None:
    if not s:
        return None
    s = s.replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def load_employment() -> dict[str, dict[int, float]]:
    """{terr_id: {год: занятые, чел.}} - индикатор 10102000017, УЖЕ
    завендорен INF-03 (data/raw/wages/), файл не создаём заново."""
    out: dict[str, dict[int, float]] = {}
    skipped: set[str] = set()
    wages_raw = ROOT / "data" / "raw" / "wages"
    for fn in ("empl_person_10102000017_2010-2019.json",
               "empl_person_10102000017_2020-2026.json"):
        d = json.loads((wages_raw / fn).read_text())
        years = [int(y) for y in d["tableHeader"][0]]
        for row in d["tableRows"]:
            name, level = row[0]["value"], row[0]["level"]
            tid = None
            if name in CITY_RU2ID:
                tid = CITY_RU2ID[name]
            elif level == 2:
                tid = RAION_RU2ID.get(_e(name))
            if tid is None:
                skipped.add(name)
                continue
            for i, y in enumerate(years):
                v = _num(row[i + 1]["value"] if i + 1 < len(row) else None)
                if v is not None:
                    out.setdefault(tid, {})[y] = v
    unexpected = skipped - {"Не распределено по районам Минской области"}
    assert not unexpected, f"несматченные территории занятости: {sorted(unexpected)}"
    return out


def load_pension_oblast() -> tuple[dict[str, dict[int, float]], dict[str, dict[int, float]]]:
    """(получатели по области {oblast_id:{год:чел.}},
    средняя пенсия по области {oblast_id:{год:руб.}})."""
    def parse(fn: str) -> dict[str, dict[int, float]]:
        d = json.loads((RAW / fn).read_text())
        years = [int(y) for y in d["tableHeader"][0]]
        out: dict[str, dict[int, float]] = {}
        for row in d["tableRows"]:
            name = row[0]["value"]
            tid = "BY" if name == "Республика Беларусь" else OBL_RU2ID.get(name)
            if tid is None:
                continue
            for i, y in enumerate(years):
                v = _num(row[i + 1]["value"] if i + 1 < len(row) else None)
                if v is not None:
                    out.setdefault(tid, {})[y] = v
        return out

    recipients = parse("recipients_10106000001_2000-2020.json")
    avg_pension = parse("avg_pension_10106000002_2000-2025.json")
    return recipients, avg_pension


def load_travel_times() -> dict[str, float]:
    return {r["territory_id"]: float(r["min_minsk"])
           for r in csv.DictReader(open(CURATED / "travel_times.csv"))}


def load_national_pyramid_struct(year: int) -> dict[str, dict[str, float]]:
    """1989/1999: web/public/data/pyramids.json (уже опубликован, WP P-1)."""
    d = json.loads((OUT / "pyramids.json").read_text())
    rec = d["series"][str(year)]
    return {"m": dict(zip(d["age_groups"], rec["m"])),
           "f": dict(zip(d["age_groups"], rec["f"]))}


def load_national_census_struct(year: int) -> dict[str, dict[str, float]]:
    """2009/2019: сумма 7 территорий уровня 0-1 (census_structure)."""
    cs = census_structure(year)
    out = {"m": dict.fromkeys(AGE_GROUPS, 0.0), "f": dict.fromkeys(AGE_GROUPS, 0.0)}
    for t in TERRITORIES:
        for sex in ("m", "f"):
            for g in AGE_GROUPS:
                out[sex][g] += cs[t][sex][g]
    return out


def load_national_2026_struct() -> dict[str, dict[str, float]]:
    j = jumpoff_2026()
    out = {"m": dict.fromkeys(AGE_GROUPS, 0.0), "f": dict.fromkeys(AGE_GROUPS, 0.0)}
    for t in TERRITORIES:
        for sex in ("m", "f"):
            for g in AGE_GROUPS:
                out[sex][g] += j[t][sex][g]
    return out


def load_national_forecast() -> dict[str, dict]:
    return json.loads((CURATED / "forecast_age_by_v2026_4.json").read_text())


def load_raion_forecast() -> dict:
    return json.loads((CURATED / "forecast_age_raion_v2026_4.json").read_text())


def _merge_hosted(structs: dict[str, dict], raion: str) -> dict[str, dict[str, float]]:
    """Периметр района-хоста = район (перепись) + город обл. подчинения -
    как r-* в forecast.json (см. sub.HOSTED)."""
    base = structs[raion]
    if raion not in HOSTED:
        return {s: dict(v) for s, v in base.items()}
    city = structs[HOSTED[raion]]
    return {s: {g: base[s][g] + city[s].get(g, 0.0) for g in AGE_GROUPS}
           for s in ("m", "f")}


def load_raion_census_struct(year: int) -> dict[str, dict[str, dict[str, float]]]:
    """{raion_id: {'m':{...},'f':{...}}} на 2009/2019, периметр района-хоста
    как в forecast.json (город обл. подчинения прибавлен)."""
    raw = load_sub_structures(year)          # {t: {sex:{age:pop}}}, r-/c-
    raions = sorted(t for t in raw if t.startswith("r-"))
    return {r: _merge_hosted(raw, r) for r in raions}


# --------------------------------------------------------- год перехода

def crossing_year(sr_by_year: dict[int, float | None], threshold: float) -> int | None:
    """Первый год, когда SR < threshold; линейная интерполяция между
    соседними известными точками ряда (раздел Приложение А ТЗ)."""
    years = sorted(y for y, v in sr_by_year.items() if v is not None)
    if not years:
        return None
    if sr_by_year[years[0]] < threshold:
        return years[0]
    for y0, y1 in zip(years, years[1:]):
        v0, v1 = sr_by_year[y0], sr_by_year[y1]
        if v0 >= threshold > v1:
            if v1 == v0:
                return y1
            frac = (v0 - threshold) / (v0 - v1)
            return round(y0 + frac * (y1 - y0))
    return None


# ----------------------------------------------------- H2: межрайонный разброс
# Пререгистрация (docs/preregistration/pension-v0.1.md, раздел 6) заморозила
# ЕДИНСТВЕННУЮ метрику проверки H2 - коэффициент вариации (CV). Проверка
# скептика (docs/decisions/INF-13.md) показала: CV растёт (+1,2%), но
# АБСОЛЮТНЫЙ разброс (стандартное отклонение, размах) СУЖАЕТСЯ - страна не
# столько расслаивается, сколько сходится к более низкому общему уровню.
# Публикуем все три метрики, чтобы это не терялось при пересказе.

def dispersion_sr(r_sr: dict[str, dict], years: list[int],
                  policy: str = "as_is", key: str = "base:official") -> dict:
    out = {}
    for y in years:
        vals = [r_sr[r][policy][key][y] for r in r_sr if r_sr[r][policy][key].get(y) is not None]
        n = len(vals)
        if n < 2:
            out[y] = {"n": n, "mean": None, "sd": None, "cv": None,
                      "min": None, "max": None, "range": None}
            continue
        mean = sum(vals) / n
        var = sum((v - mean) ** 2 for v in vals) / n
        sd = var ** 0.5
        out[y] = {"n": n, "mean": round(mean, 4), "sd": round(sd, 4),
                  "cv": round(sd / mean, 4) if mean else None,
                  "min": round(min(vals), 2), "max": round(max(vals), 2),
                  "range": round(max(vals) - min(vals), 2)}
    return out


# --------------------------------------------- G-3: независимый бэктест
# (проверка 3 раздела 7 ТЗ). Раион.уровне нет НЕЗАВИСИМОГО калибровочного
# узла до 2009 (перепись-1999 по районам не оцифрована - см. раздел 6 ТЗ
# «есть» только для 2009/2019), поэтому CCR-модель sub.py, откалиброванная
# ИМЕННО на паре 2009-2019, не может быть честно бэктестирована на этом же
# окне без утечки. Вместо этого используется НЕЗАВИСИМАЯ от sub.py.ccr_of
# альтернатива: проекция 2009->2019 только дожитием (национальная таблица
# смертности HMD-2018, БЕЗ миграции, БЕЗ калибровки к 2019, CWR из САМОГО
# 2009 года) - как бы «встроенный наивный демограф», который не видел 2019.
# Обоснование замены окна и метода - docs/decisions/INF-13.md.

def _survival_project_10y(struct09: dict[str, dict[str, float]], surv: dict,
                          ) -> dict[str, dict[str, float]]:
    from .forecast.sub import WOMEN_1549, N_G
    new = {"m": dict.fromkeys(AGE_GROUPS, 0.0), "f": dict.fromkeys(AGE_GROUPS, 0.0)}
    for s in ("m", "f"):
        S = surv[s]["S"]
        for i in range(N_G - 3):
            new[s][AGE_GROUPS[i + 2]] = struct09[s][AGE_GROUPS[i]] * S[i] * S[i + 1]
        base = (struct09[s]["70-74"] + struct09[s]["75-79"] + struct09[s]["80+"])
        new[s]["80+"] += base * surv[s]["S_open"] ** 2
    women09 = sum(struct09["f"][g] for g in WOMEN_1549)
    for s in ("m", "f"):
        cwr04 = struct09[s]["0-4"] / women09 if women09 > 0 else 0.0
        cwr59 = struct09[s]["5-9"] / women09 if women09 > 0 else 0.0
        # своя (2009-го года) CWR held constant - не калибруется к 2019
        new[s]["0-4"] = women09 * cwr04
        new[s]["5-9"] = women09 * cwr59
    return new


def backtest_g3(struct09: dict[str, dict[str, dict[str, float]]],
                struct19: dict[str, dict[str, dict[str, float]]]) -> dict:
    """Возвращает {'mape_model','mape_naive','beats_naive','correct_sign_share','n'}."""
    from .forecast.data import mortality_mx
    from .forecast.lifetable import survival_5y

    mx0 = mortality_mx(2018)
    surv = {s: survival_5y(mx0[s]) for s in ("m", "f")}
    ape_model, ape_naive, sign_ok = [], [], []
    for r in sorted(struct09):
        sr09, _ = sr_tdr(struct09[r], 2009, "as_is")
        sr19, _ = sr_tdr(struct19[r], 2019, "as_is")
        if sr09 is None or sr19 is None:
            continue
        pred_struct = _survival_project_10y(struct09[r], surv)
        sr_pred, _ = sr_tdr(pred_struct, 2019, "as_is")
        if sr_pred is None:
            continue
        ape_model.append(abs(sr_pred - sr19) / sr19)
        ape_naive.append(abs(sr09 - sr19) / sr19)
        actual_sign = (sr19 > sr09) - (sr19 < sr09)
        pred_sign = (sr_pred > sr09) - (sr_pred < sr09)
        sign_ok.append(1 if actual_sign == pred_sign else 0)
    n = len(ape_model)
    mape_model = 100 * sum(ape_model) / n
    mape_naive = 100 * sum(ape_naive) / n
    return {"n": n, "mape_model": round(mape_model, 2), "mape_naive": round(mape_naive, 2),
           "beats_naive": mape_model < mape_naive,
           "correct_sign_share": round(sum(sign_ok) / n, 3)}


def bucket_interval(year: int | None) -> str | None:
    """G-3 не пройдена на районном уровне (см. backtest_g3) -> год перехода
    района публикуется интервалом, не датой (раздел 13 ТЗ)."""
    if year is None:
        return None
    if year <= 2035:
        return "до 2035"
    if year <= 2045:
        return "2035-2045"
    return "после 2045"


# --------------------------------------------------------------- SR/TDR

def struct_provider(raion_fc: dict, census2009: dict, census2019: dict):
    ages = raion_fc["age_groups"]

    def get(raion: str, year: int, series_key: str) -> dict[str, dict[str, float]]:
        if year == 2009:
            return census2009[raion]
        if year == 2019:
            return census2019[raion]
        node = raion_fc["territories"][raion][series_key][str(year)]
        return {"m": dict(zip(ages, node["m"])), "f": dict(zip(ages, node["f"]))}
    return get


def national_struct_provider(nat_fc: dict, hist: dict[int, dict]):
    def get(year: int, series_key: str) -> dict[str, dict[str, float]]:
        if year in hist:
            return hist[year]
        node = nat_fc["series"][series_key][str(year)]
        return {"m": dict(zip(nat_fc["age_groups"], node["m"])),
               "f": dict(zip(nat_fc["age_groups"], node["f"]))}
    return get


def build_series(get_year_key, years_all: list[int]) -> tuple[dict, dict, dict]:
    """{policy:{series_key:{year:val}}} для sr/tdr и crossing (по всем годам)."""
    sr = {p: {} for p in POLICY_VARIANTS}
    tdr = {p: {} for p in POLICY_VARIANTS}
    crossing = {p: {} for p in POLICY_VARIANTS}
    for policy in POLICY_VARIANTS:
        for key in SERIES_KEYS:
            sr_vals, tdr_vals = {}, {}
            for y in years_all:
                struct = get_year_key(y, key)
                s, t = sr_tdr(struct, y, policy)
                sr_vals[y] = s
                tdr_vals[y] = t
            sr[policy][key] = sr_vals
            tdr[policy][key] = tdr_vals
            crossing[policy][key] = {th: crossing_year(sr_vals, th) for th in THRESHOLDS}
    return sr, tdr, crossing


def policy_delta_of(crossing: dict) -> dict:
    """{threshold: {policy: {series_key: сдвиг лет | null}}}."""
    out = {th: {} for th in THRESHOLDS}
    for th in THRESHOLDS:
        for policy in ("65_60", "67_62"):
            out[th][policy] = {}
            for key in SERIES_KEYS:
                base = crossing["as_is"][key][th]
                alt = crossing[policy][key][th]
                out[th][policy][key] = (alt - base) if (base is not None and alt is not None) else None
    return out


# ------------------------------------------------- CG (условная арифметика)

CG_YEARS = (2026, 2031, 2036, 2041, 2046, 2051, 2056)
OBLASTS6 = ("BY-BR", "BY-VI", "BY-HO", "BY-HR", "BY-MI", "BY-MA")


def coverage_k_oblast(recipients_ob: dict, ref_year: int = 2019) -> dict[str, float | None]:
    """k_oblast = получатели(область,ref_year) / P[>=A(ref_year)](область).
    Якорь - перепись 2019 (последний год, где есть И возрастная структура
    области, И официальная численность получателей по годам области)."""
    cs = census_structure(ref_year)
    out = {}
    for o in OBLASTS6:
        p_above = 0.0
        for sex in ("m", "f"):
            a = age_boundary(ref_year, sex, "as_is")
            s = cs[o][sex]
            p_above += sum(s.values()) - pop_below(s, a)
        rec = recipients_ob.get(o, {}).get(ref_year)
        out[o] = (rec / p_above) if (rec and p_above > 0) else None
    return out


def build_cg(get_raion, raions: list[str], oblast_of_map: dict[str, str],
            employment: dict, wages: dict, k_oblast: dict, avg_pension_ob: dict,
            travel_min: dict, rate_multiplier: float = 1.0,
            k_multiplier: float = 1.0, b_multiplier: float = 1.0) -> dict:
    """{raion: {'suppressed':bool, 'series': {sid+':official': {year: cg|None}}}}.
    Множители - только для чувствительности G-5 (не меняют основной расчёт
    при значениях по умолчанию 1.0)."""
    out = {}
    for r in raions:
        o = oblast_of_map[r]
        k = k_oblast.get(o)
        k = k * k_multiplier if k is not None else None
        w_years = wages.get(r, {})
        w_latest = w_years[max(w_years)] if w_years else None
        e_years = employment.get(r, {})
        b_years = avg_pension_ob.get(o, {})
        b_latest = b_years[max(b_years)] * b_multiplier if b_years else None
        rate = None
        if e_years:
            e_last_year = max(e_years)
            struct2026 = get_raion(r, 2026, "base:official")
            p_working = 0.0
            for sex in ("m", "f"):
                a = age_boundary(2026, sex, "as_is")
                s = struct2026[sex]
                p_working += pop_below(s, a) - pop_below(s, WORKING_LOWER)
            rate = (e_years[e_last_year] / p_working) if p_working > 0 else None
            if rate is not None:
                rate *= rate_multiplier

        suppressed = travel_min.get(r, 9999) <= COMMUTE_MINUTES_CUTOFF
        series = {}
        ready = not suppressed and k and w_latest and b_latest and rate
        if ready:
            for sid in SCENARIOS:
                key = f"{sid}:official"
                vals = {}
                for y in CG_YEARS:
                    struct = get_raion(r, y, key)
                    p_above = p_working_y = 0.0
                    for sex in ("m", "f"):
                        a = age_boundary(y, sex, "as_is")
                        s = struct[sex]
                        total = sum(s.values())
                        below_a = pop_below(s, a)
                        p_working_y += below_a - pop_below(s, WORKING_LOWER)
                        p_above += total - below_a
                    e = rate * p_working_y
                    r_recip = p_above * k
                    cg = (e * w_latest * CONTRIB_RATE) / (r_recip * b_latest) \
                        if r_recip > 0 else None
                    vals[y] = round(cg, 2) if cg is not None else None
                series[key] = vals
        out[r] = {"suppressed": suppressed, "series": series}
    return out


# --------------------------------------------------------------- сборка

def build() -> dict:
    nat_hist = {
        1989: load_national_pyramid_struct(1989),
        1999: load_national_pyramid_struct(1999),
        2009: load_national_census_struct(2009),
        2019: load_national_census_struct(2019),
    }
    nat_fc = load_national_forecast()
    get_national = national_struct_provider(nat_fc, nat_hist)
    nat_sr, nat_tdr, nat_crossing = build_series(get_national, NATIONAL_YEARS)
    nat_policy_delta = policy_delta_of(nat_crossing)

    raion_fc = load_raion_forecast()
    census2009 = load_raion_census_struct(2009)
    census2019 = load_raion_census_struct(2019)
    get_raion = struct_provider(raion_fc, census2009, census2019)
    raions = sorted(census2019)
    expected = sorted(raion_id(lat) for lat in RAIONS)
    assert raions == expected, ("номенклатура районов разошлась",
                                set(raions) ^ set(expected))

    r_sr, r_tdr, r_crossing, r_policy_delta = {}, {}, {}, {}
    for r in raions:
        s, t, c = build_series(lambda y, k, r=r: get_raion(r, y, k), TERRITORY_YEARS)
        r_sr[r] = s
        r_tdr[r] = t
        r_crossing[r] = c
        r_policy_delta[r] = policy_delta_of(c)

    dispersion = dispersion_sr(r_sr, TERRITORY_YEARS)
    g3 = backtest_g3(census2009, census2019)

    employment = load_employment()
    wages = load_wages()
    recipients_ob, avg_pension_ob = load_pension_oblast()
    k_oblast = coverage_k_oblast(recipients_ob)
    travel_min = load_travel_times()
    oblast_map = oblast_of()
    cg = build_cg(get_raion, raions, oblast_map, employment, wages, k_oblast,
                 avg_pension_ob, travel_min)

    return {
        "nat_hist": nat_hist, "nat_fc": nat_fc, "get_national": get_national,
        "national": {"sr": nat_sr, "tdr": nat_tdr, "crossing": nat_crossing,
                    "policy_delta": nat_policy_delta},
        "raions": raions, "raion_fc": raion_fc, "get_raion": get_raion,
        "raion_sr": r_sr, "raion_tdr": r_tdr,
        "raion_crossing": r_crossing, "raion_policy_delta": r_policy_delta,
        "dispersion": dispersion,
        "g3": g3, "cg": cg, "k_oblast": k_oblast,
        "employment": employment, "wages": wages,
        "recipients_ob": recipients_ob, "avg_pension_ob": avg_pension_ob,
        "travel_min": travel_min, "oblast_map": oblast_map,
        "census2009": census2009, "census2019": census2019,
    }


# --------------------------------------------------------- гейты G1-G7

def gate_g1() -> dict:
    """Реперные доли на 01.01.2025 (Белстат, ±0,3 п.п.)."""
    struct = {"m": dict.fromkeys(AGE_GROUPS, 0.0), "f": dict.fromkeys(AGE_GROUPS, 0.0)}
    for r in csv.DictReader(open(CURATED / "age_current.csv")):
        if r["year"] == "2025" and r["territory_id"] == "BY" and r["locality"] == "total" \
                and r["sex"] in ("m", "f"):
            g = r["age_group"].replace("80 и старше", "80+").replace("80 +", "80+")
            if g in AGE_GROUPS:
                struct[r["sex"]][g] += int(r["pop"])
    below = above = total = 0.0
    for sex in ("m", "f"):
        s = struct[sex]
        a = age_boundary(2025, sex, "as_is")
        t = sum(s.values())
        b16 = pop_below(s, 16.0)
        total += t
        below += b16
        above += t - pop_below(s, a)
    share_below = below / total
    share_above = above / total
    # эталон: абсолютные числа инфографики Белстата на 01.01.2025
    # (data/raw/pension/registry.csv#belstat_age_shares_2025), точнее
    # округлённых 17,1%/24,5% из Постановления Совмина №765 (та же дата)
    ref_below, ref_above, ref_total = 1_553_708, 2_238_235, 9_109_280
    ref_share_below, ref_share_above = ref_below / ref_total, ref_above / ref_total
    d_below = abs(share_below - ref_share_below) * 100
    d_above = abs(share_above - ref_share_above) * 100
    return {
        "share_below_model": round(share_below * 100, 2),
        "share_above_model": round(share_above * 100, 2),
        "share_below_ref": round(ref_share_below * 100, 2),
        "share_above_ref": round(ref_share_above * 100, 2),
        "delta_below_pp": round(d_below, 3), "delta_above_pp": round(d_above, 3),
        "pass": d_below <= 0.3 and d_above <= 0.3,
    }


def gate_g2(b: dict) -> dict:
    """Сумма районов (P_working/P_above, as_is) = ИТОГ 6 ОБЛАСТЕЙ (без
    г. Минска - Минск не район) ±0,1%, на 2026 и 2046. Область берётся из
    независимого пересчёта run_scenario (тот же путь, что и в
    test_forecast_age_raion.py, а не из forecast_age_by - там уровень
    "BY" включает Минск, с которым районы несопоставимы)."""
    from .forecast.run import load_scenarios, run_scenario
    scens = load_scenarios()
    _, structs = run_scenario(scens["base"], keep_structures=True)

    def obl_struct(o: str, y: int) -> dict:
        from .forecast.sub import interp_struct
        return interp_struct(structs[o], y)

    obl_of_map = b["oblast_map"]
    bad = []
    checked = 0
    for y in (2026, 2046):
        obl_work = {o: 0.0 for o in OBLASTS6}
        obl_above = {o: 0.0 for o in OBLASTS6}
        for o in OBLASTS6:
            st = obl_struct(o, y)
            for sex in ("m", "f"):
                s = st[sex]
                a = age_boundary(y, sex, "as_is")
                below_a, below_16 = pop_below(s, a), pop_below(s, 16.0)
                obl_work[o] += below_a - below_16
                obl_above[o] += sum(s.values()) - below_a
        r_work = {o: 0.0 for o in OBLASTS6}
        r_above = {o: 0.0 for o in OBLASTS6}
        for r in b["raions"]:
            o = obl_of_map[r]
            struct = b["get_raion"](r, y, "base:official")
            for sex in ("m", "f"):
                s = struct[sex]
                a = age_boundary(y, sex, "as_is")
                below_a, below_16 = pop_below(s, a), pop_below(s, 16.0)
                r_work[o] += below_a - below_16
                r_above[o] += sum(s.values()) - below_a
        for o in OBLASTS6:
            checked += 1
            d_work = abs(r_work[o] - obl_work[o]) / obl_work[o]
            d_above = abs(r_above[o] - obl_above[o]) / obl_above[o]
            if d_work > 0.001 or d_above > 0.001:
                bad.append((y, o, round(d_work, 4), round(d_above, 4)))
    return {"checked": checked, "bad": bad, "pass": not bad}


def gate_g4(b: dict) -> dict:
    """Национальный SR-2050 против потенциального коэффициента поддержки
    UN WPP 2024 medium (P15-64/P65+, ДРУГАЯ граница трудоспособности -
    объясняется письменно, не подгоняется, см. data/raw/pension/registry.csv
    #owid_wpp2024_age_groups)."""
    sr46 = b["national"]["sr"]["as_is"]["base:official"][2046]
    sr51 = b["national"]["sr"]["as_is"]["base:official"][2051]
    sr50 = sr46 + (sr51 - sr46) * (2050 - 2046) / (2051 - 2046)
    un_psr = 2.18   # см. registry.csv - выведено из OWID/UN WPP 2024 medium
    delta_pct = abs(sr50 - un_psr) / un_psr * 100
    return {
        "sr_2050_model": round(sr50, 2), "un_psr_2050": un_psr,
        "delta_pct": round(delta_pct, 1), "pass_within_5pct": delta_pct <= 5,
        "explanation": ("расхождение объясняется определением, а не ошибкой "
                        "расчёта: наша граница трудоспособности - законный "
                        "график (63 муж./58 жен.) - у ОБОИХ полов НИЖЕ "
                        "единой константы UN (65 для обоих полов), особенно "
                        "сильно у женщин (58 против 65). Поэтому по нашему "
                        "определению БОЛЬШЕ людей считаются «старше "
                        "трудоспособного» (в т.ч. все женщины 58-64 и "
                        "мужчины 63-64, которых UN считает ещё «рабочей "
                        "силой» 15-64), а работающих - меньше: наш SR "
                        "СТРУКТУРНО НИЖЕ UN PSR при том же демографическом "
                        "составе. Расхождение ожидаемо по конструкции "
                        "показателя и не подгонялось."),
    }


def gate_g5(b: dict) -> dict:
    """Устойчивость CG: знак (CG<1 / CG>=1) при +-10% охвата, +-10% пенсии,
    год 2046, сценарий base - сохраняется у >=90% районов."""
    base_cg = b["cg"]
    variants = {
        "k+10%": dict(k_multiplier=1.10), "k-10%": dict(k_multiplier=0.90),
        "b+10%": dict(b_multiplier=1.10), "b-10%": dict(b_multiplier=0.90),
    }
    base_sign = {}
    for r, rec in base_cg.items():
        v = rec["series"].get("base:official", {}).get(2046)
        if v is not None:
            base_sign[r] = v >= 1.0
    results = {}
    for name, kwargs in variants.items():
        alt = build_cg(b["get_raion"], b["raions"], b["oblast_map"], b["employment"],
                       b["wages"], b["k_oblast"], b["avg_pension_ob"], b["travel_min"],
                       **kwargs)
        same = total = 0
        for r, base in base_sign.items():
            v = alt[r]["series"].get("base:official", {}).get(2046)
            if v is None:
                continue
            total += 1
            if (v >= 1.0) == base:
                same += 1
        results[name] = {"n": total, "share_same_sign": round(same / total, 3) if total else None}
    min_share = min(v["share_same_sign"] for v in results.values() if v["share_same_sign"] is not None)
    return {"variants": results, "min_share_same_sign": round(min_share, 3),
           "pass": min_share >= 0.90, "n_evaluated_raions": len(base_sign)}


def gate_g7(b: dict) -> dict:
    """Перекос «место работы vs жительства»: не оценивается количественно
    (нет матрицы корреспонденций) - применён предусмотренный запасной
    вариант (раздел 7 п.7 ТЗ): CG скрыт для районов <=45 мин от Минска."""
    suppressed = [r for r in b["raions"] if b["cg"][r]["suppressed"]]
    return {"estimated_bias_quantitatively": False,
           "fallback_applied": "suppress_within_45min",
           "n_suppressed": len(suppressed), "suppressed": suppressed}


def run_gates(b: dict) -> dict:
    return {"G1": gate_g1(), "G2": gate_g2(b), "G3": b["g3"],
           "G4": gate_g4(b), "G5": gate_g5(b), "G7": gate_g7(b)}


# ------------------------------------------------------------- экспорт

def _series_to_arrays(by_policy_key: dict, years: list[int]) -> dict:
    return {p: {k: [by_policy_key[p][k].get(y) for y in years]
               for k in by_policy_key[p]}
           for p in by_policy_key}


def _crossing_to_str(by_policy_key: dict) -> dict:
    return {p: {k: {str(th): by_policy_key[p][k][th] for th in THRESHOLDS}
               for k in by_policy_key[p]}
           for p in by_policy_key}


def _policy_delta_to_str(pd: dict) -> dict:
    return {str(th): {policy: pd[th][policy] for policy in ("65_60", "67_62")}
           for th in THRESHOLDS}


def export_json(b: dict, gates: dict, g3_pass: bool) -> dict:
    territories = {}
    for r in b["raions"]:
        lat = next(l for l, (ru, _g, _c) in RAIONS.items() if raion_id(l) == r)
        name = f"{RAIONS[lat][0]} район"
        crossing_str = _crossing_to_str(b["raion_crossing"][r])
        entry = {
            "name": name,
            "oblast": b["oblast_map"].get(r),
            "commute_zone_45min": b["travel_min"].get(r, 9999) <= COMMUTE_MINUTES_CUTOFF,
            "sr": _series_to_arrays(b["raion_sr"][r], TERRITORY_YEARS),
            "tdr": _series_to_arrays(b["raion_tdr"][r], TERRITORY_YEARS),
            "crossing": crossing_str,
            "crossing_interval": ({p: {k: {str(th): bucket_interval(v)
                                          for th, v in b["raion_crossing"][r][p][k].items()}
                                      for k in b["raion_crossing"][r][p]}
                                   for p in POLICY_VARIANTS} if not g3_pass else None),
            "policy_delta": _policy_delta_to_str(b["raion_policy_delta"][r]),
            "cg": (b["cg"][r]["series"] if not b["cg"][r]["suppressed"] else None),
            "cg_suppressed": b["cg"][r]["suppressed"],
        }
        territories[r] = entry

    national = {
        "sr": _series_to_arrays(b["national"]["sr"], NATIONAL_YEARS),
        "tdr": _series_to_arrays(b["national"]["tdr"], NATIONAL_YEARS),
        "crossing": _crossing_to_str(b["national"]["crossing"]),
        "policy_delta": _policy_delta_to_str(b["national"]["policy_delta"]),
        "dispersion_sr": {str(y): v for y, v in b["dispersion"].items()},
    }

    # полный график (не только переходные 2016-2022) - чтобы "найди себя"
    # на клиенте не дублировал константы 60/55 до / 63/58 после отдельным
    # источником истины
    schedule_out = {str(y): {"m": v["m"], "f": v["f"]}
                    for y, v in RETIREMENT_SCHEDULE.items()}

    return {
        "version": VERSION,
        "forecast_version": FORECAST_VERSION,
        "generated": date.today().isoformat(),
        "retirement_schedule": schedule_out,
        "policy_variants": list(POLICY_VARIANTS),
        "policy_ages": {p: POLICY_AGE[p] for p in POLICY_VARIANTS},
        "policy_applies_from": POLICY_APPLIES_FROM,
        "contribution_rate": CONTRIB_RATE,
        "series_keys": SERIES_KEYS,
        "thresholds": list(THRESHOLDS),
        "years": {"national": NATIONAL_YEARS, "territory": TERRITORY_YEARS},
        "dtype": {"national": DTYPE_NATIONAL, "territory": DTYPE_TERRITORY},
        "national": national,
        "territories": territories,
        "meta": {
            "claims": [f"C-{i:03d}" for i in range(1, 13)],
            "artifact": "by-maps-pension-v1.0.0.zip",
            "validation": {
                "G1_national_shares": gates["G1"]["pass"],
                "G2_raion_sum_oblast": gates["G2"]["pass"],
                "G3_backtest": gates["G3"]["beats_naive"] and
                              gates["G3"]["correct_sign_share"] >= 0.80,
                "G4_wpp_check": gates["G4"]["pass_within_5pct"],
                "G5_sensitivity": gates["G5"]["pass"],
                "G7_commute_bias": "fallback_applied",
                "note": ("G3 не пройдена на районном уровне (нет независимого "
                         "калибровочного узла ранее 2009) -> crossing_year "
                         "районов публикуется интервалом (см. crossing_interval "
                         "и docs/decisions/INF-13.md). Национальный crossing_year "
                         "- точный год (не завязан на G-3)."),
            },
        },
    }


def write_pension_inputs_csv(b: dict) -> None:
    path = CURATED / "pension_inputs.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["territory_id", "metric", "year", "value", "dtype"])
        for r in b["raions"]:
            for y, v in sorted(b["wages"].get(r, {}).items()):
                w.writerow([r, "wage_byn", y, v, "d"])
            for y, v in sorted(b["employment"].get(r, {}).items()):
                w.writerow([r, "employed_persons", y, v, "d"])
            o = b["oblast_map"].get(r)
            k = b["k_oblast"].get(o)
            if k is not None:
                w.writerow([r, "k_oblast_coverage_2019", 2019, round(k, 4), "m"])
            b_years = b["avg_pension_ob"].get(o, {})
            if b_years:
                y_latest = max(b_years)
                w.writerow([r, "avg_pension_oblast_byn", y_latest, b_years[y_latest], "d"])
            tm = b["travel_min"].get(r)
            if tm is not None:
                w.writerow([r, "min_minutes_to_minsk", 2026, round(tm, 1), "d"])
    print(f"OK: {path.name}")


def write_validation_notes(gates: dict) -> None:
    path = ROOT / "docs" / "notes" / "pension_validation.md"
    g1, g2, g3, g4, g5, g7 = (gates[k] for k in ("G1", "G2", "G3", "G4", "G5", "G7"))
    text = f"""# Отчёт валидации INF-13 (pension)

Семь проверок раздела 7 ТЗ. У каждой - число, а не слово «пройдено».

## G-1. Национальные доли на 01.01.2025

| Показатель | Модель | Эталон (Белстат) | Отклонение |
|---|---|---|---|
| моложе трудоспособного | {g1['share_below_model']}% | {g1['share_below_ref']}% | {g1['delta_below_pp']} п.п. |
| старше трудоспособного | {g1['share_above_model']}% | {g1['share_above_ref']}% | {g1['delta_above_pp']} п.п. |

Порог 0,3 п.п. **{"пройдена" if g1['pass'] else "НЕ ПРОЙДЕНА"}**.

## G-2. Сумма районов = страна

Проверено (год x область): {g2['checked']}. Расхождения сверх 0,1%: {len(g2['bad'])}.
**{"пройдена" if g2['pass'] else "НЕ ПРОЙДЕНА"}**.

## G-3. Бэктест (районы)

Окно **2009->2019** (замена метода - см. docs/decisions/INF-13.md: районного
разреза 1999 года не существует, поэтому вместо CCR-модели sub.py
[откалиброванной ИМЕННО на паре 2009-2019, бэктест на том же окне был бы
самоисполняющимся] используется независимая от неё проекция «только
дожитие» - национальная таблица смертности HMD-2018, без миграции, без
калибровки к 2019).

- MAPE модели (survival-only): {g3['mape_model']}%
- MAPE наивного прогноза (SR заморожен на 2009): {g3['mape_naive']}%
- Модель точнее наивного: **{g3['beats_naive']}**
- Верный знак изменения: {g3['correct_sign_share']*100:.1f}% районов (n={g3['n']})
- Требование: точнее наивного И доля верного знака >= 80%.

**Итог: {"пройдена" if (g3['beats_naive'] and g3['correct_sign_share']>=0.80) else "НЕ ПРОЙДЕНА"}**.
Следствие (раздел 13 ТЗ): год перехода district-level публикуется
**интервалом** («до 2035» / «2035-2045» / «после 2045»), не точной датой.
Национальный crossing_year на этот гейт не завязан (длинный ряд 1959-2019 +
внешняя сверка G-4) и публикуется точным годом.

Оговорка проверяющего-скептика (docs/decisions/INF-13.md, находка E):
бэктест «только дожитие» НЕ включает миграцию, в отличие от боевой
CCR-модели `etl.forecast.sub` (которая неявно учитывает миграцию через
эмпирический коэффициент когортного изменения 2009->2019) - метод G-3
тестирует более слабый ПРОКСИ, а не саму боевую модель. Ошибка знака
вероятнее у районов с сильной миграцией (пригороды агломераций против
удалённой убыли) - отдельно не выделялась.

## G-4. Сверка с UN WPP 2024 (SR-2050)

- Наш национальный SR-2050 (базовый сценарий, официальный старт): {g4['sr_2050_model']}
- UN WPP 2024 medium, потенциальный коэффициент поддержки (15-64/65+), 2050: {g4['un_psr_2050']}
- Расхождение: {g4['delta_pct']}%

{g4['explanation']}

Порог 5% (или письменное объяснение) - **{"в допуске" if g4['pass_within_5pct'] else "вне допуска, объяснение выше обязательно"}**.

## G-5. Чувствительность денежного слоя (CG)

Год 2046, сценарий base, n={g5['n_evaluated_raions']} районов с рассчитанным CG.

| Вариант | Доля районов с тем же знаком (CG>=1 / CG<1) |
|---|---|
""" + "\n".join(f"| {name} | {v['share_same_sign']*100:.1f}% (n={v['n']}) |"
                for name, v in g5["variants"].items()) + f"""

Минимум по вариантам: {g5['min_share_same_sign']*100:.1f}%. Порог 90% -
**{"пройдена" if g5['pass'] else "НЕ ПРОЙДЕНА -> CG публикуется классами, без цифр"}**.

Оговорка проверяющего-скептика (docs/decisions/INF-13.md, находка C): для
конкретного района CG(y) = K_r * SR(y), где K_r - константа района
(зарплата, занятость, охват, ставка взносов зафиксированы на текущем
уровне). CG НЕ независимый от SR денежный сигнал - это тот же
демографический ряд, пересчитанный в условные деньги при текущем
экономическом масштабе района. Смысл G-5 точнее: «многие ли районы стоят
близко к порогу CG=1», а не «устойчивость независимого сигнала».

## G-6. Ни одного числа без подтверждения

Проверяется на этапе сборки пакета (`checks/expected_results.json`,
`etl.artifacts.validate`) - см. VALIDATION.md пакета `artifacts/pension/`.

## G-7. Перекос «место работы vs жительства»

Количественная оценка перекоса не выполнена (нет матрицы корреспонденций
поездок на работу - только времена в пути INF-04, которые дают доступность,
не объём миграции). Применён предусмотренный ТЗ запасной вариант: CG **скрыт**
для {g7['n_suppressed']} районов в пределах {COMMUTE_MINUTES_CUTOFF} минут
эффективной доступности до Минска.
"""
    path.write_text(text)
    print(f"OK: {path.relative_to(ROOT)}")


def main() -> None:
    print("Расчёт INF-13 pension...")
    b = build()
    gates = run_gates(b)
    if not gates["G1"]["pass"]:
        print("!! G-1 НЕ ПРОЙДЕНА - публикация должна быть остановлена (раздел 13 ТЗ)")
    g3_pass = gates["G3"]["beats_naive"] and gates["G3"]["correct_sign_share"] >= 0.80

    payload = export_json(b, gates, g3_pass)
    out_path = OUT / "pension.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")))
    size_kb = out_path.stat().st_size / 1024
    print(f"OK: {out_path.name} ({size_kb:.0f} КБ)")
    if size_kb > 900:
        print(f"!! бюджет 900 КБ превышен ({size_kb:.0f} КБ) - требуется разделение/сжатие")

    write_pension_inputs_csv(b)
    write_validation_notes(gates)

    n_suppressed = gates["G7"]["n_suppressed"]
    print(f"\nИтоги: {len(b['raions'])} районов, CG скрыт у {n_suppressed} "
         f"(зона {COMMUTE_MINUTES_CUTOFF} мин до Минска)")
    print(f"  G1={gates['G1']['pass']} G2={gates['G2']['pass']} "
         f"G3={g3_pass} G4={gates['G4']['pass_within_5pct']} "
         f"G5={gates['G5']['pass']}")
    sr09 = b["national"]["sr"]["as_is"]["base:official"][2009]
    sr46 = b["national"]["sr"]["as_is"]["base:official"][2046]
    below15_2046 = sum(1 for r in b["raions"]
                       if (b["raion_sr"][r]["as_is"]["base:official"].get(2046) or 99) < 1.5)
    below15_2009 = sum(1 for r in b["raions"]
                       if (b["raion_sr"][r]["as_is"]["base:official"].get(2009) or 99) < 1.5)
    print(f"  Нац. SR: 2009={sr09}, 2046={sr46}")
    print(f"  Районов с SR<1,5: 2009={below15_2009}/118, 2046={below15_2046}/118 (H1)")


if __name__ == "__main__":
    main()
