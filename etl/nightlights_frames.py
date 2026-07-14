"""INF-08 v2, шаг 5: предрендеренные PNG-кадры карты света (T-5).

Кадры для интерактива /research/nightlights и рилс-конвейера:
  наблюдения: y<год>.png, 1992-2011 из calDMSP (ресемпл на сетку VNL),
              2012-2024 из VNL;
  модель:     m<узел>_<сценарий>_<старт>.png, 2030-2075 x 3 x 2 -
              яркая компонента пикселей VNL-2024 масштабируется
              зональным фактором (pop_i(t)/pop_i(2024))^beta, пол
              (< floor_max нВт) неподвижен - как в зональной модели.

Требования ТЗ: единая проекция и рамка кадра на весь ряд (сетка вырезки
VNL-2024, EPSG:4326); палитра чёрный -> тёплый белый без «неоновых радуг»;
гамма под мобильные экраны; сеяный дизеринг против бандинга; вес
<= 150 КБ/кадр. Гарантия честности (T-13): в кадры будущего ВПЕЧАТАНЫ
штриховая рамка и бейдж «МОДЕЛЬ + сценарий» - маркер не удаляется
скриншотом.

Нормировка яркости фиксирована на весь ряд (сравнимость кадров):
  VNL/модель: v = log1p(rad)/log1p(VMAX), VMAX - параметр;
  DMSP: v = (DN/63)^DMSP_GAMMA (шкала DN сатурируется в центрах - сегмент
  честно помечен «ретро»).

Запуск (требует rasterio+numpy+Pillow):
  python -m etl.nightlights_frames -> web/public/data/nl_frames/*.png
"""
from __future__ import annotations

import json
import math

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from PIL import Image, ImageDraw, ImageFont

from .common import ROOT, OUT
from .nightlights_fetch import RASTERS
from .nightlights_zonal import zone_labels
from . import nightlights_model as M

FRAMES = OUT / "nl_frames"
SEED = 20260712          # сеяный дизеринг - байт-воспроизводимость
VMAX = 120.0             # нВт/см²/ср: фиксированный потолок нормировки VNL
DMSP_GAMMA = 0.95        # DN-шкала: сдержанный подъём (0,62 задирал
                         # блюминг DMSP - стык с VNL резал глаз)
VNL_GAMMA = 0.90         # лёгкая гамма-коррекция сегмента VNL
NOISE = 0.6              # амплитуда дизеринга, ур. 0-255 (только лит-пиксели)

# тёплая палитра: чёрный -> янтарь -> тёплый белый
_STOPS = [(0.00, (0, 0, 0)), (0.18, (26, 16, 4)), (0.42, (96, 60, 22)),
          (0.65, (190, 138, 68)), (0.85, (240, 205, 150)),
          (1.00, (255, 247, 228))]

SCN_RU = {"base": "базовый", "negative": "негативный",
          "optimistic": "оптимистичный"}
FONT_PATH = ROOT / "data" / "raw" / "nightlights" / "fonts" / \
    "DejaVuSans.ttf"


def lut() -> np.ndarray:
    t = np.linspace(0, 1, 256)
    out = np.zeros((256, 3), dtype="uint8")
    for c in range(3):
        xs = [s[0] for s in _STOPS]
        ys = [s[1][c] for s in _STOPS]
        out[:, c] = np.clip(np.interp(t, xs, ys), 0, 255).astype("uint8")
    return out


def _ref():
    return rasterio.open(RASTERS / "vnl_2024.tif")


def _norm_vnl(a: np.ndarray) -> np.ndarray:
    v = np.log1p(np.clip(a, 0, VMAX)) / math.log1p(VMAX)
    return np.clip(v, 0, 1) ** VNL_GAMMA


def _norm_dmsp(a: np.ndarray) -> np.ndarray:
    return np.clip(a / 63.0, 0, 1) ** DMSP_GAMMA


def _to_png(v: np.ndarray, path, rng, table, badge: str | None,
            noise: float = NOISE) -> None:
    """v в [0,1] -> палитровый PNG с сеяным дизерингом и бейджем.

    Шум - только на освещённых пикселях: чистый нулевой фон сохраняет
    длинные серии для deflate (иначе кадр не влезает в 150 КБ). Для
    DMSP noise=0: данные дискретны (DN 0-63), дизеринг бессмыслен и
    ломает 2x2-блоки nearest-ресемпла."""
    x = v * 255.0
    if noise > 0:
        lit = x > 0.5
        x = np.where(lit, x + rng.uniform(-noise, noise, v.shape), 0.0)
    idx = np.clip(np.round(x), 0, 255).astype("uint8")
    img = Image.fromarray(idx, mode="P")
    img.putpalette(table.flatten().tolist())
    if badge:
        # рисуем индексами палитры (без RGB-квантования): тёплый конец
        # LUT - янтарь/белый, начало - тёмные тона
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


def render_obs(table, rng) -> list[str]:
    names = []
    with _ref() as ref:
        ref_arr = np.zeros((ref.height, ref.width), dtype="float64")
        ref_transform, ref_crs = ref.transform, ref.crs
    for y in range(1992, 2025):
        if y <= 2011:
            # nearest: честные «пиксели эпохи» DMSP (и компактный PNG -
            # билинейная гладкость раздувала кадр за лимит 150 КБ)
            with rasterio.open(RASTERS / f"dmsp_{y}.tif") as s:
                src = s.read(1).astype("float64")
                dst = np.zeros_like(ref_arr)
                reproject(src, dst, src_transform=s.transform,
                          src_crs=s.crs, dst_transform=ref_transform,
                          dst_crs=ref_crs,
                          resampling=Resampling.nearest)
            v = _norm_dmsp(dst)
            noise = 0.0
        else:
            with rasterio.open(RASTERS / f"vnl_{y}.tif") as s:
                v = _norm_vnl(s.read(1).astype("float64"))
            noise = NOISE
        name = f"y{y}.png"
        _to_png(v, FRAMES / name, rng, table, None, noise=noise)
        names.append(name)
    return names


def render_model(table, rng) -> list[str]:
    assump = M.load_assumptions()
    fut = M.future_light(assump)
    floor_max = assump["model"]["floor_max_nw"]
    with _ref() as ref:
        labels, ids = zone_labels(ref)
        base = ref.read(1).astype("float64")
    zid_index = {z: i + 1 for i, z in enumerate(ids)}
    bright_mask = base >= floor_max
    names = []
    for j in M.JUMPOFFS:
        for s in M.SCENARIOS:
            factors = fut["factor"][j][s]
            for t in fut["nodes"]:
                f_arr = np.ones(len(ids) + 1, dtype="float64")
                for z, fz in factors.items():
                    f_arr[zid_index[z]] = fz[t]
                scaled = np.where(bright_mask, base * f_arr[labels], base)
                v = _norm_vnl(scaled)
                badge = f"МОДЕЛЬ · {SCN_RU[s]}"
                name = f"m{t}_{s}_{j}.png"
                _to_png(v, FRAMES / name, rng, table, badge)
                names.append(name)
        print(f"  модель {j}: ok")
    return names


def write_meta() -> None:
    """meta.json: геопривязка кадров для SVG-оверлея районов на фронте."""
    with _ref() as ref:
        b = ref.bounds
        meta = {"bounds": [b.left, b.bottom, b.right, b.top],
                "width": ref.width, "height": ref.height,
                "vmax": VMAX, "dmspGamma": DMSP_GAMMA, "seed": SEED}
    (FRAMES / "meta.json").write_text(json.dumps(meta))


def main() -> None:
    FRAMES.mkdir(parents=True, exist_ok=True)
    write_meta()
    table = lut()
    rng = np.random.default_rng(SEED)
    obs = render_obs(table, rng)
    print(f"OK: {len(obs)} кадров наблюдений")
    rng = np.random.default_rng(SEED + 1)
    mod = render_model(table, rng)
    print(f"OK: {len(mod)} кадров модели")
    sizes = [(FRAMES / n).stat().st_size for n in obs + mod]
    big = [n for n in obs + mod
           if (FRAMES / n).stat().st_size > 150 * 1024]
    print(f"  размер: медиана {sorted(sizes)[len(sizes) // 2] // 1024} КБ, "
          f"макс {max(sizes) // 1024} КБ; >150КБ: {big or 'нет'}")


if __name__ == "__main__":
    main()
