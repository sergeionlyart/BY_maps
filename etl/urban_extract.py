"""INF-12: мозаика и клип GHS-BUILT-S R2023A по Беларуси (однократный шаг).

Источник: GHSL GHS-BUILT-S R2023A, 100 м, Молльвейде (ESRI:54009),
эпохи 1975-2020 (10 шт.). Эпохи 2025/2030 продукта - модельные
экстраполяции, в исследовании НЕ используются как наблюдения.
Беларусь покрывают 4 тайла: R3_C20, R3_C21, R4_C20, R4_C21.

Тайлы (~9-25 МБ каждый) не вендорятся - фиксируются URL+sha256 в
data/raw/urban/registry_ghsl.csv. Вендорятся производные зональные
агрегаты (etl/urban_morph.py). Национальные клипы built_E<год>.tif
(~5180x8835, uint16, м² застройки на ячейку 1 га) лежат в
data/raw/urban/rasters/ (в .gitignore).

Запуск (требует rasterio+numpy; однократно):
  python -m etl.urban_extract          # клипы из data/raw/ghsl/tiles
  GHSL_FETCH=1 python -m etl.urban_extract   # + докачать недостающие тайлы
"""
from __future__ import annotations

import csv
import hashlib
import os
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge

from .common import ROOT

RAW = ROOT / "data" / "raw" / "urban"
TILES = ROOT / "data" / "raw" / "ghsl" / "tiles"
RASTERS = RAW / "rasters"

EPOCHS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020]
TILE_IDS = ["R3_C20", "R3_C21", "R4_C20", "R4_C21"]
BASE_URL = ("https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/"
            "GHS_BUILT_S_GLOBE_R2023A/GHS_BUILT_S_E{epoch}_GLOBE_R2023A_54009_100/"
            "V1-0/tiles/{name}.zip")

# Клип-рамка Беларуси в Молльвейде, выровнена на сетку 100 м GHSL
# (bbox страны + ~5 км запаса).
CLIP = (1591500.0, 5993500.0, 2475000.0, 6511500.0)  # minx, miny, maxx, maxy
LICENSE = ("CC BY 4.0 (Joint Research Centre, European Commission; "
           "Pesaresi & Politis 2023, GHS-BUILT-S R2023A)")


def tile_name(epoch: int, tile: str) -> str:
    return f"GHS_BUILT_S_E{epoch}_GLOBE_R2023A_54009_100_V1_0_{tile}"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_missing() -> None:
    TILES.mkdir(parents=True, exist_ok=True)
    for epoch in EPOCHS:
        for tile in TILE_IDS:
            name = tile_name(epoch, tile)
            out = TILES / f"{name}.zip"
            if out.exists():
                continue
            url = BASE_URL.format(epoch=epoch, name=name)
            print("fetch", name)
            urllib.request.urlretrieve(url, out)


def clip_epoch(epoch: int) -> Path:
    """Мозаика 4 тайлов эпохи + клип Беларуси -> built_E<epoch>.tif."""
    out = RASTERS / f"built_E{epoch}.tif"
    srcs = []
    for tile in TILE_IDS:
        z = TILES / f"{tile_name(epoch, tile)}.zip"
        with zipfile.ZipFile(z) as zf:
            tif = next(n for n in zf.namelist() if n.endswith(".tif"))
        srcs.append(rasterio.open(f"zip://{z}!/{tif}"))
    arr, transform = merge(srcs, bounds=CLIP)
    profile = {
        "driver": "GTiff", "dtype": "uint16", "count": 1,
        "width": arr.shape[2], "height": arr.shape[1],
        "crs": srcs[0].crs, "transform": transform,
        "compress": "deflate", "predictor": 2, "tiled": True,
        "nodata": 65535,
    }
    for s in srcs:
        s.close()
    data = arr[0].astype(np.uint16)
    with rasterio.open(out, "w", **profile) as dst:
        dst.write(data, 1)
    return out


def write_registry() -> None:
    rows = []
    for epoch in EPOCHS:
        for tile in TILE_IDS:
            name = tile_name(epoch, tile)
            z = TILES / f"{name}.zip"
            rows.append({
                "id": f"ghsl_{epoch}_{tile.lower()}",
                "title": f"GHS-BUILT-S R2023A эпоха {epoch}, тайл {tile} "
                         "(100 м, Молльвейде)",
                "url": BASE_URL.format(epoch=epoch, name=name),
                "license": LICENSE,
                "accessed": "2026-07-16",
                "sha256": sha256(z) if z.exists() else "",
                "size_bytes": z.stat().st_size if z.exists() else "",
                "vendored": "no",
                "notes": "глобальный тайл; клип Беларуси - "
                         f"data/raw/urban/rasters/built_E{epoch}.tif",
            })
    reg = RAW / "registry_ghsl.csv"
    with reg.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"registry: {len(rows)} тайлов -> {reg}")


def main() -> None:
    RASTERS.mkdir(parents=True, exist_ok=True)
    if os.environ.get("GHSL_FETCH"):
        fetch_missing()
    for epoch in EPOCHS:
        out = RASTERS / f"built_E{epoch}.tif"
        if out.exists():
            print("skip", out.name)
            continue
        p = clip_epoch(epoch)
        with rasterio.open(p) as s:
            a = s.read(1)
            total = float(a[(a > 0) & (a != 65535)].sum())
        print(f"{p.name}: built {total / 1e6:.1f} km²")
    write_registry()


if __name__ == "__main__":
    main()
