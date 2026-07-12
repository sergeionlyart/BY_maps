"""INF-08: зональная светимость по районам из годовых композитов VIIRS.

Источник: WorldPop VIIRS night-time-lights covariate, Беларусь
(Global_2015_2030, вариант fvf - flares/volcanoes-filtered), 2015-2023 -
это подлинный годовой продукт EOG «average_masked» VNL 2.1/2.2 (Colorado
School of Mines / Payne Institute), ресемплированный на 100 м и обрезанный
по стране. Файлы (~30 МБ/год) в репозиторий не вендорятся - их URL и
sha256 фиксируются в data/raw/nightlights/registry.csv; вендорится
итоговая зональная сумма (data/raw/nightlights/zonal_light.csv), с которой
дальше работает etl/nightlights.py на стандартной библиотеке.

Зоны: 118 районов (adm2) + Минск (adm1 BY-HM; в adm2 он «дыра» Минского
района). Растеризация полигонов на сетку композита, сумма радиометрии
(порог > 1 нВт/см²/ср, отсечка фонового шума) по каждой зоне.

Запуск (требует rasterio; однократно):
  NL_SRC=<каталог с blr_<год>.tif> python -m etl.nightlights_extract
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize

from .common import ROOT, OUT

RAW = ROOT / "data" / "raw" / "nightlights"
YEARS = list(range(2015, 2024))
DIM_THRESHOLD = 1.0   # нВт/см²/ср: ниже - фоновый шум VIIRS

WP_URL = ("https://data.worldpop.org/GIS/Covariates/Global_2015_2030/"
          "BLR/VIIRS/v1/fvf/blr_viirs_fvf_{year}_100m_v1.tif")


def _zone_labels(ref_tif: Path):
    """Растеризация 118 районов + Минска на сетку композита -> (labels, ids)."""
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
    with rasterio.open(ref_tif) as s:
        labels = rasterize(feats, out_shape=(s.height, s.width),
                           transform=s.transform, fill=0, dtype="int32")
    return labels, ids


def main() -> None:
    src = Path(os.environ.get("NL_SRC", RAW / "wp_src"))
    tifs = {y: src / f"blr_{y}.tif" for y in YEARS}
    missing = [y for y, p in tifs.items() if not p.exists()]
    if missing:
        raise SystemExit(f"нет исходных композитов {missing} в {src}; "
                         f"скачайте WorldPop fvf (URL в registry.csv)")

    labels, ids = _zone_labels(tifs[2019])
    n = len(ids)
    rows = []
    checksums = {}
    for y in YEARS:
        with rasterio.open(tifs[y]) as s:
            a = s.read(1).astype("float64")
            nd = s.nodata
        checksums[y] = hashlib.sha256(tifs[y].read_bytes()).hexdigest()
        mask = (a != nd) & (a >= DIM_THRESHOLD)
        rad = np.where(mask, a, 0.0)
        lab = labels.ravel()
        rsum = np.bincount(lab, weights=rad.ravel(), minlength=n + 1)
        lit = np.bincount(lab, weights=mask.ravel().astype("float64"),
                          minlength=n + 1)
        for i, zid in enumerate(ids):
            rows.append({"zone_id": zid, "year": y,
                         "radiance": round(float(rsum[i + 1]), 3),
                         "lit_px": int(lit[i + 1])})

    RAW.mkdir(parents=True, exist_ok=True)
    with open(RAW / "zonal_light.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["zone_id", "year", "radiance",
                                          "lit_px"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    # реестр источника с sha256 каждого композита
    with open(RAW / "registry.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["id", "title", "url", "license", "accessed", "sha256",
                    "notes"])
        for y in YEARS:
            w.writerow([f"worldpop_viirs_fvf_{y}",
                        f"WorldPop VIIRS fvf (EOG average_masked VNL) BLR {y}",
                        WP_URL.format(year=y),
                        "CC BY 4.0 (WorldPop) / EOG VNL",
                        "2026-07-12", checksums[y],
                        "подлинный годовой композит EOG average_masked, "
                        "100 м, обрезан по Беларуси; в репозиторий не "
                        "вендорится (~30 МБ)"])
        w.writerow(["zonal_light", "Зональная светимость 119 зон x 9 лет "
                    "(итог extract)", "data/raw/nightlights/zonal_light.csv",
                    "CC BY 4.0 (проект)", "2026-07-12",
                    hashlib.sha256((RAW / "zonal_light.csv").read_bytes())
                    .hexdigest(),
                    f"порог > {DIM_THRESHOLD} нВт/см²/ср; растеризация "
                    "adm2+Минск(adm1)"])

    nat = {y: sum(r["radiance"] for r in rows if r["year"] == y)
           for y in YEARS}
    print(f"OK: zonal_light.csv ({n} зон x {len(YEARS)} лет)")
    print("  нац. сумма (М):",
          " ".join(f"{nat[y] / 1e6:.1f}" for y in YEARS))


if __name__ == "__main__":
    main()
