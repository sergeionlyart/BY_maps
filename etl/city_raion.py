"""Привязка городов к районам для прогноза уровня 3 (этап 5).

Три источника, по убыванию приоритета:
- native: город - центр района (поле raion в data.json, ручной реестр);
- pip: point-in-polygon по координатам города и полигонам adm2 (shapely);
- none: координат нет - город остаётся без привязки (перечислен явно).

Результат детерминирован и вендорится: data/curated/city_raion.csv.
Запуск (однократно, требует shapely): python -m etl.city_raion
"""
from __future__ import annotations

import csv
import json

from shapely.geometry import Point, shape

from .common import ROOT, OUT

CURATED = ROOT / "data" / "curated"

# ручной реестр: живые гп без координат в Wikidata (сверено по справочникам)
OVERRIDES = {
    "c-chalapienichy": "r-krupski",       # Холопеничи, Крупский район
    "c-jelizava": "r-asipovicki",         # Елизово, Осиповичский район
    "c-krasnaja-slabada": "r-salihorski", # Красная Слобода, Солигорский район
    "c-narach": "r-miadzielski",          # Нарочь, Мядельский район
}


def main() -> None:
    data = json.loads((OUT / "data.json").read_text())["territories"]
    geo = json.loads((OUT / "geo" / "adm2.geojson").read_text())
    polys = {f["properties"]["id"]: shape(f["geometry"]) for f in geo["features"]}

    rows = []
    unmapped = []
    for t, v in sorted(data.items()):
        if v["level"] != "city" or t == "c-minsk":
            continue
        if v.get("raion"):
            rows.append({"city_id": t, "raion_id": v["raion"], "method": "native"})
            continue
        if t in OVERRIDES:
            rows.append({"city_id": t, "raion_id": OVERRIDES[t], "method": "manual"})
            continue
        lon, lat = v.get("lon"), v.get("lat")
        if lon and lat:
            p = Point(lon, lat)
            hit = [rid for rid, poly in polys.items()
                   if rid.startswith("r-") and poly.contains(p)]
            if len(hit) == 1:
                rows.append({"city_id": t, "raion_id": hit[0], "method": "pip"})
                continue
        unmapped.append(t)

    with open(CURATED / "city_raion.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["city_id", "raion_id", "method"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"OK: city_raion.csv ({len(rows)} городов; native "
          f"{sum(1 for r in rows if r['method'] == 'native')}, pip "
          f"{sum(1 for r in rows if r['method'] == 'pip')})")
    if unmapped:
        print(f"без привязки ({len(unmapped)}): {', '.join(unmapped)}")


if __name__ == "__main__":
    main()
