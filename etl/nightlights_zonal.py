"""INF-08 v2, шаг 2: зональная агрегация светимости 1992-2024.

Вход - вырезки Беларуси (etl/nightlights_fetch.py):
  data/raw/nightlights/rasters/dmsp_<1992-2013>.tif  (Li calDMSP, DN 0-63)
  data/raw/nightlights/rasters/vnl_<2012-2024>.tif   (EOG VNL v2.1, нВт/см²/ср)
плюс невендоримые глобальные simVIIRS (NL_SRC) - для спайка гармонизации.

Зоны: 118 районов (adm2) + Минск (adm1 BY-HM), растеризация по центру
пикселя, Минск поверх (в adm2 он «дыра» Минского района) - как в v1.

Выход (вендорится):
  zonal_dmsp.csv      zone_id, year, dn_sum, lit_km2
  zonal_vnl.csv       zone_id, year, radiance, lit_km2
  zonal_simviirs.csv  zone_id, year, dn_sum, lit_km2   (спайк)
Плюс строка zone_id=BY - сумма по всему клипу страны (маска all_touched
шире объединения зон на приграничные пиксели; допуск - в тестах).

Пороги: VNL - радиансность >= 1,0 нВт/см²/ср (фон, как в v1);
DMSP/simVIIRS - DN >= 1 (продукт stable lights уже отфильтрован).
lit_km2 - площадь освещённых пикселей с поправкой cos(широты).

Запуск (требует rasterio+numpy; однократно):
  NL_SRC=<кэш> python -m etl.nightlights_zonal
"""
from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize

from .common import ROOT, OUT
from .nightlights_fetch import DMSP_YEARS, SIM_YEARS, VNL_YEARS, RASTERS, RAW

VNL_THRESHOLD = 1.0   # нВт/см²/ср, фон VNL average - как DIM_THRESHOLD v1
DN_THRESHOLD = 1      # DN, stable lights уже без фона


def zone_labels(ref: rasterio.DatasetReader):
    """Растеризация 118 районов + Минска на сетку ref -> (labels, ids)."""
    g2 = json.loads((OUT / "geo" / "adm2.geojson").read_text())
    g1 = json.loads((OUT / "geo" / "adm1.geojson").read_text())
    raions = [f for f in g2["features"]
              if f["properties"]["id"].startswith("r-")]
    ids = [f["properties"]["id"] for f in raions]
    feats = [(f["geometry"], i + 1) for i, f in enumerate(raions)]
    minsk = next(f for f in g1["features"]
                 if f["properties"]["id"] == "BY-HM")
    ids.append("BY-HM")
    feats.append((minsk["geometry"], len(ids)))   # Минск последним - поверх
    labels = rasterize(feats, out_shape=(ref.height, ref.width),
                       transform=ref.transform, fill=0, dtype="int32")
    return labels, ids


def _px_area_km2(ref: rasterio.DatasetReader) -> np.ndarray:
    """Площадь пикселя (км²) по строкам сетки, поправка cos(широты)."""
    t = ref.transform
    dlon, dlat = abs(t.a), abs(t.e)
    lats = np.array([t.f + t.e * (r + 0.5) for r in range(ref.height)])
    return (dlon * 111.32) * (dlat * 111.32) * np.cos(np.radians(lats))


def _aggregate(path: Path, labels, ids, area_rows, threshold) -> list[dict]:
    with rasterio.open(path) as s:
        a = s.read(1).astype("float64")
    mask = a >= threshold
    vals = np.where(mask, a, 0.0)
    area = np.broadcast_to(area_rows[:, None], a.shape)
    lit_area = np.where(mask, area, 0.0)
    lab = labels.ravel()
    n = len(ids)
    vsum = np.bincount(lab, weights=vals.ravel(), minlength=n + 1)
    asum = np.bincount(lab, weights=lit_area.ravel(), minlength=n + 1)
    rows = [{"zone_id": z, "value": vsum[i + 1], "lit_km2": asum[i + 1]}
            for i, z in enumerate(ids)]
    rows.append({"zone_id": "BY", "value": float(vals.sum()),
                 "lit_km2": float(lit_area.sum())})
    return rows


def _write(path: Path, rows: list[dict], value_col: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["zone_id", "year", value_col, "lit_km2"])
        for r in rows:
            w.writerow([r["zone_id"], r["year"],
                        round(r["value"], 3), round(r["lit_km2"], 3)])


def run_segment(paths: dict[int, Path], threshold, ndec=3) -> list[dict]:
    ref_path = paths[sorted(paths)[-1]]
    with rasterio.open(ref_path) as ref:
        labels, ids = zone_labels(ref)
        area_rows = _px_area_km2(ref)
        shape = (ref.height, ref.width)
    out = []
    for y in sorted(paths):
        with rasterio.open(paths[y]) as s:
            if (s.height, s.width) != shape:
                raise SystemExit(f"{paths[y].name}: сетка {s.width}x"
                                 f"{s.height} != опорной {shape[1]}x{shape[0]}")
        for r in _aggregate(paths[y], labels, ids, area_rows, threshold):
            out.append({**r, "year": y})
        print(f"  {paths[y].name}: ok")
    return out


def write_floor(floor_max: float = 5.0) -> None:
    """floor_2024.csv: разложение света 2024 на «инфраструктурный пол»
    (пиксели VNL_THRESHOLD..floor_max нВт - дороги, рассеянная подсветка)
    и «яркую» компоненту (>= floor_max - населённые пункты, объекты).
    Инвариант: floor + bright = зональная радиансность 2024."""
    path = RASTERS / "vnl_2024.tif"
    with rasterio.open(path) as ref:
        labels, ids = zone_labels(ref)
        a = ref.read(1).astype("float64")
    lab = labels.ravel()
    n = len(ids)
    lit = a >= VNL_THRESHOLD
    dim = lit & (a < floor_max)
    bright = a >= floor_max
    fsum = np.bincount(lab, weights=np.where(dim, a, 0.0).ravel(),
                       minlength=n + 1)
    bsum = np.bincount(lab, weights=np.where(bright, a, 0.0).ravel(),
                       minlength=n + 1)
    with open(RAW / "floor_2024.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["zone_id", "floor_radiance", "bright_radiance",
                    "floor_max_nw"])
        for i, z in enumerate(ids):
            w.writerow([z, round(fsum[i + 1], 3), round(bsum[i + 1], 3),
                        floor_max])
    print(f"OK: floor_2024.csv (порог {floor_max} нВт)")


def main() -> None:
    src = Path(os.environ.get("NL_SRC", ROOT / "data" / "tmp" / "nl_src"))

    dmsp = {y: RASTERS / f"dmsp_{y}.tif" for y in DMSP_YEARS}
    vnl = {y: RASTERS / f"vnl_{y}.tif" for y in VNL_YEARS}
    sim = {y: src / "dmsp" / (f"DN_NTL_{y}_simVIIRS.tif" if y == 2013 else
                              f"Harmonized_DN_NTL_{y}_simVIIRS.tif")
           for y in SIM_YEARS}
    for name, d in [("dmsp", dmsp), ("vnl", vnl), ("simviirs", sim)]:
        missing = [y for y, p in d.items() if not p.exists()]
        if missing:
            raise SystemExit(f"{name}: нет файлов {missing}")

    print("DMSP 1992-2013 (вырезки):")
    _write(RAW / "zonal_dmsp.csv",
           run_segment(dmsp, DN_THRESHOLD), "dn_sum")
    print("VNL 2012-2024 (вырезки):")
    _write(RAW / "zonal_vnl.csv",
           run_segment(vnl, VNL_THRESHOLD), "radiance")
    print("simVIIRS 2013-2024 (глобальные, спайк) - вырезка на лету:")
    # simVIIRS не вендорится: агрегируем по окну bbox из глобального файла
    from .nightlights_fetch import BBOX, _country_geom
    from rasterio.windows import from_bounds
    import tempfile
    geoms = _country_geom()
    rows = []
    with tempfile.TemporaryDirectory() as td:
        clip_paths = {}
        for y, g in sorted(sim.items()):
            dst = Path(td) / f"sim_{y}.tif"
            from .nightlights_fetch import _clip
            _clip(g, dst, geoms, "uint8", None)
            clip_paths[y] = dst
        rows = run_segment(clip_paths, DN_THRESHOLD)
    _write(RAW / "zonal_simviirs.csv", rows, "dn_sum")

    write_floor()

    for f in ["zonal_dmsp.csv", "zonal_vnl.csv", "zonal_simviirs.csv",
              "floor_2024.csv"]:
        n = sum(1 for _ in open(RAW / f)) - 1
        print(f"OK: {f} ({n} строк)")


if __name__ == "__main__":
    main()
