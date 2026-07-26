"""INF-15, шаг 1а: докачка тайлов GHS-POP R2023A (1 км, Молльвейде).

Источник: JRC GHSL GHS-POP R2023A, 1000 м, ESRI:54009, эпохи 1975-2020
(шаг 5 лет). Беларусь покрывают те же 4 тайла глобальной решётки JRC, что
и GHS-BUILT-S у INF-12 (тайловая сетка едина для всех продуктов и
разрешений GHSL): R3_C20, R3_C21, R4_C20, R4_C21.

Глобальные тайлы (~4.5-4.8 МБ каждый, ~190 МБ всего) в репозиторий НЕ
вендорятся - кэшируются в общей директории data/raw/ghsl/tiles/ (уже в
.gitignore, используется и INF-12). Вендорится только реестр с
URL+sha256+лицензией (data/raw/grid/registry_ghsl_pop.csv) и, отдельным
шагом (etl/grid_extract.py), вырезка по Беларуси.

Запуск (сеть; идемпотентно - готовые файлы не перекачиваются):
  python -m etl.grid_fetch
"""
from __future__ import annotations

import csv
import hashlib
import urllib.request
from pathlib import Path

from .common import ROOT

TILES = ROOT / "data" / "raw" / "ghsl" / "tiles"
REG_DIR = ROOT / "data" / "raw" / "grid"

EPOCHS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020]
TILE_IDS = ["R3_C20", "R3_C21", "R4_C20", "R4_C21"]
BASE_URL = ("https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/"
            "GHS_POP_GLOBE_R2023A/GHS_POP_E{epoch}_GLOBE_R2023A_54009_1000/"
            "V1-0/tiles/{name}.zip")

LICENSE = ("CC BY 4.0 (Joint Research Centre, European Commission; "
           "Schiavina, Freire, MacManus 2023, GHS-POP R2023A)")
ACCESSED = "2026-07-26"


def tile_name(epoch: int, tile: str) -> str:
    return f"GHS_POP_E{epoch}_GLOBE_R2023A_54009_1000_V1_0_{tile}"


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
            if out.exists() and out.stat().st_size > 0:
                continue
            url = BASE_URL.format(epoch=epoch, name=name)
            print("fetch", name)
            tmp = out.with_suffix(".part")
            urllib.request.urlretrieve(url, tmp)
            tmp.rename(out)


def write_registry() -> Path:
    REG_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for epoch in EPOCHS:
        for tile in TILE_IDS:
            name = tile_name(epoch, tile)
            z = TILES / f"{name}.zip"
            rows.append({
                "id": f"ghspop_{epoch}_{tile.lower()}",
                "title": f"GHS-POP R2023A эпоха {epoch}, тайл {tile} "
                         "(1000 м, Молльвейде)",
                "url": BASE_URL.format(epoch=epoch, name=name),
                "license": LICENSE,
                "accessed": ACCESSED,
                "sha256": sha256(z) if z.exists() else "",
                "size_bytes": z.stat().st_size if z.exists() else "",
                "vendored": "no",
                "notes": "глобальный тайл; клип Беларуси -> "
                         f"data/raw/grid/rasters/pop_{epoch}.tif",
            })
    reg = REG_DIR / "registry_ghsl_pop.csv"
    with reg.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"registry: {len(rows)} тайлов -> {reg}")
    return reg


def main() -> None:
    fetch_missing()
    write_registry()


if __name__ == "__main__":
    main()
