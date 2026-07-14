"""INF-08 v2, шаг 1: загрузка глобальных растров NTL и вырезка Беларуси.

Источники (оба открытые, анонимная загрузка):

1. Li et al., «Harmonization of DMSP and VIIRS nighttime light data from
   1992-2024 at the global scale» (Figshare, doi:10.6084/m9.figshare.
   9828827.v10, CC BY 4.0): калиброванный DMSP-OLS stable lights
   1992-2013 (интеркалибровка спутников F10-F18 выполнена авторами,
   шкала DN 0-63, ~1 км) и simVIIRS 2014-2024 (VIIRS, сконвертированный
   в DMSP-подобную шкалу; используется ТОЛЬКО для спайка-сравнения
   схем гармонизации, вырезки не вендорятся).

2. EOG VIIRS VNL v2.1 annual (average), зеркало OpenGeoHub/Zenodo
   record 17294744 (CC BY 4.0): подлинные годовые композиты EOG,
   ресемплированные на 500 м EPSG:4326, 2012-2024. Сам EOG
   (eogdata.mines.edu) с 2021 г. закрыт OpenID-логином - зеркало
   выбрано ради анонимной воспроизводимости; для 2015-2023 ряд
   кросс-валидируется зональной суммой против WorldPop fvf
   (data/raw/nightlights/zonal_light.csv, источник v1).

Глобальные растры (~2 ГБ) в репозиторий НЕ вендорятся - кэшируются в
NL_SRC; вендорятся вырезки по Беларуси (data/raw/nightlights/rasters/):
пиксели вне страны обнулены (маска adm1 union, all_touched - пиксель
на границе сохраняется), сетка и значения источника не меняются
(DMSP - uint8 DN; VNL - float32 нВт/см²/ср, округление до 0,1).
registry.csv фиксирует URL, дату обращения, лицензию и sha256 и
глобального файла, и вырезки.

Запуск (требует rasterio+numpy; однократно):
  NL_SRC=<кэш глобальных растров> python -m etl.nightlights_fetch
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import ssl
import urllib.request
from datetime import date
from pathlib import Path

try:                       # системный питон macOS без корневых сертификатов
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:        # pragma: no cover
    _SSL_CTX = ssl.create_default_context()

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.windows import from_bounds

from .common import ROOT, OUT

RAW = ROOT / "data" / "raw" / "nightlights"
RASTERS = RAW / "rasters"

# рамка вырезки: bbox adm1 (23.180-32.767, 51.276-56.185) + запас
BBOX = (23.10, 51.20, 32.85, 56.25)   # W, S, E, N

DMSP_YEARS = list(range(1992, 2014))      # calDMSP
SIM_YEARS = list(range(2013, 2025))       # simVIIRS (2013 - бонус-файл)
VNL_YEARS = list(range(2012, 2025))       # VNL v2.1 (зеркало)

FIGSHARE_API = "https://api.figshare.com/v2/articles/9828827"
FIGSHARE_LICENSE = "CC BY 4.0 (Li et al., figshare 9828827 v10)"
ZENODO_URL = ("https://zenodo.org/api/records/17294744/files/"
              "nightlights.average_viirs.v21_m_500m_s_{y}0101_{y}1231_go_"
              "epsg4326_v20250904.tif/content")
ZENODO_KEY = ("nightlights.average_viirs.v21_m_500m_s_{y}0101_{y}1231_go_"
              "epsg4326_v20250904.tif")
ZENODO_LICENSE = "CC BY 4.0 (OpenGeoHub, Zenodo 17294744; данные EOG VNL)"


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    print(f"  качаю {dest.name}")
    tmp = dest.with_suffix(".part")
    req = urllib.request.Request(url, headers={"User-Agent": "by-maps-etl"})
    with urllib.request.urlopen(req, timeout=600, context=_SSL_CTX) as r, \
            open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.rename(dest)


def _country_geom() -> list:
    g1 = json.loads((OUT / "geo" / "adm1.geojson").read_text())
    return [f["geometry"] for f in g1["features"]]


def _deflare_sites() -> list[dict]:
    for p in [ROOT / "params" / "assumptions.json",
              ROOT / "artifacts" / "nightlights" / "params"
              / "assumptions.json"]:
        if p.exists():
            return json.loads(p.read_text())["deflare"]["sites"]
    raise SystemExit("нет params/assumptions.json (deflare)")


def _deflare(a: np.ndarray, tr) -> np.ndarray:
    """Обнуление дисков вокруг факелов НПЗ (см. assumptions: deflare).

    Зеркальный продукт VNL average не фильтрует газовые факелы (в
    отличие от fvf v1); факелы - не электрический свет. Маска едина
    для обоих сегментов ряда."""
    h, w = a.shape
    lons = tr.c + tr.a * (np.arange(w) + 0.5)
    lats = tr.f + tr.e * (np.arange(h) + 0.5)
    lon_g, lat_g = np.meshgrid(lons, lats)
    for s in _deflare_sites():
        kx = math.cos(math.radians(s["lat"])) * 111.32
        d2 = ((lon_g - s["lon"]) * kx) ** 2 \
            + ((lat_g - s["lat"]) * 111.32) ** 2
        a = np.where(d2 <= s["radius_km"] ** 2, 0.0, a)
    return a


def _clip(src_path: Path, dst_path: Path, geoms: list,
          dtype: str, round_dec: int | None,
          value_scale: float = 1.0) -> dict:
    """Вырезка bbox + маска страны; возвращает свойства для реестра.

    value_scale - явный множитель значений источника: зеркало Zenodo
    хранит радианс x10 («0-200 -> 0-2000», см. описание записи), GDAL
    SCALE-тег при этом равен 1.0 - полагаться на s.scales нельзя,
    множитель задаётся вызывающим кодом (ловушка v1: SCALE 1.0/10.0).
    """
    with rasterio.open(src_path) as s:
        win = from_bounds(*BBOX, transform=s.transform)
        win = win.round_offsets(op="floor").round_lengths(op="ceil")
        a = s.read(1, window=win).astype("float64")
        tr = s.window_transform(win)
        if s.nodata is not None:
            a = np.where(a == s.nodata, 0.0, a)
        gdal_scale = s.scales[0] if s.scales and s.scales[0] else 1.0
        a *= gdal_scale * value_scale
    mask = rasterize(((g, 1) for g in geoms), out_shape=a.shape,
                     transform=tr, fill=0, dtype="uint8", all_touched=True)
    a = np.where(mask == 1, a, 0.0)
    a = _deflare(a, tr)
    a = np.clip(a, 0.0, None)
    if round_dec is not None:
        a = np.round(a, round_dec)
    prof = {"driver": "GTiff", "height": a.shape[0], "width": a.shape[1],
            "count": 1, "dtype": dtype, "crs": "EPSG:4326", "transform": tr,
            "compress": "lzw", "predictor": 2, "nodata": 0}
    with rasterio.open(dst_path, "w", **prof) as d:
        d.write(a.astype(dtype), 1)
    return {"px": f"{a.shape[1]}x{a.shape[0]}",
            "max": float(a.max()), "sum": float(a.sum())}


def main() -> None:
    src = Path(os.environ.get("NL_SRC", ROOT / "data" / "tmp" / "nl_src"))
    (src / "dmsp").mkdir(parents=True, exist_ok=True)
    (src / "viirs").mkdir(parents=True, exist_ok=True)
    RASTERS.mkdir(parents=True, exist_ok=True)
    geoms = _country_geom()
    today = date.today().isoformat()

    with urllib.request.urlopen(
            urllib.request.Request(FIGSHARE_API,
                                   headers={"User-Agent": "by-maps-etl"}),
            timeout=120, context=_SSL_CTX) as r:
        fig = {f["name"]: f for f in json.load(r)["files"]}

    reg_rows = []

    def reg(rid, title, url, lic, sha, notes):
        reg_rows.append([rid, title, url, lic, today, sha, notes])

    # --- DMSP calDMSP 1992-2013: вырезки вендорятся ---
    for y in DMSP_YEARS:
        name = f"Harmonized_DN_NTL_{y}_calDMSP.tif"
        g = src / "dmsp" / name
        _download(fig[name]["download_url"], g)
        dst = RASTERS / f"dmsp_{y}.tif"
        info = _clip(g, dst, geoms, "uint8", None)
        reg(f"li_caldmsp_{y}", f"Li et al. calDMSP {y} (глобальный)",
            fig[name]["download_url"], FIGSHARE_LICENSE, _sha256(g),
            "DMSP-OLS stable lights, интеркалиброван, DN 0-63, ~1 км; "
            "глобальный файл не вендорится")
        reg(f"clip_dmsp_{y}", f"Вырезка Беларуси calDMSP {y}",
            f"data/raw/nightlights/rasters/dmsp_{y}.tif",
            "CC BY 4.0", _sha256(dst),
            f"{info['px']}, маска adm1 all_touched, вне страны 0; "
            f"max DN {info['max']:.0f}")

    # --- VNL v2.1 2012-2024: вырезки вендорятся ---
    for y in VNL_YEARS:
        g = src / "viirs" / ZENODO_KEY.format(y=y)
        _download(ZENODO_URL.format(y=y), g)
        dst = RASTERS / f"vnl_{y}.tif"
        info = _clip(g, dst, geoms, "float32", 1, value_scale=0.1)
        reg(f"vnl_avg_{y}", f"EOG VNL v2.1 average {y} (зеркало, глобальный)",
            ZENODO_URL.format(y=y), ZENODO_LICENSE, _sha256(g),
            "подлинный годовой композит EOG, 500 м EPSG:4326, значения "
            "радианс x10 (int16); глобальный файл не вендорится")
        reg(f"clip_vnl_{y}", f"Вырезка Беларуси VNL {y}",
            f"data/raw/nightlights/rasters/vnl_{y}.tif",
            "CC BY 4.0", _sha256(dst),
            f"{info['px']}, нВт/см²/ср (значения зеркала x0,1) окр. 0,1, "
            f"маска adm1 all_touched; max {info['max']:.1f}")

    # --- simVIIRS 2013-2024: только для спайка, вырезки НЕ вендорятся ---
    for y in SIM_YEARS:
        name = (f"DN_NTL_{y}_simVIIRS.tif" if y == 2013
                else f"Harmonized_DN_NTL_{y}_simVIIRS.tif")
        g = src / "dmsp" / name
        _download(fig[name]["download_url"], g)
        reg(f"li_simviirs_{y}", f"Li et al. simVIIRS {y} (глобальный)",
            fig[name]["download_url"], FIGSHARE_LICENSE, _sha256(g),
            "VIIRS в DMSP-подобной шкале DN; только спайк-сравнение "
            "гармонизации, вырезка не вендорится")

    # v1-источник (WorldPop fvf) остаётся в реестре - кросс-валидация
    reg("worldpop_fvf_2015_2023",
        "WorldPop VIIRS fvf BLR 2015-2023 (источник v1)",
        "https://data.worldpop.org/GIS/Covariates/Global_2015_2030/BLR/"
        "VIIRS/v1/fvf/", "CC BY 4.0 (WorldPop) / EOG VNL",
        "см. zonal_light.csv",
        "зональные суммы v1 - независимая кросс-проверка ряда VNL")

    with open(RAW / "registry_v2.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["id", "title", "url", "license", "accessed", "sha256",
                    "notes"])
        w.writerows(reg_rows)
    print(f"OK: {len(reg_rows)} записей реестра, вырезки в {RASTERS}")


if __name__ == "__main__":
    main()
