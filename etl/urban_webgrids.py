"""INF-12: пер-городские сетки для веб-инфографики «физический след».

Для каждого города основной выборки создаёт web/public/data/urban/city_<id>.json:
  - grids[эпоха]  - PNG (grayscale, base64): доля застройки ячейки 0..255
                    (255 = ячейка застроена полностью), окно вокруг города;
  - entry         - PNG: 255=вне фикс-рамки города, 0=буфер рамки (не входил
                    в фонд), 1..10=индекс эпохи первого входа в фонд;
  - light         - PNG: VNL 2013/2024 (лог-шкала), ~500 м, ресемпл nearest
                    на сетку окна (маркируется в UI как грубое разрешение).

Окно: bbox фикс-рамки города + 12 ячеек запаса (Молльвейде, 100 м).
PNG декодируется в браузере через canvas.drawImage + getImageData.

Запуск (требует numpy+rasterio+PIL; после etl.urban_morph):
  python -m etl.urban_webgrids
"""
from __future__ import annotations

import base64
import io
import json

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject

from .common import OUT, ROOT
from .urban_morph import (CLIP_MINX, CLIP_MAXY, CELL, EPOCHS, PRIMARY_SC,
                          RASTERS, TMP, load_registry, read_epoch)

WEB_URBAN = OUT / "urban"
NL = ROOT / "data" / "raw" / "nightlights" / "rasters"
MARGIN = 12
LIGHT_YEARS = [("vnl", 2013), ("vnl", 2024)]
LIGHT_LOG_MAX = 5.0   # ln(1+нВт), верх шкалы 255


def png_b64(arr: np.ndarray) -> str:
    img = Image.fromarray(arr, mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def main() -> None:
    WEB_URBAN.mkdir(parents=True, exist_ok=True)
    cities = load_registry()
    z = np.load(TMP / f"fixed_{PRIMARY_SC}.npz")
    fixed_owner, entry = z["fixed_owner"], z["entry"]
    epoch_arrays = {e: read_epoch(e) for e in EPOCHS}
    light_src = {}
    for sensor, year in LIGHT_YEARS:
        with rasterio.open(NL / f"{sensor}_{year}.tif") as s:
            light_src[(sensor, year)] = (s.read(1), s.transform, s.crs)

    for i, c in enumerate(cities):
        code = i + 1
        mask = fixed_owner == code
        if not mask.any():
            print("skip (нет рамки):", c["city_id"])
            continue
        rows = np.any(mask, axis=1).nonzero()[0]
        cols = np.any(mask, axis=0).nonzero()[0]
        r0 = int(max(0, rows[0] - MARGIN))
        r1 = int(min(mask.shape[0], rows[-1] + MARGIN + 1))
        c0 = int(max(0, cols[0] - MARGIN))
        c1 = int(min(mask.shape[1], cols[-1] + MARGIN + 1))
        h, w = r1 - r0, c1 - c0
        win_owner = fixed_owner[r0:r1, c0:c1]
        win_entry = entry[r0:r1, c0:c1]
        entry_png = np.where(win_owner == code, win_entry, 255).astype(np.uint8)
        grids = {}
        for e in EPOCHS:
            a = epoch_arrays[e][r0:r1, c0:c1].astype(np.float32)
            grids[str(e)] = png_b64(
                np.clip(a / 10_000.0 * 255.0, 0, 255).astype(np.uint8))
        # свет: ресемпл на сетку окна
        win_transform = from_origin(CLIP_MINX + c0 * CELL,
                                    CLIP_MAXY - r0 * CELL, CELL, CELL)
        light = {}
        for (sensor, year), (arr, tr, crs) in light_src.items():
            dst = np.zeros((h, w), np.float32)
            reproject(source=arr, destination=dst,
                      src_transform=tr, src_crs=crs,
                      dst_transform=win_transform, dst_crs="ESRI:54009",
                      resampling=Resampling.nearest)
            scaled = np.clip(np.log1p(np.maximum(dst, 0)) / LIGHT_LOG_MAX
                             * 255.0, 0, 255).astype(np.uint8)
            light[f"{sensor}{year}"] = png_b64(scaled)
        payload = {
            "id": c["city_id"], "w": w, "h": h,
            "cellM": 100,
            "epochs": EPOCHS,
            "grids": grids,
            "entry": png_b64(entry_png),
            "light": light,
            "lightNote": "VNL ~500 м, лог-шкала; грубее сетки застройки",
        }
        (WEB_URBAN / f"city_{c['city_id']}.json").write_text(
            json.dumps(payload, separators=(",", ":")))
    print("web grids:", len(cities), "->", WEB_URBAN)


if __name__ == "__main__":
    main()
