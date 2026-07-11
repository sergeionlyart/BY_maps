"""WP-F1: возрастно-половые структуры переписей 2009/2019 по районам.

Источник: выгрузка OLAP-куба F201N «Половозрастная структура населения»
(census.belstat.gov.by) - data/raw/census_olap/f201_raion_age5_sex_loc.json.
Каждая ячейка: район (или город обл. подчинения) x 5-летняя группа x пол x
тип местности, отдельно для переписей 2009 и 2019.

Выход:
  data/curated/age2009.csv, age2019.csv
    колонки: territory_id, oblast, age_group, sex, locality, pop
    territory_id: r-* (район), c-* (город обл. подчинения), BY-HM (Минск),
    BY-xx (область), BY (страна)

Гармонизация района к реестру проекта - по русскому названию
(«Барановичский р-н» -> RAIONS ru «Барановичский»).

Запуск: python -m etl.census_age
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .common import ROOT, RAW
from .registry import RAIONS, OBLASTS, raion_id, city_id

CURATED = ROOT / "data" / "curated"

OBL_RU2ID = {
    "Брестская обл.": "BY-BR", "Витебская обл.": "BY-VI",
    "Гомельская обл.": "BY-HO", "Гродненская обл.": "BY-HR",
    "Минская обл.": "BY-MI", "Могилевская обл.": "BY-MA",
    "г. Минск": "BY-HM",
}

def _e(s: str) -> str:
    """Нормализация е/ё для сопоставления названий."""
    return s.replace("ё", "е").replace("Ё", "Е")


# русское название района (без «р-н», е=ё) -> id проекта
RAION_RU2ID = {_e(ru): raion_id(lat) for lat, (ru, _g, _c) in RAIONS.items()}
# города областного подчинения в OLAP: «г. X» либо «Xский горсовет»
CITY_RU2ID = {
    "г. Барановичи": "c-baranavichy", "г. Брест": "c-brest", "г. Пинск": "c-pinsk",
    "г. Витебск": "c-viciebsk", "Витебский горсовет": "c-viciebsk",
    "г. Новополоцк": "c-navapolack", "Новополоцкий горсовет": "c-navapolack",
    "г. Орша": "c-orsha", "Оршанский горсовет": "c-orsha",
    "г. Полоцк": "c-polack", "Полоцкий горсовет": "c-polack",
    "г. Гомель": "c-homiel", "Гомельский горсовет": "c-homiel",
    "г. Гродно": "c-hrodna", "Гродненский горсовет": "c-hrodna",
    "г. Бобруйск": "c-babrujsk", "Бобруйский горсовет": "c-babrujsk",
    "г. Могилев": "c-mahilou", "Могилевский горсовет": "c-mahilou",
    "г. Жодино": "c-zhodzina", "Жодинский горсовет": "c-zhodzina",
}

AGE_ORDER = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
             "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74",
             "75-79", "80-84", "85 и старше"]

SEX_MAP = {"Мужчины": "m", "Женщины": "f"}
LOC_MAP = {"Городское население": "urban", "Сельское население": "rural"}


def _num(s: str) -> int | None:
    s = (s or "").replace("\xa0", "").strip()
    return int(s) if s.isdigit() else None


def territory_id(obl_ru: str, raion_ru: str | None) -> str | None:
    """id территории проекта; None - пропустить (внутригородские районы Минска
    и Орша/Полоцк, вошедшие в районы к 2019 г. - их скопом держит район)."""
    if raion_ru is None or raion_ru == "null":
        return OBL_RU2ID.get(obl_ru)
    base = _e(raion_ru.replace(" р-н", "").strip())
    if base in RAION_RU2ID:
        return RAION_RU2ID[base]
    if raion_ru in CITY_RU2ID:
        return CITY_RU2ID[raion_ru]
    if obl_ru == "г. Минск":
        return None  # внутригородские районы Минска не гармонизируем
    return f"UNMAPPED:{raion_ru}"


def parse(dump: Path) -> list[dict]:
    d = json.loads(dump.read_text())
    cs = d["cellset"]
    head_obl = [c["value"] for c in cs[0]]
    head_raion = [c["value"] for c in cs[1]]
    head_meas = [c["value"] for c in cs[2]]
    rows = cs[3:]

    records = []
    unmapped = set()
    for j in range(3, len(head_meas)):
        year = 2009 if "2009" in head_meas[j] else 2019
        tid = territory_id(head_obl[j], head_raion[j])
        if tid is None:
            continue
        if tid.startswith("UNMAPPED"):
            unmapped.add(head_raion[j])
            continue
        obl = OBL_RU2ID.get(head_obl[j], "")
        for r in rows:
            age, sex, loc = r[0]["value"], r[1]["value"], r[2]["value"]
            v = _num(r[j]["value"])
            if v is None:
                continue
            records.append({
                "territory_id": tid, "oblast": obl, "year": year,
                "age_group": age, "sex": SEX_MAP.get(sex, sex),
                "locality": LOC_MAP.get(loc, loc), "pop": v,
            })
    if unmapped:
        raise ValueError(f"негармонизированные территории OLAP: {sorted(unmapped)}")
    return records


def main() -> None:
    records = parse(RAW / "census_olap" / "f201_raion_age5_sex_loc.json")
    CURATED.mkdir(parents=True, exist_ok=True)
    for year in (2009, 2019):
        rows = [r for r in records if r["year"] == year]
        rows.sort(key=lambda r: (r["oblast"], r["territory_id"],
                                 AGE_ORDER.index(r["age_group"]) if r["age_group"] in AGE_ORDER else 99,
                                 r["sex"], r["locality"]))
        dest = CURATED / f"age{year}.csv"
        with open(dest, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["territory_id", "oblast", "year",
                                              "age_group", "sex", "locality", "pop"],
                               lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        n_terr = len({r["territory_id"] for r in rows})
        print(f"OK: {dest.name}: {len(rows)} строк, {n_terr} территорий")


if __name__ == "__main__":
    main()
