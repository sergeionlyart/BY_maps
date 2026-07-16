"""INF-12: зональная ночная светимость по городским маскам (однократный шаг).

Источник света - вырезки INF-08 v2 (data/raw/nightlights/rasters, EPSG:4326,
факелы НПЗ обнулены): DMSP 1992-2013 (calDMSP Li et al., DN 0-63, ~1 км),
VNL 2012-2024 (EOG VNL v2.1, нВт/см²/ср, ~500 м).

Маски городов - MORPH_FIXED_FRAME основного сценария (t10_c1) из
etl/urban_morph.py (Молльвейде, 100 м). Схема пересчёта: карта владельцев
репроецируется nearest на суперсетку 4326 (1/10 пикселя DMSP = 1/5 пикселя
VNL), свет каждого пикселя делится между городами пропорционально числу
суперячеек - суммы по стране сохраняются, малые города не теряют пиксели.

Зоны: total (вся фикс-рамка), core (контур 1975), edge (ячейки, вошедшие
в фонд после 1975), buffer (ячейки рамки, не входившие в фонд ни в одну
эпоху). Пороги фона - как в INF-08: VNL >= 1.0 нВт, DMSP DN >= 1.

Выход (вендорится): data/raw/urban/city_light.csv
  sensor,year,city_id,light_total,light_core,light_edge,light_buffer
  + строка city_id=__national__ (вся страна, для долевой нормализации).

Запуск (требует rasterio+numpy; однократно, после etl.urban_morph):
  python -m etl.urban_light
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject

from .common import ROOT
from .urban_morph import PRIMARY_SC, TMP, load_registry

RAW = ROOT / "data" / "raw" / "urban"
NL = ROOT / "data" / "raw" / "nightlights" / "rasters"

DMSP_YEARS = list(range(1992, 2014))
VNL_YEARS = list(range(2012, 2025))
VNL_THRESHOLD = 1.0
DMSP_THRESHOLD = 1

# Суперсетка: границы вырезок INF-08, шаг = 1/10 DMSP (1/5 VNL)
S_BOUNDS = (23.1, 51.2, 32.85, 56.25)
S_W, S_H = 11_700, 6_060
CLIP_MINX, CLIP_MAXY, CELL = 1_591_500.0, 6_511_500.0, 100.0


def super_transform():
    from rasterio.transform import from_bounds
    return from_bounds(*S_BOUNDS, S_W, S_H)


def reproject_zones() -> tuple[np.ndarray, np.ndarray]:
    """(owner_super uint8, zone_super uint8: 1=core 2=edge 3=buffer)."""
    from rasterio.transform import from_origin
    z = np.load(TMP / f"fixed_{PRIMARY_SC}.npz")
    fixed_owner, entry = z["fixed_owner"], z["entry"]
    zone = np.zeros_like(fixed_owner)
    zone[(fixed_owner > 0) & (entry == 1)] = 1
    zone[(fixed_owner > 0) & (entry >= 2)] = 2
    zone[(fixed_owner > 0) & (entry == 0)] = 3
    src_transform = from_origin(CLIP_MINX, CLIP_MAXY, CELL, CELL)
    dst = super_transform()
    out_owner = np.zeros((S_H, S_W), np.uint8)
    out_zone = np.zeros((S_H, S_W), np.uint8)
    for src, out in ((fixed_owner, out_owner), (zone, out_zone)):
        reproject(source=src, destination=out,
                  src_transform=src_transform, src_crs="ESRI:54009",
                  dst_transform=dst, dst_crs="EPSG:4326",
                  resampling=Resampling.nearest)
    return out_owner, out_zone


def light_super(path: Path, factor: int, threshold: float) -> np.ndarray:
    """Свет, перенесённый на суперсетку с делением на factor² (сохранение сумм).

    Перенос учитывает фактическую геопривязку растра (nearest-ресемплинг по
    трансформациям, а не naive repeat): origin отдельных вырезок INF-08 смещён
    на доли пикселя относительно номинальных границ S_BOUNDS.
    """
    with rasterio.open(path) as s:
        a = s.read(1).astype(np.float64)
        src_transform, src_crs = s.transform, s.crs
    a[a < threshold] = 0.0
    dst = np.zeros((S_H, S_W), np.float64)
    reproject(source=a, destination=dst,
              src_transform=src_transform, src_crs=src_crs,
              dst_transform=super_transform(), dst_crs="EPSG:4326",
              resampling=Resampling.nearest)
    return dst / (factor * factor)


def main() -> None:
    cities = load_registry()
    ids = [c["city_id"] for c in cities]
    n = len(ids)
    owner, zone = reproject_zones()
    rows: list[dict] = []

    def city_sums(light: np.ndarray) -> dict[str, np.ndarray]:
        res = {}
        res["total"] = np.bincount(owner.ravel(), weights=light.ravel(),
                                   minlength=n + 1)[1:]
        for name, code in (("core", 1), ("edge", 2), ("buffer", 3)):
            o = np.where(zone == code, owner, 0)
            res[name] = np.bincount(o.ravel(), weights=light.ravel(),
                                    minlength=n + 1)[1:]
        return res

    jobs = ([("dmsp", y, NL / f"dmsp_{y}.tif", 10, DMSP_THRESHOLD)
             for y in DMSP_YEARS] +
            [("vnl", y, NL / f"vnl_{y}.tif", 5, VNL_THRESHOLD)
             for y in VNL_YEARS])
    for sensor, year, path, factor, thr in jobs:
        light = light_super(path, factor, thr)
        national = float(light.sum())
        sums = city_sums(light)
        for i in range(n):
            rows.append({
                "sensor": sensor, "year": year, "city_id": ids[i],
                "light_total": round(float(sums["total"][i]), 3),
                "light_core": round(float(sums["core"][i]), 3),
                "light_edge": round(float(sums["edge"][i]), 3),
                "light_buffer": round(float(sums["buffer"][i]), 3),
            })
        rows.append({
            "sensor": sensor, "year": year, "city_id": "__national__",
            "light_total": round(national, 3),
            "light_core": "", "light_edge": "", "light_buffer": "",
        })
        print(f"{sensor} {year}: national {national:.0f}")

    RAW.mkdir(parents=True, exist_ok=True)
    out = RAW / "city_light.csv"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{out}: {len(rows)} строк")


if __name__ == "__main__":
    main()
