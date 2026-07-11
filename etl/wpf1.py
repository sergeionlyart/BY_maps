"""WP-F1: производные curated-наборы из завендоренных сырых источников.

- migration_internal.csv  - межобластная матрица миграции (переписи 2009/2019,
  куб F602: место жительства x предыдущее место, 5-летние группы)
- age_current.csv         - возрастные структуры 2019-2026 (дата-портал,
  страна/области/Минск x 5-летние группы x пол x тип местности)

Запуск: python -m etl.wpf1
"""
from __future__ import annotations

import csv
import json

from .common import ROOT, RAW

CURATED = ROOT / "data" / "curated"

OBL_RU2ID = {
    "Брестская": "BY-BR", "Витебская": "BY-VI", "Гомельская": "BY-HO",
    "Гродненская": "BY-HR", "Минская": "BY-MI", "Могилевская": "BY-MA",
    "г. Минск": "BY-HM", "г.Минск": "BY-HM",
}


def _obl_id(name: str) -> str | None:
    name = (name or "").replace("обл.", "").replace("область", "").strip()
    for k, v in OBL_RU2ID.items():
        if name.startswith(k):
            return v
    return None


def _num(s) -> int | None:
    s = str(s or "").replace("\xa0", "").replace(" ", "").strip()
    return int(float(s)) if s.replace(".", "").isdigit() else None


def migration_csv() -> None:
    d = json.loads((RAW / "census_olap" / "f602_oblast_matrix_age5.json").read_text())
    cs = d["cellset"]
    dest_heads = [c["value"] for c in cs[0]]   # область места жительства
    meas_heads = [c["value"] for c in cs[1]]   # мера (2009/2019)
    rows = cs[2:]
    out = []
    for r in rows:
        origin = _obl_id(r[0]["value"])
        age = r[1]["value"]
        if origin is None:
            continue
        for j in range(2, len(r)):
            dest = _obl_id(dest_heads[j])
            if dest is None:
                continue
            year = 2009 if "2009" in meas_heads[j] else 2019
            v = _num(r[j]["value"])
            if v is not None:
                out.append([year, origin, dest, age, v])
    out.sort()
    with open(CURATED / "migration_internal.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["year", "origin_oblast", "dest_oblast", "age_group", "migrants"])
        w.writerows(out)
    print(f"OK: migration_internal.csv: {len(out)} строк")


def age_current_csv() -> None:
    data = json.loads((RAW / "age_current" / "dataportal_age5_2019-2026.json").read_text())
    dims = json.loads((RAW / "age_current" / "dataportal_dims.json").read_text())
    name_by_code = {}
    for dim in dims.values():
        for v in dim:
            name_by_code[v["code"]] = v["name"]

    terr_map = {
        "Республика Беларусь": "BY", "Брестская область": "BY-BR",
        "Витебская область": "BY-VI", "Гомельская область": "BY-HO",
        "Гродненская область": "BY-HR", "Минская область": "BY-MI",
        "Могилевская область": "BY-MA", "г.Минск": "BY-HM", "г. Минск": "BY-HM",
    }
    sex_map = {"Оба пола": "t", "мужчины": "m", "женщины": "f",
               "Мужчины": "m", "Женщины": "f"}
    loc_map = {"Всего по типам местности": "total",
               "городская местность": "urban", "сельская местность": "rural",
               "Городское население": "urban", "Сельское население": "rural"}

    years = [int(y) for y in data["tableHeader"][0]]
    ndims = len(data["tableHeaderDimColumns"])  # 4: территория, возраст, пол, местность
    out = []
    for row in data["tableRows"]:
        cells = [c["value"] for c in row]
        terr = terr_map.get(cells[0].strip())
        age = (cells[1].replace("в возрасте", "").replace("лет и старше", "+")
               .replace("лет", "").replace("года", "").replace("год", "").strip())
        sex = sex_map.get(cells[2].strip())
        loc = loc_map.get(cells[3].strip())
        if not terr or not sex or not loc:
            continue
        for y, v in zip(years, cells[ndims:]):
            n = _num(v)
            if n is not None:
                out.append([y, terr, age, sex, loc, n])
    out.sort()
    with open(CURATED / "age_current.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["year", "territory_id", "age_group", "sex", "locality", "pop"])
        w.writerows(out)
    print(f"OK: age_current.csv: {len(out)} строк")


def main() -> None:
    CURATED.mkdir(parents=True, exist_ok=True)
    migration_csv()
    age_current_csv()


if __name__ == "__main__":
    main()
