"""INF-15, шаг 1б: мозаика тайлов GHS-POP + единая сетка 1 км по Беларуси.

Берёт 4 тайла на эпоху из data/raw/ghsl/tiles/ (см. etl/grid_fetch.py),
собирает мозаику, обрезает по замороженной рамке (docs/preregistration/
grid-v0.1.md, раздел 6: clip_bbox_moll) и маскирует по границе страны
(union adm1, репроецированный в ESRI:54009). Решётка одинакова для всех
эпох (общий transform/width/height) - обязательное условие сравнимости
кадров и проверки G-2.

Расчётная проекция - ESRI:54009 (Молльвейде), НЕ EPSG:3857 из примера
Приложения А ТЗ: решение D-001 в docs/decisions/INF-15.md (равновеликая
сетка сохраняет обещанный размер ячейки "1 км" на широте Беларуси; в
Web Mercator ячейка исказилась бы в 2.5-3.2 раза по площади).

Пиксели вне Беларуси зануляются (nodata=0). Значения источника - float64,
GHS-POP хранит численность людей на ячейку (не плотность per км² -
но при ячейке ровно 1 км² это численно совпадает); пишем float32,
округление до 3 знаков (доли человека на ячейку - артефакт дазиметрической
интерполяции, не подделка точности).

Запуск (требует rasterio+numpy; однократно):
  python -m etl.grid_extract
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.merge import merge
from rasterio.warp import transform_geom

from .common import ROOT, OUT
from .grid_fetch import EPOCHS, TILE_IDS, TILES, tile_name

RAW = ROOT / "data" / "raw" / "grid"
RASTERS = RAW / "rasters"

# Клип-рамка Беларуси в Молльвейде, выровнена на сетку 1000 м GHSL
# (bbox страны + запас; см. пререгистрацию, раздел 6).
CLIP = (1602000.0, 5998000.0, 2459000.0, 6512000.0)  # minx, miny, maxx, maxy


def _country_geom_moll() -> list:
    """Union полигонов adm1 (EPSG:4326), репроецированный в ESRI:54009."""
    g1 = json.loads((OUT / "geo" / "adm1.geojson").read_text())
    out = []
    for f in g1["features"]:
        out.append(transform_geom("EPSG:4326", "ESRI:54009", f["geometry"]))
    return out


def clip_epoch(epoch: int, country_geoms: list) -> Path:
    RASTERS.mkdir(parents=True, exist_ok=True)
    out = RASTERS / f"pop_{epoch}.tif"
    srcs = []
    for tile in TILE_IDS:
        z = TILES / f"{tile_name(epoch, tile)}.zip"
        with zipfile.ZipFile(z) as zf:
            tif = next(n for n in zf.namelist() if n.endswith(".tif"))
        srcs.append(rasterio.open(f"zip://{z}!/{tif}"))
    arr, transform = merge(srcs, bounds=CLIP, res=(1000.0, 1000.0))
    crs = srcs[0].crs
    nodata_vals = [s.nodata for s in srcs]
    for s in srcs:
        s.close()

    data = arr[0].astype("float64")
    # GHS-POP: nodata = -200 (нет данных, не "0 людей") -> обнуляем перед
    # маской страны (за пределами страны всё равно занулится).
    nd = nodata_vals[0] if nodata_vals[0] is not None else -200.0
    data = np.where(data == nd, 0.0, data)
    data = np.clip(data, 0.0, None)

    mask = rasterize(((g, 1) for g in country_geoms), out_shape=data.shape,
                      transform=transform, fill=0, dtype="uint8",
                      all_touched=True)
    data = np.where(mask == 1, data, 0.0)
    data = np.round(data, 3).astype("float32")

    profile = {
        "driver": "GTiff", "dtype": "float32", "count": 1,
        "width": data.shape[1], "height": data.shape[0],
        "crs": crs, "transform": transform,
        "compress": "deflate", "predictor": 3, "tiled": True,
        "nodata": 0.0,
    }
    with rasterio.open(out, "w", **profile) as dst:
        dst.write(data, 1)
    return out


def write_grid_meta(ref_epoch: int = 2020) -> Path:
    """Метаданные единой решётки (общие для всех эпох) - для grid.py/grid.json."""
    ref = RASTERS / f"pop_{ref_epoch}.tif"
    with rasterio.open(ref) as s:
        bounds = s.bounds
        meta = {
            "crs": str(s.crs),
            "cell_m": 1000,
            "width": s.width,
            "height": s.height,
            "transform": list(s.transform)[:6],
            "bounds_moll": [bounds.left, bounds.bottom, bounds.right, bounds.top],
            "note": "единая решётка для всех эпох (1975-2050); проекция "
                    "ESRI:54009 (Молльвейде) - см. docs/decisions/INF-15.md D-001",
        }
    p = RAW / "grid_meta.json"
    p.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    print(f"grid_meta -> {p} ({meta['width']}x{meta['height']})")
    return p


def main() -> None:
    geoms = _country_geom_moll()
    for epoch in EPOCHS:
        out = RASTERS / f"pop_{epoch}.tif"
        if out.exists():
            print("skip", out.name)
            continue
        p = clip_epoch(epoch, geoms)
        with rasterio.open(p) as s:
            a = s.read(1)
            total = float(a.sum())
            n_cells = int((a > 0).sum())
        print(f"{p.name}: pop {total:,.0f} на {n_cells:,} заселённых ячейках "
              f"из {a.size:,} ({s.width}x{s.height})")
    write_grid_meta()


if __name__ == "__main__":
    main()
