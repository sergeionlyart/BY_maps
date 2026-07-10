"""Геообработка: полигоны geoBoundaries, врезка Дрибинского района из OSM,
площади (сферическая формула), историческая граница 1921-1939 гг."""
from __future__ import annotations

import json
import math
from pathlib import Path

from shapely.geometry import shape, mapping, MultiPolygon, Polygon
from shapely.ops import unary_union

from .registry import RAIONS, WEST_1921, raion_id

R_EARTH = 6371.0088  # км, средний радиус


def _ring_area_km2(ring: list[list[float]]) -> float:
    """Площадь кольца на сфере (алгоритм geojson-area, км²)."""
    n = len(ring)
    if n < 3:
        return 0.0
    total = 0.0
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        total += math.radians(x2 - x1) * (2 + math.sin(math.radians(y1)) + math.sin(math.radians(y2)))
    return abs(total * R_EARTH * R_EARTH / 2.0)


def geom_area_km2(geom) -> float:
    gj = mapping(geom)
    polys = [gj["coordinates"]] if gj["type"] == "Polygon" else list(gj["coordinates"])
    area = 0.0
    for poly in polys:
        area += _ring_area_km2(poly[0])
        for hole in poly[1:]:
            area -= _ring_area_km2(hole)
    return area


def load_adm1(path: Path) -> dict[str, dict]:
    """{oblast_id/BY-HM: {'geom': shapely, 'area': км²}} по shapeISO."""
    gj = json.loads(path.read_text())
    out = {}
    for f in gj["features"]:
        iso = f["properties"].get("shapeISO", "")
        g = shape(f["geometry"])
        out[iso] = {"geom": g, "area": geom_area_km2(g)}
    return out


def load_adm2(path: Path) -> dict[str, dict]:
    """{shapeName: shapely geometry} (118 фич: 117 районов + Minsk City)."""
    gj = json.loads(path.read_text())
    return {f["properties"]["shapeName"]: shape(f["geometry"]) for f in gj["features"]}


def drybin_polygon(osm_path: Path) -> Polygon:
    """Собирает полигон Дрибинского района из OSM-отношения (Overpass out geom):
    сшивает внешние (outer) линии в замкнутое кольцо."""
    data = json.loads(osm_path.read_text())
    rel = next(e for e in data["elements"] if e["type"] == "relation")
    segs = []
    for m in rel["members"]:
        if m.get("role") == "outer" and m.get("geometry"):
            segs.append([(p["lon"], p["lat"]) for p in m["geometry"]])
    ring = list(segs.pop(0))
    while segs:
        for i, s in enumerate(segs):
            if s[0] == ring[-1]:
                ring.extend(s[1:]); segs.pop(i); break
            if s[-1] == ring[-1]:
                ring.extend(reversed(s[:-1])); segs.pop(i); break
            if s[-1] == ring[0]:
                ring[0:0] = s[:-1]; segs.pop(i); break
            if s[0] == ring[0]:
                ring[0:0] = list(reversed(s[1:])); segs.pop(i); break
        else:
            raise ValueError("Не удалось сшить кольцо границы Дрибинского района")
    return Polygon(ring)


def build_raion_geoms(adm2_path: Path, drybin_osm: Path) -> dict[str, dict]:
    """{raion_lat_name: {'geom','area'}} для всех 118 районов + 'MINSK_CITY'.

    Дрибинский район отсутствует в geoBoundaries (создан в 1989 г.,
    исходник CIESIN его не содержит): его полигон берётся из OSM и
    вырезается из полигонов Горецкого и Мстиславского районов.
    """
    shapes = load_adm2(adm2_path)
    drybin = drybin_polygon(drybin_osm)
    shapes["Horki"] = shapes["Horki"].difference(drybin)
    shapes["Mstsislaw"] = shapes["Mstsislaw"].difference(drybin)

    out = {}
    for lat, (_ru, geo_name, _c) in RAIONS.items():
        geom = drybin if geo_name is None else shapes[geo_name]
        out[lat] = {"geom": geom, "area": geom_area_km2(geom)}
    out["MINSK_CITY"] = {"geom": shapes["Minsk City"],
                         "area": geom_area_km2(shapes["Minsk City"])}
    return out


def border_1921(raion_geoms: dict[str, dict]):
    """Линия польско-советской границы 1921-1939 гг., агрегированная по
    современным районам: общее ребро между растворёнными западной и
    восточной частями страны."""
    west = unary_union([raion_geoms[r]["geom"] for r in WEST_1921])
    east_names = [r for r in RAIONS if r not in WEST_1921]
    east = unary_union([raion_geoms[r]["geom"] for r in east_names]
                       + [raion_geoms["MINSK_CITY"]["geom"]])
    country = unary_union([west, east])
    # внутреннее ребро = граница запада минус внешний контур страны
    line = west.boundary.difference(country.boundary.buffer(0.001))
    return line.simplify(0.002)


def emit_geojson(raion_geoms, adm1, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    feats = []
    for lat in RAIONS:
        g = raion_geoms[lat]
        feats.append({
            "type": "Feature",
            "properties": {"id": raion_id(lat)},
            "geometry": mapping(g["geom"].simplify(0.002)),
        })
    feats.append({"type": "Feature", "properties": {"id": "BY-HM"},
                  "geometry": mapping(raion_geoms["MINSK_CITY"]["geom"])})
    (out_dir / "adm2.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False))

    feats1 = [{"type": "Feature", "properties": {"id": iso},
               "geometry": mapping(v["geom"])} for iso, v in adm1.items()]
    (out_dir / "adm1.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats1}, ensure_ascii=False))

    line = border_1921(raion_geoms)
    (out_dir / "border1921.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"id": "border-1921-1939"},
             "geometry": mapping(line)}]}, ensure_ascii=False))
