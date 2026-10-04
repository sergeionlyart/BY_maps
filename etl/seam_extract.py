"""«Шов на карте»: таблица ячеек 1 км в полосе ±52 км вокруг границы Беларуси.

Тяжёлый шаг (numpy + rasterio + shapely; requirements-raster.txt). Глобальные
растры НЕ вендорятся: их адреса и sha256 — в пакете by-maps-seam
(sources/registry_files.csv, загрузчик code/fetch.py); имена файлов, которые
ожидает этот модуль, — в константах ниже. Выход — data/raw/seam/cells.csv.gz
(вендорится); анализ поверх него (etl/seam.py) идёт на стандартной библиотеке.

Сетка — GHSL 1 км (ESRI:54009, мозаика тайлов R3/R4 x C20/C21). Расстояния до
границы считаются в EPSG:3035: Mollweide на 22–33° в.д. сдвигает формы, и
расстояния в нём искажались бы на 10–20%.

Запуск:  SEAM_RAW=<папка загрузок> python -m etl.seam_extract
"""
from __future__ import annotations

import csv
import gzip
import json
import math
import os
import zipfile
from pathlib import Path

import numpy as np
import rasterio
import shapely
from rasterio.transform import Affine
from rasterio.warp import Resampling, reproject, transform, transform_geom
from rasterio.windows import from_bounds
from shapely.geometry import LineString, Point, box, mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
RAW = Path(os.environ.get("SEAM_RAW", ROOT / "data" / "raw" / "seam" / "src"))
OUT = ROOT / "data" / "raw" / "seam"
GEO = ROOT / "web" / "public" / "data" / "geo"

MOLL, LAEA, WGS = "ESRI:54009", "EPSG:3035", "EPSG:4326"
TILES = {"R3_C20": (0, 0), "R3_C21": (0, 1), "R4_C20": (1, 0), "R4_C21": (1, 1)}
X0, Y1, CELL = 959000.0, 7000000.0, 1000.0       # левый верх мозаики 2x2 тайла
MOSAIC = Affine(CELL, 0, X0, 0, -CELL, Y1)
BBOX = (21.4, 49.9, 34.2, 57.3)                  # W S E N с запасом
BAND_KM = 52.0
CITY_MIN_POP = 50_000
CITY_RADIUS_KM = 5.0
CHNPP = (30.099, 51.389)                         # ЧАЭС, lon/lat
CHERN_RADIUS_KM = 35.0
NEIGHBORS = ["POL", "LTU", "LVA", "RUS", "UKR"]
SEG = {"POL": "PL", "LTU": "LT", "LVA": "LV", "RUS": "RU", "UKR": "UA"}
GHSL_BUILT_EPOCHS = [1975, 1990, 2000, 2015, 2020]
GHSL_POP_EPOCHS = [1990, 2000, 2020]
WSF_YEARS = [1990, 2000, 2015]
LI_FILES = {1992: "1992_calDMSP", 2000: "2000_calDMSP", 2004: "2004_calDMSP",
            2012: "2012_calDMSP", 2014: "2014_simVIIRS", 2019: "2019_simVIIRS",
            2024: "2024_simVIIRS"}
VNL_YEARS = [2014, 2019, 2024]
VNL_URL = ("/vsicurl/https://zenodo.org/api/records/17294744/files/"
           "nightlights.average_viirs.v21_m_500m_s_{y}0101_{y}1231_go_"
           "epsg4326_v20250904.tif/content")
GLAD_YEARS = [2003, 2019]
GLAD_TILES = ["60N_020E", "60N_030E"]


# ---------------------------------------------------------------- геометрия
def load_geoms():
    by = unary_union([shape(f["geometry"]) for f in
                      json.load(open(GEO / "adm1.geojson"))["features"]]).buffer(0)
    nb = json.load(open(OUT / "neighbors_adm0.geojson"))
    neigh = {f["properties"]["iso"]: shape(f["geometry"]).buffer(0) for f in nb["features"]}
    to3035 = lambda g: shape(transform_geom(WGS, LAEA, mapping(g)))
    return to3035(by), {k: to3035(v) for k, v in neigh.items()}


def boundary_pieces(by3035, neigh3035, step=1000.0):
    """Граница Беларуси, нарезанная на куски ~1 км с меткой соседа."""
    ring = by3035.boundary
    lines = list(ring.geoms) if hasattr(ring, "geoms") else [ring]
    pieces, labels = [], []
    for ln in lines:
        n = max(1, int(ln.length // step))
        pts = [ln.interpolate(i * ln.length / n) for i in range(n + 1)]
        for a, b in zip(pts[:-1], pts[1:]):
            seg = LineString([a, b])
            mid = seg.interpolate(0.5, normalized=True)
            dists = {k: g.distance(mid) for k, g in neigh3035.items()}
            labels.append(SEG[min(dists, key=dists.get)])
            pieces.append(seg)
    return pieces, np.array(labels)


# ---------------------------------------------------------------- растры
def mosaic_window():
    xs, ys = transform(WGS, MOLL, [BBOX[0], BBOX[2], BBOX[0], BBOX[2]],
                       [BBOX[1], BBOX[1], BBOX[3], BBOX[3]])
    c0 = max(0, int((min(xs) - X0) // CELL)); c1 = min(2000, int((max(xs) - X0) // CELL) + 1)
    r0 = max(0, int((Y1 - max(ys)) // CELL)); r1 = min(2000, int((Y1 - min(ys)) // CELL) + 1)
    return r0, r1, c0, c1


def read_ghsl(kind: str, epoch: int) -> np.ndarray:
    """Мозаика 2000x2000 одного продукта GHSL 1 км (NaN вместо nodata)."""
    mos = np.full((2000, 2000), np.nan, dtype="float64")
    prod = "BUILT_S" if kind == "built" else "POP"
    for tile, (tr, tc) in TILES.items():
        z = RAW / "ghsl" / f"GHS_{prod}_E{epoch}_GLOBE_R2023A_54009_1000_V1_0_{tile}.zip"
        name = [n for n in zipfile.ZipFile(z).namelist() if n.endswith(".tif")][0]
        with rasterio.open(f"zip://{z}!{name}") as s:
            a = s.read(1).astype("float64")
            if s.nodata is not None:
                a[a == s.nodata] = np.nan
            a[a < 0] = np.nan
        mos[tr * 1000:(tr + 1) * 1000, tc * 1000:(tc + 1) * 1000] = a
    return mos


def to_mosaic(src: np.ndarray, src_transform, src_crs, win, resampling=Resampling.average):
    """Перепроецировать грубый растр в окно мозаики (NaN вне покрытия)."""
    r0, r1, c0, c1 = win
    dst = np.full((r1 - r0, c1 - c0), np.nan, dtype="float64")
    dst_tr = MOSAIC * Affine.translation(c0, r0)
    reproject(source=src.astype("float64"), destination=dst, src_transform=src_transform,
              src_crs=src_crs, dst_transform=dst_tr, dst_crs=MOLL,
              src_nodata=np.nan, dst_nodata=np.nan, resampling=resampling)
    return dst


def combine(acc, new):
    return np.where(np.isnan(acc), new, acc)


def block_mean(a: np.ndarray, k: int) -> np.ndarray:
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    return a[:h, :w].reshape(h // k, k, w // k, k).mean(axis=(1, 3))


def read_wsf(win) -> dict[int, np.ndarray]:
    """Доля застройки в ячейке на конец года t (WSF Evolution: год появления)."""
    out = {t: None for t in WSF_YEARS}
    k = 30
    for f in sorted((RAW / "wsf").glob("WSFevolution_v1_*.tif")):
        with rasterio.open(f) as s:
            a = s.read(1)
            tr = s.transform
            for t in WSF_YEARS:
                frac = block_mean(((a > 0) & (a <= t)).astype("float32"), k)
                ctr = tr * Affine.scale(k, k)
                m = to_mosaic(frac, ctr, s.crs, win)
                out[t] = m if out[t] is None else combine(out[t], m)
        del a
    return out


def read_li(win) -> dict[int, np.ndarray]:
    out = {}
    for y, nm in LI_FILES.items():
        f = RAW / "li" / f"Harmonized_DN_NTL_{nm}.tif"
        with rasterio.open(f) as s:
            w = from_bounds(*BBOX, transform=s.transform).round_offsets().round_lengths()
            a = s.read(1, window=w).astype("float64")
            if s.nodata is not None:
                a[a == s.nodata] = np.nan
            out[y] = to_mosaic(a, s.window_transform(w), s.crs, win)
    return out


def read_vnl(win) -> dict[int, np.ndarray]:
    """VNL v2.1 (зеркало Zenodo): шкала по формуле проекта = тег масштаба x 0.1.

    До 2021 г. значения = радианс x10 с тегом 1, после — ~радианс с тегом 10
    (проверено 2026-10-04). Отрицательные значения до 2022 г. — переполнение
    int16 у очень ярких пикселей: возвращаем +65536.
    """
    out = {}
    for y in VNL_YEARS:
        with rasterio.open(VNL_URL.format(y=y)) as s:
            w = from_bounds(*BBOX, transform=s.transform).round_offsets().round_lengths()
            raw = s.read(1, window=w).astype("float64")
            nod = s.nodata
            tag = s.scales[0] if s.scales and s.scales[0] else 1.0
            if nod is not None:
                raw[raw == nod] = np.nan
            if y <= 2021:
                raw = np.where(raw < 0, raw + 65536.0, raw)
            a = np.clip(raw * tag * 0.1, 0.0, None)
            out[y] = to_mosaic(a, s.window_transform(w), s.crs, win)
    return out


def read_glad(win) -> dict[int, np.ndarray]:
    """Доля пашни (GLAD cropland 30 м) в ячейке: окна 1°x1°, блоки 32x32."""
    out = {}
    k = 32
    for y in GLAD_YEARS:
        acc = None
        for t in GLAD_TILES:
            f = RAW / "glad" / f"cropland_{y}_{t}.tif"
            with rasterio.open(f) as s:
                lon0 = max(BBOX[0], s.bounds.left); lon1 = min(BBOX[2], s.bounds.right)
                for lo in np.arange(math.floor(lon0), math.ceil(lon1), 1.0):
                    for la in np.arange(math.floor(BBOX[1]), math.ceil(BBOX[3]), 1.0):
                        wb = (max(lo, lon0), max(la, BBOX[1], s.bounds.bottom),
                              min(lo + 1, lon1), min(la + 1, BBOX[3], s.bounds.top))
                        if wb[2] - wb[0] < 0.01 or wb[3] - wb[1] < 0.01:
                            continue
                        w = from_bounds(*wb, transform=s.transform).round_offsets().round_lengths()
                        a = s.read(1, window=w)
                        if a.shape[0] < k or a.shape[1] < k:
                            continue
                        valid = (a <= 1)
                        frac = block_mean(np.where(valid, a, 0).astype("float32"), k)
                        vfrac = block_mean(valid.astype("float32"), k)
                        frac = np.where(vfrac > 0.5, frac / np.maximum(vfrac, 1e-6), np.nan)
                        ctr = s.window_transform(w) * Affine.scale(k, k)
                        m = to_mosaic(frac, ctr, s.crs, win)
                        acc = m if acc is None else combine(acc, m)
        out[y] = acc
    return out


# ---------------------------------------------------------------- города
def load_cities():
    z = zipfile.ZipFile(RAW / "misc" / "cities15000.zip")
    rows = []
    with z.open("cities15000.txt") as fh:
        for line in fh:
            p = line.decode("utf-8").rstrip("\n").split("\t")
            lat, lon, pop = float(p[4]), float(p[5]), int(p[14] or 0)
            if BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3] and pop >= CITY_MIN_POP:
                rows.append((p[1], lon, lat, pop, p[8]))
    return rows


# ---------------------------------------------------------------- сборка
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    by3035, neigh3035 = load_geoms()
    shapely.prepare(by3035)
    pieces, labels = boundary_pieces(by3035, neigh3035)
    tree = shapely.STRtree(pieces)
    win = mosaic_window()
    r0, r1, c0, c1 = win
    rr, cc = np.mgrid[r0:r1, c0:c1]
    xm = X0 + (cc + 0.5) * CELL
    ym = Y1 - (rr + 0.5) * CELL
    lon, lat = transform(MOLL, WGS, xm.ravel().tolist(), ym.ravel().tolist())
    x3, y3 = transform(WGS, LAEA, lon, lat)
    x3, y3 = np.array(x3), np.array(y3)
    pts = shapely.points(x3, y3)
    idx, dist = tree.query_nearest(pts, return_distance=True, all_matches=False)
    near_lab = np.empty(len(pts), dtype=object)
    near_lab[idx[0]] = labels[idx[1]]
    # подучасток границы: квадрат 1°x1° середины ближайшего куска (как у Pinkovskiy)
    mids = np.array([[p.interpolate(0.5, normalized=True).x, p.interpolate(0.5, normalized=True).y]
                     for p in pieces])
    mlon, mlat = transform(LAEA, WGS, mids[:, 0].tolist(), mids[:, 1].tolist())
    piece_key = np.array([f"{labels[i]}_{math.floor(mlon[i])}_{math.floor(mlat[i])}"
                          for i in range(len(pieces))])
    subseg = np.empty(len(pts), dtype=object)
    subseg[idx[0]] = piece_key[idx[1]]
    dmin = np.full(len(pts), np.inf)
    dmin[idx[0]] = dist
    inside = shapely.contains_xy(by3035, x3, y3)
    keep = dmin <= BAND_KM * 1000
    seg = near_lab.copy()
    for iso, g in neigh3035.items():
        shapely.prepare(g)
        hit = keep & ~inside & shapely.contains_xy(g, x3, y3)
        seg[hit] = SEG[iso]
    side = np.where(inside, "BY", seg)
    # снаружи, но не у соседа (например, Балтика/третья страна) — отбросить
    outside_nb = ~inside & keep
    in_any = np.zeros(len(pts), dtype=bool)
    for g in neigh3035.values():
        in_any |= shapely.contains_xy(g, x3, y3)
    keep &= inside | in_any
    d_km = np.where(inside, -dmin, dmin) / 1000.0

    cities = load_cities()
    cpts = shapely.points(*transform(WGS, LAEA, [c[1] for c in cities], [c[2] for c in cities]))
    ctree = shapely.STRtree(cpts)
    cidx, cdist = ctree.query_nearest(pts, return_distance=True, all_matches=False)
    dcity = np.full(len(pts), np.inf); dcity[cidx[0]] = cdist
    ncity = np.full(len(pts), -1); ncity[cidx[0]] = cidx[1]
    chx, chy = transform(WGS, LAEA, [CHNPP[0]], [CHNPP[1]])
    dchern = np.hypot(x3 - chx[0], y3 - chy[0]) / 1000.0

    print("ячеек в окне:", len(pts), "в полосе:", int(keep.sum()))
    built = {e: read_ghsl("built", e)[r0:r1, c0:c1].ravel() for e in GHSL_BUILT_EPOCHS}
    pop = {e: read_ghsl("pop", e)[r0:r1, c0:c1].ravel() for e in GHSL_POP_EPOCHS}
    print("GHSL ok"); wsf = {t: v.ravel() for t, v in read_wsf(win).items()}
    print("WSF ok"); li = {y: v.ravel() for y, v in read_li(win).items()}
    print("Li ok"); vnl = {y: v.ravel() for y, v in read_vnl(win).items()}
    print("VNL ok"); glad = {y: v.ravel() for y, v in read_glad(win).items()}
    print("GLAD ok")

    cols = (["cell", "lon", "lat", "x3035", "y3035", "side", "seg", "subseg", "d_km", "city_km",
             "city", "chern_km"]
            + [f"built_{e}" for e in GHSL_BUILT_EPOCHS] + [f"pop_{e}" for e in GHSL_POP_EPOCHS]
            + [f"wsf_{t}" for t in WSF_YEARS] + [f"li_{y}" for y in LI_FILES]
            + [f"vnl_{y}" for y in VNL_YEARS] + [f"crop_{y}" for y in GLAD_YEARS])

    def fmt(v, nd):
        return "" if (v is None or (isinstance(v, float) and not math.isfinite(v))) else f"{v:.{nd}f}"

    sel = np.nonzero(keep)[0]
    rows_ = rr.ravel(); cols_ = cc.ravel()
    with gzip.open(OUT / "cells.csv.gz", "wt", newline="", encoding="utf-8", compresslevel=9) as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for i in sel:
            rec = [f"{rows_[i]}_{cols_[i]}", f"{lon[i]:.4f}", f"{lat[i]:.4f}",
                   f"{x3[i]:.0f}", f"{y3[i]:.0f}", side[i], seg[i], subseg[i], f"{d_km[i]:.3f}",
                   fmt(dcity[i] / 1000.0, 2), cities[ncity[i]][0] if ncity[i] >= 0 else "",
                   fmt(dchern[i], 2)]
            rec += [fmt(built[e][i], 0) for e in GHSL_BUILT_EPOCHS]
            rec += [fmt(pop[e][i], 1) for e in GHSL_POP_EPOCHS]
            rec += [fmt(wsf[t][i] * 1e6, 0) for t in WSF_YEARS]
            rec += [fmt(li[y][i], 3) for y in LI_FILES]
            rec += [fmt(vnl[y][i], 3) for y in VNL_YEARS]
            rec += [fmt(glad[y][i], 4) for y in GLAD_YEARS]
            w.writerow(rec)
    json.dump([{"name": c[0], "lon": c[1], "lat": c[2], "pop": c[3], "cc": c[4]} for c in cities],
              open(OUT / "cities50k.json", "w"), ensure_ascii=False, indent=1)
    print("OK:", OUT / "cells.csv.gz", len(sel), "ячеек")


if __name__ == "__main__":
    main()
