"""INF-08: демонстрационный слой будущего demographic_concentration.

НЕ научный прогноз радианса. Слой отвечает на перцептивную задачу
рилса и экспериментального режима сайта: сделать демографическую
концентрацию видимой. Научный слой (scientific_abs, etl/nightlights_
visual.py) остаётся без изменений и используется по умолчанию.

Отличия от научного слоя (ТЗ рилса v3, §11):
  - свет разделён на 4 класса (ядра / пригородные ореолы / малые
    поселения / дороги-инфраструктура) по порогам радианса шаблона
    2024 и близости к ядрам;
  - для каждого класса раздельно моделируются ИНТЕНСИВНОСТЬ
    I = I2024 * (P_t/P2024)^beta_c и ПЛОЩАДЬ следа
    A = A2024 * (P_t/P2024)^eta_c: доля самых тусклых пикселей класса
    в зоне гаснет полностью - периферия теряет площадь, а не только
    яркость;
  - промышленные точечные объекты (economic_infrastructure_residual:
    теплицы, БМЗ, промзоны - список в assumptions) отдельного прогноза
    не имеют -> not_modeled, остаются без изменений;
  - запрещена по-кадровая нормализация: единая шкала научного слоя.

Каждый кадр несёт впечатанную маркировку «УСИЛЕННАЯ ВИЗУАЛИЗАЦИЯ
ДЕМОГРАФИЧЕСКОЙ КОНЦЕНТРАЦИИ · не прогноз спутникового радианса»
плюс стандартный маркер МОДЕЛЬ.

Запуск (требует rasterio+numpy+Pillow; после etl.nightlights_visual):
  python -m etl.nightlights_demo
    -> web/public/data/nightlights/visual/demographic/*.png
    -> data/tmp/nl_fields/d<узел>_<сценарий>_<старт>.npy (кэш рилса)
    -> манифест дополняется секцией demoFrames
"""
from __future__ import annotations

import hashlib
import json
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .common import ROOT
from . import nightlights_model as M
from .nightlights_visual import NL, VISUAL, FIELDS, _norm, _ref, _to_png
from .nightlights_frames import lut, SEED, FONT_PATH, SCN_RU

DEMO = VISUAL / "demographic"


def _classes(base: np.ndarray, cfg: dict, transform) -> np.ndarray:
    """Карта классов: 0 фон, 1 core, 2 halo, 3 settlement, 4 infra,
    5 industrial not_modeled."""
    c = cfg["classes"]
    cls = np.zeros(base.shape, dtype="uint8")
    core = base >= c["core"]["minNw"]
    mid = (base >= c["halo"]["minNw"]) & (base < c["halo"]["maxNw"])
    infra = (base >= c["infra"]["minNw"]) & (base < c["infra"]["maxNw"])
    # дилатация ядра на nearCorePx (квадратное окно, детерминированно)
    r = int(c["halo"]["nearCorePx"])
    near = np.zeros_like(core)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            sh = np.roll(np.roll(core, dy, axis=0), dx, axis=1)
            near |= sh
    cls[infra] = 4
    cls[mid & ~near] = 3
    cls[mid & near] = 2
    cls[core] = 1
    # промышленные объекты - поверх всех классов
    h, w = base.shape
    lons = transform.c + transform.a * (np.arange(w) + 0.5)
    lats = transform.f + transform.e * (np.arange(h) + 0.5)
    lon_g, lat_g = np.meshgrid(lons, lats)
    for s in cfg["industrial_sites_not_modeled"]:
        kx = math.cos(math.radians(s["lat"])) * 111.32
        d2 = ((lon_g - s["lon"]) * kx) ** 2 \
            + ((lat_g - s["lat"]) * 111.32) ** 2
        cls[(d2 <= s["radius_km"] ** 2) & (base >= 1.0)] = 5
    return cls


def demo_field(base: np.ndarray, cls: np.ndarray, labels: np.ndarray,
               ids: list, factors: dict[str, float], cfg: dict,
               rng_seedless_index: np.ndarray) -> np.ndarray:
    """Поле демонстрационного слоя для одного узла/сценария/старта."""
    ckeys = {1: "core", 2: "halo", 3: "settlement", 4: "infra"}
    out = base.copy()
    zid_index = {z: i + 1 for i, z in enumerate(ids)}
    for z, f in factors.items():
        zmask = labels == zid_index[z]
        f = max(f, 1e-6)
        for ci, cname in ckeys.items():
            m = zmask & (cls == ci)
            if not m.any():
                continue
            beta = cfg["classes"][cname]["beta"]
            eta = cfg["classes"][cname]["eta"]
            out[m] = base[m] * (f ** beta)
            if eta > 0 and f < 1.0:
                keep = f ** eta
                vals = base[m]
                # детерминированный порог: гаснут самые тусклые
                thr = np.quantile(vals, 1.0 - keep) if keep < 1.0 else 0
                kill = m & (base <= thr)
                out[kill] = 0.0
    # industrial not_modeled: без изменений
    out[cls == 5] = base[cls == 5]
    return np.clip(out, 0, None)


def _bake_marking(img: Image.Image, scn_ru: str) -> Image.Image:
    """Впечатанная маркировка демонстрационного слоя (на каждом кадре)."""
    HATCH, TXT, BGD = 205, 235, 12
    d = ImageDraw.Draw(img)
    w, h = img.size
    step, m = 18, 3
    for x0 in range(0, w, step):
        d.line([(x0, m), (min(x0 + 9, w), m)], fill=HATCH, width=2)
        d.line([(x0, h - m), (min(x0 + 9, w), h - m)], fill=HATCH, width=2)
    for y0 in range(0, h, step):
        d.line([(m, y0), (m, min(y0 + 9, h))], fill=HATCH, width=2)
        d.line([(w - m, y0), (w - m, min(y0 + 9, h))], fill=HATCH, width=2)
    f1 = ImageFont.truetype(str(FONT_PATH), 40)
    f2 = ImageFont.truetype(str(FONT_PATH), 30)
    lines = ["УСИЛЕННАЯ ВИЗУАЛИЗАЦИЯ", "ДЕМОГРАФИЧЕСКОЙ КОНЦЕНТРАЦИИ",
             f"не прогноз спутникового радианса · МОДЕЛЬ · {scn_ru}"]
    widths = [d.textlength(lines[0], font=f1),
              d.textlength(lines[1], font=f1),
              d.textlength(lines[2], font=f2)]
    bw = max(widths) + 28
    d.rectangle([w - bw - 10, 8, w - 8, 8 + 40 * 2 + 34 + 26], fill=BGD)
    d.text((w - bw + 4, 14), lines[0], font=f1, fill=TXT)
    d.text((w - bw + 4, 56), lines[1], font=f1, fill=TXT)
    d.text((w - bw + 4, 100), lines[2], font=f2, fill=HATCH)
    return img


def main() -> None:
    DEMO.mkdir(parents=True, exist_ok=True)
    assump = M.load_assumptions()
    cfg = assump["model"]["demo_layer"]
    table = lut()
    from .nightlights_zonal import zone_labels
    with _ref() as ref:
        labels, ids = zone_labels(ref)
        base = ref.read(1).astype("float64")
        transform = ref.transform
    cls = _classes(base, cfg, transform)
    fut = M.future_pop(assump)
    data = json.loads((ROOT / "web/public/data/data.json").read_text())
    terr = data["territories"]
    base_year = assump["model"]["base_year"]
    p0 = {z: M._pop(terr, z, base_year) for z in
          [q for q in terr if q.startswith("r-")] + ["BY-HM"]}
    nodes = assump["model"]["nodes"]
    rng = np.random.default_rng(SEED + 7)
    entries = []
    for jmp in M.JUMPOFFS:
        ratio0 = M._jumpoff_ratio0(terr)
        for scn in M.SCENARIOS:
            for t in nodes:
                factors = {}
                for z, series in fut[jmp][scn].items():
                    denom = p0[z] * (ratio0[z] if jmp == "adjusted"
                                     else 1.0)
                    factors[z] = series[t] / denom
                f = demo_field(base, cls, labels, ids, factors, cfg, None)
                np.save(FIELDS / f"d{t}_{scn}_{jmp}.npy",
                        f.astype("float32"))
                v = _norm(f)
                p = DEMO / f"{t}_{scn}_{jmp}.png"
                _to_png(v, p, rng, table, None)
                with Image.open(p) as im:
                    im = im.convert("P")
                    im.putpalette(table.flatten().tolist())
                    im = _bake_marking(im, SCN_RU[scn])
                    im.save(p, optimize=True)
                entries.append({
                    "year": t, "scenario": scn, "jumpoff": jmp,
                    "asset": f"/data/nightlights/visual/demographic/{t}_{scn}_{jmp}.png",
                    "sourceType": "demographic_concentration_demo",
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
        print(f"  demo {jmp}: ok")

    manifest_p = NL / "nightlights_manifest.json"
    man = json.loads(manifest_p.read_text())
    man["demoLayer"] = {
        "note": cfg["comment"],
        "marking": cfg["marking_ru"],
        "classes": cfg["classes"],
        "industrialSitesNotModeled": cfg["industrial_sites_not_modeled"],
        "frames": entries}
    manifest_p.write_text(json.dumps(man, ensure_ascii=False, indent=1))
    sizes = sorted((DEMO / e["asset"].rsplit("/", 1)[-1]).stat().st_size
                   for e in entries)
    print(f"OK: {len(entries)} demo-кадров, медиана "
          f"{sizes[len(sizes) // 2] // 1024} КБ, макс {sizes[-1] // 1024} КБ")


if __name__ == "__main__":
    main()
