"""Загрузка входов прогноза из data/curated и data/raw."""
from __future__ import annotations

import csv
from functools import lru_cache

from ..common import ROOT
from . import TERRITORIES, AGE_GROUPS, FERTILE

CURATED = ROOT / "data" / "curated"
RAW = ROOT / "data" / "raw"


def _norm_age(a: str) -> str:
    a = a.strip()
    if a in ("80 и старше", "80+", "80 +", "85 и старше", "85+", "85 +"):
        return "80+"  # верхняя открытая группа движка
    return a


@lru_cache(maxsize=None)
def jumpoff_2026() -> dict:
    """Стартовые структуры на 01.01.2026: {terr: {sex: {age_group: pop}}}.

    Верхняя группа источников - открытая «80+» (как и в движке)."""
    out = {t: {"m": dict.fromkeys(AGE_GROUPS, 0.0), "f": dict.fromkeys(AGE_GROUPS, 0.0)}
           for t in TERRITORIES}
    for r in csv.DictReader(open(CURATED / "age_current.csv")):
        if (r["year"] == "2026" and r["territory_id"] in out
                and r["sex"] in ("m", "f") and r["locality"] == "total"):
            t, s = r["territory_id"], r["sex"]
            age = _norm_age(r["age_group"])
            if age in out[t][s]:
                out[t][s][age] += int(r["pop"])
    return out


@lru_cache(maxsize=None)
def census_structure(year: int) -> dict:
    """Структуры переписи (2009/2019) по областям: {terr: {sex: {age: pop}}}."""
    out = {t: {"m": dict.fromkeys(AGE_GROUPS, 0), "f": dict.fromkeys(AGE_GROUPS, 0)}
           for t in TERRITORIES}
    for r in csv.DictReader(open(CURATED / f"age{year}.csv")):
        if r["territory_id"] in out and r["sex"] in ("m", "f"):
            age = _norm_age(r["age_group"])
            if age in out[r["territory_id"]][r["sex"]]:  # 'Возраст не определен' - 0 записей
                out[r["territory_id"]][r["sex"]][age] += int(r["pop"])
    return out


@lru_cache(maxsize=None)
def mortality_mx(year: int = 2018) -> dict:
    """Однолетние mx из HMD: {sex: [mx_0 .. mx_109]}."""
    mx = {"m": [0.0] * 110, "f": [0.0] * 110}
    col = {"male": "m", "female": "f"}
    for r in csv.DictReader(open(CURATED / "mortality.csv")):
        if int(r["year"]) == year and r["sex"] in col and r["type"] == "period":
            age = r["age"]
            # в файле есть и однолетние, и агрегированные группы ('1-4') - берём 1x1
            if age == "110+":
                a = 109
            elif age.isdigit():
                a = int(age)
            else:
                continue
            if a <= 109 and r["central_death_rate"]:
                # в зеркале OWID коэффициенты даны на 1000 человек
                mx[col[r["sex"]]][a] = float(r["central_death_rate"]) / 1000.0
    return mx


@lru_cache(maxsize=None)
def asfr_profile(year: int = 2018) -> dict:
    """Областные ASFR (на 1000 женщин): {terr: {age_group: asfr}} и СКР."""
    prof = {}
    tfr = {}
    for r in csv.DictReader(open(CURATED / "fertility_oblast.csv")):
        if int(r["year"]) == year:
            prof.setdefault(r["oblast"], {})[
                "15-19" if r["age_group"] == "15-19" else r["age_group"]] = float(r["asfr"])
            tfr[r["oblast"]] = float(r["tfr"])
    return {"asfr": prof, "tfr": tfr}


@lru_cache(maxsize=None)
def migration_matrix(year: int) -> dict:
    """Межобластная матрица (переписной поток): {origin: {dest: {age: n}}}."""
    out = {}
    for r in csv.DictReader(open(CURATED / "migration_internal.csv")):
        if int(r["year"]) == year:
            age = _norm_age(r["age_group"])
            out.setdefault(r["origin_oblast"], {}).setdefault(
                r["dest_oblast"], {})[age] = int(r["migrants"])
    return out


@lru_cache(maxsize=None)
def wpp_indicators() -> list[dict]:
    return list(csv.DictReader(open(RAW / "wpp2024" / "blr_indicators_medium.csv")))


@lru_cache(maxsize=None)
def wpp_total_variants() -> dict:
    """{variant: {year: pop_thousands}}."""
    out = {}
    for r in csv.DictReader(open(RAW / "wpp2024" / "blr_total_all_variants.csv")):
        out.setdefault(r["Variant"], {})[int(r["Time"])] = float(r["PopTotal"])
    return out


def wpp_trajectory(column: str) -> dict[int, float]:
    """Траектория показателя WPP Medium по годам (2024-2100)."""
    return {int(r["Time"]): float(r[column]) for r in wpp_indicators()
            if r.get(column) not in (None, "", "NULL")}
