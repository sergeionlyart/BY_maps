"""Главный сборочный конвейер: сырые источники -> web/public/data/*.

Запуск:  python -m etl.build
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .common import RAW, CURATED, OUT
from .parse_popstat import parse_division, parse_cities
from .parse_demoscope import parse_regions
from .parse_wikidata import load_settlements, match_city
from . import geo
from .registry import (RAIONS, OBLASTS, OBLAST_CITIES_HOST, OBLAST_CENTERS,
                       TOP7_CITIES, WEST_1921, COORD_OVERRIDES, raion_id, city_id)

DEMOSCOPE_YEARS = {1959: "demo59.html", 1970: "demo70.html",
                   1979: "demo79.html", 1989: "demo89.html"}
CENSUS_YEARS = [1897, 1923, 1926, 1939, 1959, 1970, 1979, 1989, 1999, 2009, 2019]

# коды типов данных в выходном JSON
T = {"census": "c", "estimate": "e", "reconstructed": "r", "computed": "m"}


def _pack(series: dict[int, tuple[int, str]]) -> dict[str, list]:
    return {str(y): [v, T.get(t, t)] for y, (v, t) in sorted(series.items())}


def build() -> dict:
    div = parse_division(RAW / "ps_div.html")
    cities_raw = parse_cities(RAW / "ps_cities.html")
    demo = {y: parse_regions(RAW / f) for y, f in DEMOSCOPE_YEARS.items()}
    settlements = load_settlements(RAW / "wikidata_settlements.json")
    raion_geoms = geo.build_raion_geoms(RAW / "gb-BLR-ADM2.geojson",
                                        RAW / "drybin_osm.json")
    adm1 = geo.load_adm1(RAW / "gb-BLR-ADM1.geojson")

    territories: dict[str, dict] = {}

    # --- страна -------------------------------------------------------------
    country_pop: dict[int, tuple[int, str]] = dict(div["country"])
    for y, d in demo.items():
        if y not in country_pop:
            country_pop[y] = (d["country"][0], "census")
    with open(CURATED / "country_history.csv") as f:
        for row in csv.DictReader(f):
            country_pop[int(row["year"])] = (int(row["pop"]), row["dtype"])
    country_urban: dict[int, tuple[int, str]] = {
        y: (d["country"][1], "census") for y, d in demo.items()}

    # --- города -------------------------------------------------------------
    # административная привязка для разрешения неоднозначных названий
    oblast_admins = {obl: set() for obl in list(OBLASTS) + ["BY-HM"]}
    for lat, (ru, _g, _c) in RAIONS.items():
        obl = _raion_oblast(lat, div)
        oblast_admins[obl].add(ru + " район")

    city_ids: dict[str, str] = {}  # be name -> id
    center_of: dict[str, str] = {}  # raion lat -> city id
    for be, info in cities_raw.items():
        cid = city_id(info["lat"])
        city_ids[be] = cid
        wd = match_city(be, oblast_admins.get(info["oblast"], set()), settlements)
        lon = (wd or {}).get("lon")
        lat_ = (wd or {}).get("lat")
        if lon is None and be in COORD_OVERRIDES:
            lon, lat_ = COORD_OVERRIDES[be]
        territories[cid] = {
            "id": cid, "level": "city",
            "ru": (wd or {}).get("ru") or be, "be": be,
            "parent": info["oblast"],
            "lon": lon, "lat": lat_,
            "flags": sorted(
                (["oblCenter"] if be in OBLAST_CENTERS else [])
                + (["top7"] if be in TOP7_CITIES else [])
                + (["oblCity"] if be in OBLAST_CITIES_HOST else [])),
            "pop": _pack(info["series"]),
            "note": info["note"],
        }
    # Минск-город - и "область", и город: серия из таблицы городов
    minsk_series = cities_raw["Мінск"]["series"]

    # --- районы -------------------------------------------------------------
    hosted_by_raion: dict[str, list[str]] = {}
    for city_be, host in OBLAST_CITIES_HOST.items():
        hosted_by_raion.setdefault(host, []).append(city_be)

    for be, (lat, obl, series) in div["raions"].items():
        rid = raion_id(lat)
        ru, _geo_name, center_be = RAIONS[lat]
        # полигонный итог = админитог района + города обл. подчинения на его
        # территории (в годы, когда они учитывались отдельно)
        total: dict[int, tuple[int, str]] = {}
        for y, (v, t) in series.items():
            add = 0
            for cb in hosted_by_raion.get(lat, []):
                cs = div["obl_cities"].get(cb)
                if cs and y in cs[2]:
                    add += cs[2][y][0]
            total[y] = (v + add, t)
        # без районного центра (и без городов областного подчинения)
        no_center: dict[int, tuple[int, str]] = {}
        center_ids = []
        if center_be:
            center_ids.append(city_ids[center_be])
            center_of[lat] = city_ids[center_be]
        for cb in hosted_by_raion.get(lat, []):
            if city_ids[cb] not in center_ids:
                center_ids.append(city_ids[cb])
        cut_names = list(dict.fromkeys(
            ([center_be] if center_be else []) + hosted_by_raion.get(lat, [])))
        cut_series = [cities_raw[cb]["series"] for cb in cut_names]
        for y, (v, t) in total.items():
            cut = 0
            ok = True
            for cs in cut_series:
                if y in cs:
                    cut += cs[y][0]
                elif y >= 1970:
                    ok = False
            if ok:
                no_center[y] = (max(v - cut, 0), t)

        territories[rid] = {
            "id": rid, "level": "raion", "ru": ru + " район",
            "be": be, "parent": obl,
            "area": round(raion_geoms[lat]["area"], 1),
            "center": center_ids,
            "flags": (["west1921"] if lat in WEST_1921 else []),
            "pop": _pack(total),
            "popAdmin": _pack(series),
            "popNoCenter": _pack(no_center),
        }
        for cid in center_ids:
            flags = territories[cid]["flags"]
            if "raionCenter" not in flags and center_be and cid == city_ids.get(center_be):
                territories[cid]["flags"] = sorted(flags + ["raionCenter"])
            territories[cid]["raion"] = rid

    # --- области ------------------------------------------------------------
    for obl, series in div["oblasts"].items():
        pop = dict(series)
        urban: dict[int, tuple[int, str]] = {}
        for y, d in demo.items():
            if obl in d["oblasts"]:
                t, u, r = d["oblasts"][obl]
                if y not in pop:
                    pop[y] = (t, "census")
                urban[y] = (u, "census")
        ru, be, _ = OBLASTS[obl]
        territories[obl] = {
            "id": obl, "level": "oblast", "ru": ru, "be": be, "parent": "BY",
            "area": round(adm1[obl]["area"], 1),
            "flags": [], "pop": _pack(pop), "urban": _pack(urban),
        }

    # Минск как единица уровня области
    territories["BY-HM"] = {
        "id": "BY-HM", "level": "oblast",
        "ru": "г. Минск", "be": "г. Мінск", "parent": "BY",
        "area": round(adm1["BY-HM"]["area"], 1),
        "flags": ["capital"],
        "pop": _pack(dict(minsk_series)),
        "urban": _pack({y: (v, t) for y, (v, t) in minsk_series.items()}),
    }

    # --- страна: запись -----------------------------------------------------
    # вычисленное городское население = сумма всех городских НП (для лет,
    # где официального значения нет)
    for y in CENSUS_YEARS + [2025]:
        if y in country_urban:
            continue
        s = 0
        n = 0
        for info in cities_raw.values():
            if y in info["series"]:
                s += info["series"][y][0]
                n += 1
        if n > 20:
            country_urban[y] = (s, "computed")

    territories["BY"] = {
        "id": "BY", "level": "country", "ru": "Беларусь", "be": "Беларусь",
        "parent": None,
        "area": round(sum(v["area"] for v in adm1.values()), 1),
        "flags": [], "pop": _pack(country_pop), "urban": _pack(country_urban),
    }

    # --- панель урбанизации и концентрации ----------------------------------
    panel = []
    minsk = cities_raw["Мінск"]["series"]
    for y in CENSUS_YEARS + [2025]:
        row = {"year": y}
        cp = country_pop.get(y)
        row["pop"] = cp[0] if cp else None
        row["popType"] = T.get(cp[1], cp[1]) if cp else None
        if y in country_urban:
            row["urban"] = country_urban[y][0]
            row["urbanType"] = T.get(country_urban[y][1])
        if y in minsk:
            row["minsk"] = minsk[y][0]
        oc = [cities_raw[c]["series"] for c in OBLAST_CENTERS]
        if all(y in s for s in oc):
            row["oblCenters"] = sum(s[y][0] for s in oc)
        t7 = [cities_raw[c]["series"] for c in TOP7_CITIES]
        if all(y in s for s in t7):
            row["top7"] = sum(s[y][0] for s in t7)
        panel.append(row)

    return {
        "territories": territories,
        "panel": panel,
        "censusYears": CENSUS_YEARS,
        "raion_geoms": raion_geoms,
        "adm1": adm1,
    }


def _raion_oblast(lat: str, div) -> str:
    for be, (l, obl, _s) in div["raions"].items():
        if l == lat:
            return obl
    return "BY"


def main() -> None:
    res = build()
    OUT.mkdir(parents=True, exist_ok=True)
    data = {
        "censusYears": res["censusYears"],
        "yearRange": [1897, 2026],
        "territories": res["territories"],
        "panel": res["panel"],
    }
    (OUT / "data.json").write_text(json.dumps(data, ensure_ascii=False))
    geo.emit_geojson(res["raion_geoms"], res["adm1"], OUT / "geo")
    n = res["territories"]
    print(f"OK: {len(n)} территорий "
          f"({sum(1 for t in n.values() if t['level']=='raion')} районов, "
          f"{sum(1 for t in n.values() if t['level']=='city')} городов); "
          f"data.json {round((OUT/'data.json').stat().st_size/1024)} КБ")


if __name__ == "__main__":
    main()
