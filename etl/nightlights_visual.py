"""INF-08 v3: единый визуальный ряд карты света (T-V3, «финальная переработка»).

АНАЛИТИЧЕСКИЙ слой (nightlights_v2.json, гармонизированные зональные
ряды) остаётся единственным источником чисел, рейтингов и событий.
Этот модуль строит ВИЗУАЛЬНЫЙ слой - кадры карты - и его манифест:

  1992-2011  реконструкция VIIRS-like: пиксельное отображение
             DN -> радианс-эквивалент по «мосту» (exp(a_bar + b*ln DN),
             коэффициенты гармонизации из зональных данных), коррекция
             F18-эры и межспутниковая стабилизация median-3 (обе -
             документированная часть определения реконструкции),
             билинейный ресемпл на сетку VNL (VIIRS-подобная гладкость).
             НЕ выдаётся за наблюдение и НЕ используется для точных
             локальных числовых выводов.
  2012-2024  реальные наблюдения VIIRS (EOG VNL v2.1, вырезки).
  2030-2075  модельная визуализация: яркая компонента пикселей 2024
             масштабируется зональными факторами прогноза (маркер
             «МОДЕЛЬ» впечатан - T-13).

Единый стандарт кадра: сетка вырезки VNL-2024 (EPSG:4326), одна маска
страны, один принцип nodata (вне страны = 0 = прозрачный чёрный), одна
палитра, фиксированные VMAX и гамма на ВЕСЬ ряд - никакой по-годовой
автонормализации. Радианс-эквивалентные поля кэшируются в float16
(.npz) для расчёта delta-слоёв тем же кодом.

Запуск (требует rasterio+numpy+Pillow):
  python -m etl.nightlights_visual
    -> web/public/data/nightlights/visual/{reconstructed,observed,modeled}/
    -> web/public/data/nightlights/nightlights_manifest.json
    -> data/tmp/nl_fields/*.npy (кэш полей для delta-шага)
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from PIL import Image, ImageDraw, ImageFont

from .common import ROOT, OUT
from .nightlights_fetch import RASTERS
from . import nightlights_harmonize as H
from . import nightlights_model as M
from .nightlights_frames import lut, VMAX, VNL_GAMMA, SEED, NOISE, \
    FONT_PATH, SCN_RU

NL = OUT / "nightlights"
VISUAL = NL / "visual"
FIELDS = ROOT / "data" / "tmp" / "nl_fields"

RECON_YEARS = list(range(1992, 2012))
OBS_YEARS = list(range(2012, 2025))

SEG_DIR = {"reconstructed_viirs_like": "reconstructed",
           "observed_viirs": "observed",
           "modeled_forecast": "modeled"}


def _norm(a: np.ndarray) -> np.ndarray:
    """Единая нормировка отображения для ВСЕГО ряда (радианс -> [0,1])."""
    v = np.log1p(np.clip(a, 0, VMAX)) / math.log1p(VMAX)
    return np.clip(v, 0, 1) ** VNL_GAMMA


def _ref():
    return rasterio.open(RASTERS / "vnl_2024.tif")


def recon_params() -> dict:
    """Параметры реконструкции: гармонизированный зональный ряд
    (аналитический слой) + стабилизация median-3 нац. уровня."""
    h = H.harmonized()
    zs = sorted(h["series"])
    flux = {y: {z: h["series"][z][y] for z in zs} for y in RECON_YEARS}
    flux[2012] = {z: h["series"][z][2012] for z in zs}
    nat = {y: sum(flux[y].values()) for y in RECON_YEARS}
    stab = {}
    for y in RECON_YEARS:
        w = [nat.get(q) for q in (y - 1, y, y + 1) if q in nat]
        stab[y] = statistics.median(w) / nat[y]
    return {"flux": flux, "stab": stab,
            "f18": h["f18"], "bridge_b": h["bridge"]["b"],
            "a_bar": h["bridge"]["a_bar"]}


def recon_field(year: int, prm: dict, labels: np.ndarray, ids: list,
                template: np.ndarray) -> np.ndarray:
    """Реконструкция VIIRS-like: шаблон VNL-2012 x зональные факторы.

    Пространственная структура - первый реальный кадр VIIRS (2012);
    временная динамика - гармонизированный АНАЛИТИЧЕСКИЙ зональный ряд
    (DMSP -> мост, f18) x стабилизация median-3: пиксели зоны
    масштабируются отношением flux_year(зона)/flux_2012(зона). Зеркало
    модельного слоя (там - шаблон 2024 x факторы прогноза).
    Ограничение (в манифесте и методблоке): внутрирайонная структура
    зафиксирована на 2012 год - объекты, исчезнувшие или появившиеся
    внутри района до 2012-го, реконструкцией не отображаются; точные
    локальные выводы - только из аналитического слоя."""
    n = len(ids)
    factor = np.ones(n + 1)
    tot_y, tot_12 = 0.0, 0.0
    for i, z in enumerate(ids):
        f12 = prm["flux"][2012].get(z, 0.0)
        fy = prm["flux"][year].get(z, 0.0) * prm["stab"][year]
        factor[i + 1] = fy / f12 if f12 > 0 else 0.0
        tot_y += fy
        tot_12 += f12
    factor[0] = tot_y / tot_12 if tot_12 > 0 else 0.0   # приграничные px
    return template * factor[labels]


def obs_field(year: int) -> np.ndarray:
    with rasterio.open(RASTERS / f"vnl_{year}.tif") as s:
        return s.read(1).astype("float64")


class ModelFields:
    def __init__(self, assump):
        from .nightlights_zonal import zone_labels
        with _ref() as ref:
            self.labels, self.ids = zone_labels(ref)
            self.base = ref.read(1).astype("float64")
        self.zid = {z: i + 1 for i, z in enumerate(self.ids)}
        self.bright = self.base >= assump["model"]["floor_max_nw"]
        self.fut = M.future_light(assump)

    def field(self, node: int, scn: str, jmp: str) -> np.ndarray:
        f_arr = np.ones(len(self.ids) + 1)
        for z, fz in self.fut["factor"][jmp][scn].items():
            f_arr[self.zid[z]] = fz[node]
        return np.where(self.bright, self.base * f_arr[self.labels],
                        self.base)


def _to_png(v: np.ndarray, path, rng, table, badge: str | None,
            noise: float = NOISE) -> None:
    """Кадр [0,1] -> палитровый PNG (шум только на лит-пикселях)."""
    x = v * 255.0
    if noise > 0:
        lit = x > 0.5
        x = np.where(lit, x + rng.uniform(-noise, noise, v.shape), 0.0)
    idx = np.clip(np.round(x), 0, 255).astype("uint8")
    img = Image.fromarray(idx, mode="P")
    img.putpalette(table.flatten().tolist())
    if badge:
        HATCH, TXT, BGD = 205, 235, 12
        d = ImageDraw.Draw(img)
        w, h = img.size
        step, m = 18, 3
        for x0 in range(0, w, step):
            d.line([(x0, m), (min(x0 + 9, w), m)], fill=HATCH, width=2)
            d.line([(x0, h - m), (min(x0 + 9, w), h - m)], fill=HATCH,
                   width=2)
        for y0 in range(0, h, step):
            d.line([(m, y0), (m, min(y0 + 9, h))], fill=HATCH, width=2)
            d.line([(w - m, y0), (w - m, min(y0 + 9, h))], fill=HATCH,
                   width=2)
        font = ImageFont.truetype(str(FONT_PATH), 42)
        pad = 14
        tb = d.textbbox((0, 0), badge, font=font)
        bw, bh = tb[2] - tb[0], tb[3] - tb[1]
        d.rectangle([w - bw - pad * 3, m + 8, w - m - 6,
                     m + 8 + bh + pad * 2], fill=BGD)
        d.text((w - bw - pad * 2, m + 8 + pad - tb[1]), badge,
               font=font, fill=TXT)
    img.save(path, optimize=True)


def _sha(p) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    for d in ["reconstructed", "observed", "modeled"]:
        (VISUAL / d).mkdir(parents=True, exist_ok=True)
    FIELDS.mkdir(parents=True, exist_ok=True)
    table = lut()
    assump = M.load_assumptions()
    prm = recon_params()
    with _ref() as ref:
        shape = (ref.height, ref.width)
        transform, crs = ref.transform, ref.crs
        b = ref.bounds
        bounds = [b.left, b.bottom, b.right, b.top]

    frames = []

    def save_field(field: np.ndarray, key: str) -> None:
        np.save(FIELDS / f"{key}.npy", field.astype("float32"))

    from .nightlights_zonal import zone_labels
    with _ref() as ref:
        labels, ids = zone_labels(ref)
    template = obs_field(2012)

    rng = np.random.default_rng(SEED)
    for y in RECON_YEARS:
        f = recon_field(y, prm, labels, ids, template)
        save_field(f, f"y{y}")
        p = VISUAL / "reconstructed" / f"{y}.png"
        # реконструкция квантуется до 128 уровней: исходник ~1 км,
        # 256 уровней не несут информации, а PNG худеет вдвое
        v = np.round(_norm(f) * 127.5) / 127.5
        _to_png(v, p, rng, table, None, noise=0.0)
        frames.append({
            "year": y, "asset": f"/data/nightlights/visual/reconstructed/{y}.png",
            "sourceType": "reconstructed_viirs_like",
            "analyticalSource": "harmonized_dmsp",
            "comparableToPrevious": y > RECON_YEARS[0],
            "qualityFlags": ["reconstruction"]
            + (["f18_era_corrected"] if y in H.F18_YEARS else []),
            "referenceYear": y - 1 if y > RECON_YEARS[0] else None,
            "sha256": _sha(p)})
        print(f"  recon {y}: ok")

    for y in OBS_YEARS:
        f = obs_field(y)
        save_field(f, f"y{y}")
        p = VISUAL / "observed" / f"{y}.png"
        _to_png(_norm(f), p, rng, table, None)
        flags = []
        if y == 2012:
            flags.append("first_viirs_year_partial")
        if y == 2021:
            flags.append("vnl_processing_step")
        frames.append({
            "year": y, "asset": f"/data/nightlights/visual/observed/{y}.png",
            "sourceType": "observed_viirs",
            "analyticalSource": "vnl_v21",
            "comparableToPrevious": y > 2012,   # 2011->2012 = смена источника
            "qualityFlags": flags,
            "referenceYear": y - 1 if y > 2012 else None,
            "sha256": _sha(p)})
        print(f"  obs {y}: ok")

    mf = ModelFields(assump)
    nodes = assump["model"]["nodes"]
    for jmp in M.JUMPOFFS:
        for scn in M.SCENARIOS:
            for i, t in enumerate(nodes):
                f = mf.field(t, scn, jmp)
                save_field(f, f"m{t}_{scn}_{jmp}")
                p = VISUAL / "modeled" / f"{t}_{scn}_{jmp}.png"
                _to_png(_norm(f), p, rng, table,
                        f"МОДЕЛЬ · {SCN_RU[scn]}")
                frames.append({
                    "year": t, "scenario": scn, "jumpoff": jmp,
                    "asset": f"/data/nightlights/visual/modeled/{t}_{scn}_{jmp}.png",
                    "sourceType": "modeled_forecast",
                    "analyticalSource": "light_model_v2",
                    "comparableToPrevious": i > 0,
                    "qualityFlags": ["model"],
                    "referenceYear": nodes[i - 1] if i > 0 else 2024,
                    "sha256": _sha(p)})
        print(f"  model {jmp}: ok")

    manifest = {
        "version": "3.0.0",
        "note": ("Визуальный слой карты света. Числа, рейтинги и события "
                 "берутся ТОЛЬКО из аналитического слоя "
                 "(nightlights_v2.json); реконструкция 1992-2011 - "
                 "визуальное представление, не наблюдение."),
        "grid": {"width": shape[1], "height": shape[0],
                 "bounds": bounds, "crs": "EPSG:4326",
                 "resolutionDeg": abs(transform.a),
                 "mask": "adm1 union, all_touched; вне страны = 0",
                 "nodata": "0 -> чёрный/прозрачный"},
        "render": {"vmax_nw": VMAX, "gamma": VNL_GAMMA,
                   "normalization": "log1p(rad)/log1p(VMAX), единая на весь ряд, без по-годовой нормализации",
                   "palette": "чёрный -> янтарь -> тёплый белый (256 ступеней)",
                   "ditherSeed": SEED},
        "reconstruction": {
            "method": ("шаблонная: пространственная структура = первый "
                       "реальный кадр VIIRS (VNL-2012); временная "
                       "динамика = гармонизированный аналитический "
                       "зональный ряд (DMSP -> мост b, a_bar; f18) x "
                       "стабилизация median-3; пиксели зоны умножаются "
                       "на flux_year(зона)/flux_2012(зона) - зеркало "
                       "модельного слоя (шаблон 2024 x факторы прогноза)"),
            "template": "observed_viirs 2012",
            "a_bar": round(prm["a_bar"], 4),
            "b": round(prm["bridge_b"], 4),
            "f18": round(prm["f18"], 4),
            "stab": {str(y): round(s, 4) for y, s in prm["stab"].items()},
            "caveat": ("реконструкция - для визуальной цельности ряда; "
                       "внутрирайонная структура зафиксирована на 2012 "
                       "год (исчезнувшие/появившиеся до 2012-го объекты "
                       "не отображаются); точные локальные выводы - "
                       "только из аналитического слоя")},
        "sources": [
            {"id": "harmonized_dmsp",
             "title": "Li et al., Harmonization of DMSP and VIIRS NTL "
                      "1992-2024 (calDMSP), вырезки по Беларуси",
             "url": "https://doi.org/10.6084/m9.figshare.9828827",
             "version": "v10", "license": "CC BY 4.0",
             "accessed": "2026-07-14", "resolution": "~1 км (30\"), DN 0-63",
             "files": "data/raw/nightlights/rasters/dmsp_*.tif",
             "checksums": "data/raw/nightlights/registry_v2.csv"},
            {"id": "vnl_v21",
             "title": "EOG VIIRS VNL v2.1 annual average (зеркало "
                      "OpenGeoHub/Zenodo 17294744), вырезки по Беларуси",
             "url": "https://zenodo.org/records/17294744",
             "version": "v2.1 (v20250904)", "license": "CC BY 4.0",
             "accessed": "2026-07-14",
             "resolution": "500 м, нВт/см²/ср (значения зеркала x0,1)",
             "files": "data/raw/nightlights/rasters/vnl_*.tif",
             "checksums": "data/raw/nightlights/registry_v2.csv"},
            {"id": "light_model_v2",
             "title": "Модель светимости 2030-2075 (bright*(pop-ratio)^beta"
                      " + floor; прогноз v2026.4)",
             "url": "/artifacts/by-maps-nightlights-v2.0.0.zip",
             "version": "2.0.0", "license": "CC BY 4.0",
             "accessed": "2026-07-14",
             "resolution": "500 м (поле пикселей VNL-2024)",
             "files": "params/assumptions.json",
             "checksums": "web/public/artifacts/checksums.txt"}],
        "sourceTypeLabels": {
            "reconstructed_viirs_like": {
                "ru": "реконструкция VIIRS-like", "be": "рэканструкцыя VIIRS-like"},
            "observed_viirs": {
                "ru": "спутниковые наблюдения VIIRS", "be": "спадарожнікавыя назіранні VIIRS"},
            "modeled_forecast": {
                "ru": "модельный прогноз", "be": "мадэльны прагноз"}},
        "frames": frames,
    }
    NL.mkdir(parents=True, exist_ok=True)
    (NL / "nightlights_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1))
    sizes = [(VISUAL / SEG_DIR[f["sourceType"]] /
              f["asset"].rsplit("/", 1)[-1]).stat().st_size
             for f in frames]
    print(f"OK: {len(frames)} кадров, медиана "
          f"{sorted(sizes)[len(sizes) // 2] // 1024} КБ, "
          f"макс {max(sizes) // 1024} КБ; манифест записан")


if __name__ == "__main__":
    main()
