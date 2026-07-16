"""INF-12: современный инфраструктурный срез OSM по 94 городам (urban-overhang).

Вход: data/raw/urban/osm/belarus-latest.osm.pbf (Geofabrik; сам PBF не
вендорится, его md5/sha256 фиксируются в data/raw/urban/registry_osm.csv)
и реестр data/curated/urban/city_registry.csv (94 города, сортировка по
city_id; код города в картах-владельцах = позиция в реестре + 1).

Две фазы (подкоманда: parse | assign | all):

  parse - только PBF, без карт-владельцев и растров:
    data/tmp/urban/osm_segments.npz   - середины/длины дорожных сегментов
                                        (0=major, 1=local; длина - гаверсинус);
    data/tmp/urban/osm_poi.csv        - точки интереса 8 категорий;
    data/tmp/urban/osm_buildings.npz  - первый узел каждого building-пути;
    data/tmp/urban/admin_polygons.geojson - административная граница города:
        наименьший по площади (Молльвейде) полигон boundary=administrative
        (admin_level 6/8/9; для Минска допустим 4), содержащий seed города
        и не являющийся районом/сельсоветом (по имени).

  assign - раскладка по карте-владельцу INF-12 (data/tmp/urban/fixed_t10_c1.npz
    из etl.urban_morph, сетка Молльвейде 100 м 5180x8835) и растрам
    built_E{1975..2020}.tif; если входы ещё не готовы - печатает
    «waiting for ...» и выходит кодом 0:
    data/raw/urban/city_roads.csv     - км дорог по городам и классам;
    data/raw/urban/city_poi.csv       - счётчики POI по городам и категориям;
    data/raw/urban/city_buildings.csv - счётчики зданий по городам;
    data/raw/urban/admin_areas.csv    - площади административных границ;
    data/raw/urban/admin_built.csv    - застройка (м²) внутри админ-границ
                                        по эпохам GHS-BUILT-S;
    data/raw/urban/registry_osm.csv   - реестр источника (PBF).

Важно: таймстемпы правок OSM нигде не используются и не выводятся -
дата правки объекта не является датой его постройки.

Запуск (требует pyosmium+rasterio+shapely): python -m etl.urban_osm all
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from array import array
from math import asin, cos, radians, sin, sqrt

import numpy as np
import osmium
import shapely
from shapely.geometry import mapping, shape

from .common import ROOT
from .urban_morph import (CELL, CLIP_MAXY, CLIP_MINX, EPOCHS, RASTERS, TMP,
                          load_registry, read_epoch)

RAW = ROOT / "data" / "raw" / "urban"
OSM_PBF = RAW / "osm" / "belarus-latest.osm.pbf"
GEOFABRIK_URL = "https://download.geofabrik.de/europe/belarus-latest.osm.pbf"
GRID_SHAPE = (5180, 8835)
ACCESSED = "2026-07-16"

# --- дорожные классы ---------------------------------------------------------
_MAJOR = ("motorway", "trunk", "primary", "secondary", "tertiary")
_LOCAL = ("residential", "unclassified", "living_street")
ROAD_CLASS = {h: 0 for h in _MAJOR} | {f"{h}_link": 0 for h in _MAJOR} \
    | {h: 1 for h in _LOCAL}
CLASS_NAME = {0: "major", 1: "local"}

# --- категории POI (фиксированный порядок) -----------------------------------
POI_CATEGORIES = ("admin_service", "emergency", "grocery", "kindergarten",
                  "pharmacy", "primary_care", "school", "transport_stop")
_GROCERY_SHOP = {"supermarket", "convenience", "greengrocer", "farm", "general"}
_PRIMARY_AMENITY = {"clinic", "doctors", "hospital"}
_PRIMARY_HC = {"clinic", "doctor", "centre"}
_ADMIN_AMENITY = {"townhall", "post_office"}

# --- отбор административных границ -------------------------------------------
ADMIN_LEVELS = {"4", "6", "8", "9"}
FORBIDDEN_NAME = ("район", "раён", "сельсовет", "сельсавет")
MINSK_ID = "c-minsk"          # единственный город, которому допустим admin_level=4

R_EARTH = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Длина дуги большого круга в метрах."""
    p1, p2 = radians(lat1), radians(lat2)
    a = sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(lon2 - lon1) / 2) ** 2
    return 2.0 * R_EARTH * asin(sqrt(a))


def poi_categories(tags) -> list[str]:
    """Категории POI по тегам (может быть несколько; фиксированный порядок)."""
    shop = tags.get("shop")
    amenity = tags.get("amenity")
    hc = tags.get("healthcare")
    cats = []
    if amenity in _ADMIN_AMENITY:
        cats.append("admin_service")
    if amenity == "fire_station" or tags.get("emergency") == "ambulance_station":
        cats.append("emergency")
    if shop in _GROCERY_SHOP:
        cats.append("grocery")
    if amenity == "kindergarten":
        cats.append("kindergarten")
    if amenity == "pharmacy" or hc == "pharmacy":
        cats.append("pharmacy")
    if amenity in _PRIMARY_AMENITY or hc in _PRIMARY_HC:
        cats.append("primary_care")
    if amenity == "school":
        cats.append("school")
    if tags.get("highway") == "bus_stop" or tags.get("railway") in ("station", "halt"):
        cats.append("transport_stop")
    return cats


# =============================== фаза parse ==================================

class OsmHandler(osmium.SimpleHandler):
    """Один проход по узлам и путям: дороги, POI, здания."""

    def __init__(self):
        super().__init__()
        self.seg_lat = array("d")
        self.seg_lon = array("d")
        self.seg_len = array("f")
        self.seg_cls = array("B")
        self.n_seg = 0
        self.poi: list[tuple[str, float, float]] = []
        self.bld_lat = array("f")
        self.bld_lon = array("f")

    @staticmethod
    def _first_loc(w):
        for nd in w.nodes:
            if nd.location.valid():
                return nd.location.lat, nd.location.lon
        return None

    def node(self, n):
        if not n.tags:
            return
        cats = poi_categories(n.tags)
        if cats and n.location.valid():
            lat, lon = n.location.lat, n.location.lon
            for c in cats:
                self.poi.append((c, lat, lon))

    def way(self, w):
        tags = w.tags
        if not tags:
            return
        hw = tags.get("highway")
        if hw is not None and hw in ROAD_CLASS and tags.get("area") != "yes":
            cls = ROAD_CLASS[hw]
            plat = plon = None
            for nd in w.nodes:
                loc = nd.location
                if not loc.valid():
                    continue
                lat, lon = loc.lat, loc.lon
                if plat is not None:
                    self.seg_lat.append((plat + lat) / 2.0)
                    self.seg_lon.append((plon + lon) / 2.0)
                    self.seg_len.append(haversine_m(plat, plon, lat, lon))
                    self.seg_cls.append(cls)
                    self.n_seg += 1
                    if self.n_seg % 1_000_000 == 0:
                        print(f"  ... {self.n_seg:,} сегментов")
                plat, plon = lat, lon
        b = tags.get("building")
        is_bld = b is not None and b != "no"
        cats = poi_categories(tags)
        if is_bld or cats:
            loc = self._first_loc(w)
            if loc is None:
                return
            if is_bld:
                self.bld_lat.append(loc[0])
                self.bld_lon.append(loc[1])
            for c in cats:
                self.poi.append((c, loc[0], loc[1]))


def collect_admin_areas(pbf) -> list[dict]:
    """Мультиполигоны boundary=administrative, admin_level 4/6/8/9 (WGS84)."""
    fab = osmium.geom.WKBFactory()
    areas: list[dict] = []
    fp = (osmium.FileProcessor(str(pbf))
          .with_areas(osmium.filter.KeyFilter("boundary"))
          .with_filter(osmium.filter.EntityFilter(osmium.osm.AREA)))
    for a in fp:
        tags = a.tags
        if tags.get("boundary") != "administrative":
            continue
        lvl = tags.get("admin_level")
        if lvl not in ADMIN_LEVELS:
            continue
        try:
            geom = shapely.from_wkb(bytes.fromhex(fab.create_multipolygon(a)))
        except (RuntimeError, shapely.errors.GEOSException):
            continue          # несобираемая геометрия - пропуск
        names_lc = " | ".join(
            tags.get(k) or "" for k in ("name", "name:ru", "name:be")).lower()
        areas.append({"osm_id": a.orig_id(), "level": int(lvl),
                      "name": tags.get("name") or "", "names_lc": names_lc,
                      "geom": geom})
    return areas


def _moll_km2(geom) -> float:
    """Площадь WGS84-геометрии в км² (равновеликая Молльвейде)."""
    from rasterio.warp import transform_geom
    return shape(transform_geom("EPSG:4326", "ESRI:54009", mapping(geom))).area / 1e6


def match_admin(cities: list[dict], areas: list[dict]) -> tuple[dict, list[str]]:
    """city_id -> индекс полигона; список городов без границы."""
    geoms = np.array([a["geom"] for a in areas], dtype=object)
    km2: dict[int, float] = {}
    matched: dict[str, int] = {}
    unmatched: list[str] = []
    for c in cities:
        cid = c["city_id"]
        hit = shapely.contains_xy(geoms, float(c["lon"]), float(c["lat"]))
        cand = []
        for j in np.flatnonzero(hit):
            a = areas[j]
            if a["level"] == 4 and cid != MINSK_ID:
                continue
            if any(s in a["names_lc"] for s in FORBIDDEN_NAME):
                continue
            cand.append(int(j))
        if not cand:
            unmatched.append(cid)
            continue
        for j in cand:
            if j not in km2:
                km2[j] = _moll_km2(areas[j]["geom"])
        matched[cid] = min(cand, key=lambda j: (km2[j], areas[j]["level"],
                                                areas[j]["osm_id"]))
    return matched, unmatched


def cmd_parse() -> None:
    """Фаза 1: чтение PBF -> промежуточные файлы в data/tmp/urban."""
    if not OSM_PBF.exists():
        raise SystemExit(f"нет {OSM_PBF}; скачайте {GEOFABRIK_URL}")
    TMP.mkdir(parents=True, exist_ok=True)

    print("parse: дороги/POI/здания (один проход, flex_mem) ...")
    h = OsmHandler()
    h.apply_file(str(OSM_PBF), locations=True, idx="flex_mem")

    np.savez_compressed(
        TMP / "osm_segments.npz",
        lat_mid=np.array(h.seg_lat, dtype=np.float64),
        lon_mid=np.array(h.seg_lon, dtype=np.float64),
        length_m=np.array(h.seg_len, dtype=np.float32),
        class_group=np.array(h.seg_cls, dtype=np.uint8))
    cls = np.array(h.seg_cls, dtype=np.uint8)
    print(f"  сегментов: {h.n_seg:,} (major {int((cls == 0).sum()):,}, "
          f"local {int((cls == 1).sum()):,}) -> osm_segments.npz")

    with (TMP / "osm_poi.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["category", "lat", "lon"])
        for c, lat, lon in h.poi:
            w.writerow([c, f"{lat:.7f}", f"{lon:.7f}"])
    by_cat = {c: 0 for c in POI_CATEGORIES}
    for c, _, _ in h.poi:
        by_cat[c] += 1
    print("  POI: " + ", ".join(f"{c}={n:,}" for c, n in by_cat.items())
          + " -> osm_poi.csv")

    np.savez_compressed(TMP / "osm_buildings.npz",
                        lat=np.array(h.bld_lat, dtype=np.float32),
                        lon=np.array(h.bld_lon, dtype=np.float32))
    print(f"  зданий (building=*, кроме building=no): {len(h.bld_lat):,} "
          "-> osm_buildings.npz")

    print("parse: административные границы (areas) ...")
    areas = collect_admin_areas(OSM_PBF)
    print(f"  полигонов boundary=administrative (4/6/8/9): {len(areas):,}")
    cities = load_registry()
    matched, unmatched = match_admin(cities, areas)
    feats = []
    for c in cities:
        j = matched.get(c["city_id"])
        if j is None:
            continue
        a = areas[j]
        feats.append({"type": "Feature",
                      "properties": {"city_id": c["city_id"],
                                     "osm_id": a["osm_id"],
                                     "admin_level": a["level"],
                                     "name": a["name"]},
                      "geometry": mapping(a["geom"])})
    with (TMP / "admin_polygons.geojson").open("w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f,
                  ensure_ascii=False)
    print(f"  границы найдены: {len(feats)}/{len(cities)}"
          + (f"; без границы: {', '.join(unmatched)}" if unmatched else ""))


# =============================== фаза assign =================================

def _owners_at(lons, lats, owner_map: np.ndarray) -> np.ndarray:
    """Код города (0 = вне городов) для точек WGS84 по карте-владельцу."""
    from rasterio.warp import transform as rio_transform
    xs, ys = rio_transform("EPSG:4326", "ESRI:54009",
                           np.asarray(lons, dtype=np.float64),
                           np.asarray(lats, dtype=np.float64))
    xs, ys = np.asarray(xs), np.asarray(ys)
    cols = np.floor((xs - CLIP_MINX) / CELL).astype(np.int64)
    rows = np.floor((CLIP_MAXY - ys) / CELL).astype(np.int64)
    ok = ((rows >= 0) & (rows < owner_map.shape[0])
          & (cols >= 0) & (cols < owner_map.shape[1]))
    out = np.zeros(xs.shape, dtype=np.uint16)
    out[ok] = owner_map[rows[ok], cols[ok]]
    return out


def _write_csv(path, header: list[str], rows: list) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    print(f"  -> {path} ({len(rows)} строк)")


def _pbf_replication_ts(path) -> str:
    """osmosis_replication_timestamp из заголовка PBF (дата выгрузки), либо ''."""
    try:
        r = osmium.io.Reader(str(path), osmium.osm.osm_entity_bits.NOTHING)
        try:
            return r.header().get("osmosis_replication_timestamp") or ""
        finally:
            r.close()
    except Exception:
        return ""


def write_registry_osm() -> None:
    """Реестр источника: одна строка про PBF (sha256, md5, размер)."""
    sha, md5 = hashlib.sha256(), hashlib.md5()
    with OSM_PBF.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            sha.update(chunk)
            md5.update(chunk)
    ts = _pbf_replication_ts(OSM_PBF)
    notes = (f"md5 {md5.hexdigest()} (сверен с belarus-latest.osm.pbf.md5 "
             f"Geofabrik); osmosis_replication_timestamp {ts or 'н/д'}; "
             "в репозиторий не вендорится (~350 МБ)")
    _write_csv(RAW / "registry_osm.csv",
               ["id", "title", "url", "license", "accessed", "sha256",
                "size_bytes", "vendored", "notes"],
               [["geofabrik_belarus_pbf",
                 "Geofabrik OSM extract: Belarus (belarus-latest.osm.pbf)",
                 GEOFABRIK_URL, "ODbL 1.0 (OpenStreetMap contributors)",
                 ACCESSED, sha.hexdigest(), OSM_PBF.stat().st_size, "no",
                 notes]])


def cmd_assign() -> None:
    """Фаза 2: раскладка parse-выходов по карте-владельцу и растрам."""
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    from rasterio.warp import transform_geom

    if not OSM_PBF.exists():
        print(f"waiting for {OSM_PBF}")
        return
    write_registry_osm()

    required = [TMP / "fixed_t10_c1.npz", TMP / "osm_segments.npz",
                TMP / "osm_poi.csv", TMP / "osm_buildings.npz",
                TMP / "admin_polygons.geojson"] \
        + [RASTERS / f"built_E{e}.tif" for e in EPOCHS]
    missing = [p for p in required if not p.exists()]
    if missing:
        for p in missing:
            print(f"waiting for {p}")
        return

    owner = np.load(TMP / "fixed_t10_c1.npz")["fixed_owner"]
    assert owner.shape == GRID_SHAPE, owner.shape
    cities = load_registry()
    ids = [c["city_id"] for c in cities]
    n = len(ids)

    # --- дороги ---
    seg = np.load(TMP / "osm_segments.npz")
    km = seg["length_m"].astype(np.float64) / 1000.0
    cls = seg["class_group"]
    own = _owners_at(seg["lon_mid"], seg["lat_mid"], owner)
    rows = []
    for g in (0, 1):
        m = cls == g
        per_city = np.bincount(own[m], weights=km[m], minlength=n + 1)
        rows.append(["__national__", CLASS_NAME[g], f"{km[m].sum():.3f}"])
        rows += [[ids[i], CLASS_NAME[g], f"{per_city[i + 1]:.3f}"]
                 for i in range(n)]
    rows.sort(key=lambda r: (r[0], r[1]))
    _write_csv(RAW / "city_roads.csv", ["city_id", "class_group", "length_km"],
               rows)

    # --- POI ---
    with (TMP / "osm_poi.csv").open(encoding="utf-8") as f:
        rdr = csv.reader(f)
        next(rdr)
        poi = [(r[0], float(r[1]), float(r[2])) for r in rdr]
    cat_idx = {c: k for k, c in enumerate(POI_CATEGORIES)}
    pcat = np.array([cat_idx[p[0]] for p in poi], dtype=np.int64)
    pown = _owners_at([p[2] for p in poi], [p[1] for p in poi], owner)
    counts = np.bincount(pown * len(POI_CATEGORIES) + pcat,
                         minlength=(n + 1) * len(POI_CATEGORIES))
    rows = []
    for k, cat in enumerate(POI_CATEGORIES):
        rows.append(["__national__", cat, int((pcat == k).sum())])
        rows += [[ids[i], cat, int(counts[(i + 1) * len(POI_CATEGORIES) + k])]
                 for i in range(n)]
    rows.sort(key=lambda r: (r[0], r[1]))
    _write_csv(RAW / "city_poi.csv", ["city_id", "category", "count"], rows)

    # --- здания ---
    bld = np.load(TMP / "osm_buildings.npz")
    bown = _owners_at(bld["lon"], bld["lat"], owner)
    per_city = np.bincount(bown, minlength=n + 1)
    rows = [["__national__", int(len(bown))]] \
        + [[ids[i], int(per_city[i + 1])] for i in range(n)]
    rows.sort(key=lambda r: r[0])
    _write_csv(RAW / "city_buildings.csv", ["city_id", "buildings_count"], rows)

    # --- административные границы: площади и застройка ---
    gj = json.loads((TMP / "admin_polygons.geojson").read_text(encoding="utf-8"))
    by_city = {f["properties"]["city_id"]: f for f in gj["features"]}
    moll = {cid: transform_geom("EPSG:4326", "ESRI:54009", f["geometry"])
            for cid, f in by_city.items()}
    rows = []
    for c in cities:
        f = by_city.get(c["city_id"])
        if f is None:
            rows.append([c["city_id"], "", "", "", ""])
        else:
            p = f["properties"]
            rows.append([c["city_id"], p["osm_id"], p["admin_level"],
                         p["name"], f"{shape(moll[c['city_id']]).area / 1e6:.2f}"])
    _write_csv(RAW / "admin_areas.csv",
               ["city_id", "osm_relation_id", "admin_level", "matched_name",
                "admin_area_km2"], rows)

    tr = from_origin(CLIP_MINX, CLIP_MAXY, CELL, CELL)
    feats = [(moll[cid], i + 1) for i, cid in enumerate(ids) if cid in moll]
    labels = rasterize(feats, out_shape=GRID_SHAPE, transform=tr, fill=0,
                       dtype="uint8")
    rows = []
    for e in EPOCHS:
        built = read_epoch(e).astype(np.float64)   # >10000 -> 0 (nodata 65535)
        sums = np.bincount(labels.ravel(), weights=built.ravel(),
                           minlength=n + 1)
        rows += [[cid, e, int(round(sums[i + 1]))]
                 for i, cid in enumerate(ids) if cid in moll]
    rows.sort(key=lambda r: (r[0], r[1]))
    _write_csv(RAW / "admin_built.csv", ["city_id", "epoch", "built_admin_m2"],
               rows)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd not in ("parse", "assign", "all"):
        raise SystemExit("usage: python -m etl.urban_osm {parse|assign|all}")
    if cmd in ("parse", "all"):
        cmd_parse()
    if cmd in ("assign", "all"):
        cmd_assign()


if __name__ == "__main__":
    main()
