"""INF-15, шаг 4: кадры карты (webp) + перекрёстная проверка с огнями (G-3).

Паттерны - etl/nightlights_frames.py (лог-нормировка, сеяный дизеринг,
честный бейдж «МОДЕЛЬ» на прогнозных кадрах, единая геопривязка на весь
ряд). Отличия: (1) выходной формат webp (бюджет строже - 220 КБ/кадр);
(2) секвенциальная холодная палитра (не янтарь nightlights - чтобы кадры
двух исследований не путались на скриншотах); (3) прогнозные растры не
персистятся на диск - считаются на лету через etl.grid_project и сразу
рендерятся, чтобы не раздувать репозиторий.

G-3 (раздел 7 ТЗ): знак изменения численности по клеткам (2012->2020,
интерполяция к 2012 из наблюдаемых узлов 2010/2015) против знака изменения
светимости (web/public/data/nightlights_v2.json, сегмent VNL, без смешения
с DMSP) - требование >=70% согласия районов. Дополнительно (условие
ревью D-005, третий проверяющий): разбивка согласия отдельно по группе
«районы-хозяева городов» (систематически переоценены сырым GHS-POP) и
остальным - тест на confound, специально запрошенный при ревью constrained
dasymetric калибровки.

Запуск (требует rasterio+numpy+scipy+Pillow):
  python -m etl.grid_frames
"""
from __future__ import annotations

import json
import math

import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFont

from .common import ROOT, OUT
from .grid import (EPOCHS, RASTERS_CONSTRAINED, RAW, zone_labels,
                    _adm_geoms_moll, interp_official, load_raion_series)
from .grid_project import (FORECAST_YEARS, SCENARIOS, VARIANTS, load_forecast,
                            load_observed_stack, fit_log_share_trend,
                            anchors_from_2020, suburb_periphery_adjustment,
                            project_epoch)

FRAMES = OUT / "grid_frames"
SEED = 42                 # пререгистрация §6 - единый seed проекта
VMAX = 5000.0              # чел/км²: фиксированный потолок лог-нормировки
GAMMA = 0.92
NOISE = 0.5
FRAME_KB_MAX = 220
TOTAL_MB_MAX = 12.0

# секвенциальная холодная палитра (не радуга, отличима от янтарной nightlights):
# тёмный индиго -> тёмная бирюза -> голубой -> почти белый
_STOPS = [(0.00, (8, 8, 24)), (0.20, (15, 35, 66)), (0.45, (20, 90, 110)),
          (0.68, (60, 165, 175)), (0.86, (170, 225, 220)),
          (1.00, (250, 253, 250))]

SCN_RU = {"base": "базовый", "negative": "негативный", "optimistic": "оптимистичный"}
VARIANT_RU = {"A": "инерция", "B": "пригороды/периферия"}
FONT_PATH = ROOT / "data" / "raw" / "nightlights" / "fonts" / "DejaVuSans.ttf"

# Классы плотности (WP-1/B-2, docs/notes/grid_ux_audit_2026-07-27.md):
# пороги 1 и 5 - замороженные пороги пререгистрации (docs/preregistration/
# grid-v0.1.md §6: primary=5, secondary=1); верхний класс "густо" - без
# отдельного замороженного порога, выбран описательно (>=50 чел/км² -
# заметно выше средней плотности страны ~45). Цвета - 4 узла из той же
# секвенциальной шкалы _STOPS (не новая палитра, чтобы класс и "люди в
# клетке" читались как один язык цвета).
DENSITY_CLASSES = [
    (0.0, 1.0, (15, 35, 66), "почти никого"),      # < 1 чел/км²
    (1.0, 5.0, (20, 90, 110), "редко"),             # 1-5
    (5.0, 50.0, (70, 160, 165), "обычно"),          # 5-50
    (50.0, float("inf"), (235, 245, 240), "густо"),  # >= 50
]


def lut() -> np.ndarray:
    t = np.linspace(0, 1, 256)
    out = np.zeros((256, 3), dtype="uint8")
    for c in range(3):
        xs = [s[0] for s in _STOPS]
        ys = [s[1][c] for s in _STOPS]
        out[:, c] = np.clip(np.interp(t, xs, ys), 0, 255).astype("uint8")
    return out


def _norm(a: np.ndarray) -> np.ndarray:
    v = np.log1p(np.clip(a, 0, VMAX)) / math.log1p(VMAX)
    return np.clip(v, 0, 1) ** GAMMA


def _to_webp(v: np.ndarray, path, rng, table, badge: str | None,
             noise: float = NOISE) -> None:
    x = v * 255.0
    if noise > 0:
        lit = x > 0.5
        x = np.where(lit, x + rng.uniform(-noise, noise, v.shape), 0.0)
    idx = np.clip(np.round(x), 0, 255).astype("uint8")
    rgb = table[idx]
    img = Image.fromarray(rgb, mode="RGB")
    if badge:
        HATCH, TXT, BGD = (110, 200, 210), (250, 253, 250), (8, 8, 24)
        d = ImageDraw.Draw(img)
        w, h = img.size
        step, m = 18, 3
        for x0 in range(0, w, step):
            d.line([(x0, m), (min(x0 + 9, w), m)], fill=HATCH, width=2)
            d.line([(x0, h - m), (min(x0 + 9, w), h - m)], fill=HATCH, width=2)
        for y0 in range(0, h, step):
            d.line([(m, y0), (m, min(y0 + 9, h))], fill=HATCH, width=2)
            d.line([(w - m, y0), (w - m, min(y0 + 9, h))], fill=HATCH, width=2)
        font = ImageFont.truetype(str(FONT_PATH), 42)
        pad = 14
        tb = d.textbbox((0, 0), badge, font=font)
        bw, bh = tb[2] - tb[0], tb[3] - tb[1]
        d.rectangle([w - bw - pad * 3, m + 8, w - m - 6, m + 8 + bh + pad * 2],
                    fill=BGD)
        d.text((w - bw - pad * 2, m + 8 + pad - tb[1]), badge, font=font, fill=TXT)
    img.save(path, format="WEBP", quality=72, method=6)


def _classify_rgb(a: np.ndarray) -> np.ndarray:
    """Значения плотности -> RGB по DENSITY_CLASSES (плоская заливка,
    без дизеринга - классы дискретны, полутон между ними был бы ложью)."""
    h, w = a.shape
    rgb = np.zeros((h, w, 3), dtype="uint8")
    for lo, hi, color, _label in DENSITY_CLASSES:
        mask = (a >= lo) & (a < hi)
        rgb[mask] = color
    return rgb


def _to_webp_flat(rgb: np.ndarray, path, badge: str | None) -> None:
    img = Image.fromarray(rgb, mode="RGB")
    if badge:
        HATCH, TXT, BGD = (110, 200, 210), (250, 253, 250), (8, 8, 24)
        d = ImageDraw.Draw(img)
        w, h = img.size
        step, m = 18, 3
        for x0 in range(0, w, step):
            d.line([(x0, m), (min(x0 + 9, w), m)], fill=HATCH, width=2)
            d.line([(x0, h - m), (min(x0 + 9, w), h - m)], fill=HATCH, width=2)
        for y0 in range(0, h, step):
            d.line([(m, y0), (m, min(y0 + 9, h))], fill=HATCH, width=2)
            d.line([(w - m, y0), (w - m, min(y0 + 9, h))], fill=HATCH, width=2)
        font = ImageFont.truetype(str(FONT_PATH), 42)
        pad = 14
        tb = d.textbbox((0, 0), badge, font=font)
        bw, bh = tb[2] - tb[0], tb[3] - tb[1]
        d.rectangle([w - bw - pad * 3, m + 8, w - m - 6, m + 8 + bh + pad * 2],
                    fill=BGD)
        d.text((w - bw - pad * 2, m + 8 + pad - tb[1]), badge, font=font, fill=TXT)
    img.save(path, format="WEBP", quality=80, method=6, lossless=False)


def render_observed_density() -> list[str]:
    names = []
    for epoch in EPOCHS:
        with rasterio.open(RASTERS_CONSTRAINED / f"pop_{epoch}.tif") as s:
            a = s.read(1)
        rgb = _classify_rgb(a)
        name = f"density_{epoch}.webp"
        _to_webp_flat(rgb, FRAMES / name, None)
        names.append(name)
    return names


def render_forecast_density() -> list[str]:
    ids, feats, raions, minsk = _adm_geoms_moll()
    ref = RASTERS_CONSTRAINED / "pop_2020.tif"
    labels, ids2, transform, crs = zone_labels(ref)
    stack, transform, crs, shape = load_observed_stack()
    slope, intercept, ever_populated, t_mean = fit_log_share_trend(stack, labels, ids)
    forecast_by_raion, _ = load_forecast()
    with rasterio.open(ref) as s:
        raster_2020 = s.read(1)
    anchors = anchors_from_2020(raster_2020, transform)
    suburb_score, periphery_score = suburb_periphery_adjustment(shape, transform, anchors)

    names = []
    for year in FORECAST_YEARS:
        for scn in SCENARIOS:
            for variant in VARIANTS:
                proj = project_epoch(slope, intercept, t_mean, ever_populated,
                                      labels, ids, forecast_by_raion, year,
                                      scn, variant, suburb_score, periphery_score)
                rgb = _classify_rgb(proj)
                badge = f"МОДЕЛЬ · {SCN_RU[scn]} · {VARIANT_RU[variant]}"
                name = f"density_{year}_{scn}_{variant}.webp"
                _to_webp_flat(rgb, FRAMES / name, badge)
                names.append(name)
        print(f"  прогноз (плотность) {year}: ok")
    return names


def render_observed(table, rng) -> list[str]:
    names = []
    for epoch in EPOCHS:
        with rasterio.open(RASTERS_CONSTRAINED / f"pop_{epoch}.tif") as s:
            a = s.read(1)
        v = _norm(a)
        name = f"pop_{epoch}.webp"
        _to_webp(v, FRAMES / name, rng, table, None)
        names.append(name)
    return names


def render_forecast(table, rng) -> list[str]:
    ids, feats, raions, minsk = _adm_geoms_moll()
    ref = RASTERS_CONSTRAINED / "pop_2020.tif"
    labels, ids2, transform, crs = zone_labels(ref)
    stack, transform, crs, shape = load_observed_stack()
    slope, intercept, ever_populated, t_mean = fit_log_share_trend(stack, labels, ids)
    forecast_by_raion, _ = load_forecast()
    with rasterio.open(ref) as s:
        raster_2020 = s.read(1)
    anchors = anchors_from_2020(raster_2020, transform)
    suburb_score, periphery_score = suburb_periphery_adjustment(shape, transform, anchors)

    names = []
    for year in FORECAST_YEARS:
        for scn in SCENARIOS:
            for variant in VARIANTS:
                proj = project_epoch(slope, intercept, t_mean, ever_populated,
                                      labels, ids, forecast_by_raion, year,
                                      scn, variant, suburb_score, periphery_score)
                v = _norm(proj)
                badge = f"МОДЕЛЬ · {SCN_RU[scn]} · {VARIANT_RU[variant]}"
                name = f"pop_{year}_{scn}_{variant}.webp"
                _to_webp(v, FRAMES / name, rng, table, badge)
                names.append(name)
        print(f"  прогноз {year}: ok")
    return names


def write_meta() -> None:
    grid_meta = json.loads((RAW / "grid_meta.json").read_text())
    with rasterio.open(RASTERS_CONSTRAINED / "pop_2020.tif") as s:
        from rasterio.warp import transform_bounds
        b = s.bounds
        lon_min, lat_min, lon_max, lat_max = transform_bounds(
            s.crs, "EPSG:4326", b.left, b.bottom, b.right, b.top)
    meta = {
        "bounds_lonlat": [lon_min, lat_min, lon_max, lat_max],
        "width": grid_meta["width"], "height": grid_meta["height"],
        "vmax": VMAX, "gamma": GAMMA, "seed": SEED,
        "crs_analysis": grid_meta["crs"],
        "note": "кадры - image-overlay в 4 угловых координатах EPSG:4326; "
                "расчётная сетка/площадь ячейки - в ESRI:54009 (см. D-001)",
        "density_classes": [
            {"min": lo, "max": (hi if hi != float("inf") else None),
             "color": f"rgb({color[0]},{color[1]},{color[2]})", "label": label}
            for lo, hi, color, label in DENSITY_CLASSES
        ],
    }
    (FRAMES / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------- G-3 ----

def g3_nightlights_crosscheck() -> dict:
    nl = json.loads((OUT / "nightlights_v2.json").read_text())
    light_by_raion = {r["id"]: r["light"] for r in nl["rows"]}

    official = load_raion_series()
    ids, feats, raions, minsk = _adm_geoms_moll()

    host_raions = set()
    from .registry import OBLAST_CITIES_HOST, raion_id
    for lat in OBLAST_CITIES_HOST.values():
        host_raions.add(raion_id(lat))

    rows = []
    for tid in ids:
        light = light_by_raion.get(tid)
        pop_series = official.get(tid, {})
        if not light or "2012" not in light or "2020" not in light:
            continue
        pop_2012 = interp_official(pop_series, 2012)
        pop_2020 = interp_official(pop_series, 2020)
        if pop_2012 is None or pop_2020 is None:
            continue
        d_pop = pop_2020 - pop_2012
        d_light = light["2020"] - light["2012"]
        agree = (d_pop >= 0) == (d_light >= 0)
        rows.append({"raion": tid, "d_pop": d_pop, "d_light": round(d_light, 2),
                     "agree": agree, "is_city_host": tid in host_raions})

    n = len(rows)
    n_agree = sum(1 for r in rows if r["agree"])
    host = [r for r in rows if r["is_city_host"]]
    non_host = [r for r in rows if not r["is_city_host"]]
    result = {
        "years": [2012, 2020], "n_raions": n,
        "n_agree": n_agree, "pct_agree": round(n_agree / n * 100, 1) if n else None,
        "threshold_pct": 70, "pass": (n_agree / n * 100 >= 70) if n else None,
        "city_host_raions": {
            "n": len(host), "n_agree": sum(1 for r in host if r["agree"]),
            "pct_agree": round(sum(1 for r in host if r["agree"]) / len(host) * 100, 1) if host else None,
        },
        "non_host_raions": {
            "n": len(non_host), "n_agree": sum(1 for r in non_host if r["agree"]),
            "pct_agree": round(sum(1 for r in non_host if r["agree"]) / len(non_host) * 100, 1) if non_host else None,
        },
        "disagreements": [r["raion"] for r in rows if not r["agree"]],
    }
    return result, rows


def main() -> None:
    FRAMES.mkdir(parents=True, exist_ok=True)
    write_meta()
    table = lut()

    rng = np.random.default_rng(SEED)
    obs = render_observed(table, rng)
    print(f"OK: {len(obs)} кадров наблюдений")

    rng = np.random.default_rng(SEED + 1)
    fut = render_forecast(table, rng)
    print(f"OK: {len(fut)} кадров прогноза")

    obs_d = render_observed_density()
    fut_d = render_forecast_density()
    print(f"OK: {len(obs_d) + len(fut_d)} кадров класса плотности "
          f"(WP-1/B-2, docs/notes/grid_ux_audit_2026-07-27.md)")

    all_names = obs + fut + obs_d + fut_d
    sizes = [(FRAMES / n).stat().st_size for n in all_names]
    total_mb = sum(sizes) / 1e6
    big = [n for n in all_names if (FRAMES / n).stat().st_size > FRAME_KB_MAX * 1024]
    print(f"  всего {len(all_names)} кадров, {total_mb:.2f} МБ "
          f"(бюджет {TOTAL_MB_MAX} МБ); >{FRAME_KB_MAX}КБ: {big or 'нет'}")

    g3, g3_rows = g3_nightlights_crosscheck()
    print(f"\nG-3: согласие знаков свет/сетка {g3['pct_agree']}% "
          f"({g3['n_agree']}/{g3['n_raions']}, порог 70%, pass={g3['pass']})")
    print(f"  города-хозяева: {g3['city_host_raions']['pct_agree']}% "
          f"({g3['city_host_raions']['n_agree']}/{g3['city_host_raions']['n']})")
    print(f"  прочие районы: {g3['non_host_raions']['pct_agree']}% "
          f"({g3['non_host_raions']['n_agree']}/{g3['non_host_raions']['n']})")

    (RAW / "g3_nightlights_crosscheck.json").write_text(
        json.dumps(g3, indent=2, ensure_ascii=False) + "\n")
    import csv
    with open(RAW / "g3_nightlights_rows.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["raion", "d_pop", "d_light", "agree", "is_city_host"])
        w.writeheader()
        w.writerows(g3_rows)

    budget_report = {
        "n_frames": len(all_names), "total_mb": round(total_mb, 3),
        "total_mb_budget": TOTAL_MB_MAX,
        "frame_kb_max_observed": round(max(sizes) / 1024, 1),
        "frame_kb_budget": FRAME_KB_MAX,
        "within_budget": total_mb <= TOTAL_MB_MAX and not big,
    }
    (FRAMES / "budget_report.json").write_text(
        json.dumps(budget_report, indent=2, ensure_ascii=False))
    if not budget_report["within_budget"]:
        print("\n!!! БЮДЖЕТ ПРЕВЫШЕН - см. раздел 13 ТЗ (fallback: шаг 10 лет / "
              "ниже разрешение / убрать вариант Б с карты)")


if __name__ == "__main__":
    main()
