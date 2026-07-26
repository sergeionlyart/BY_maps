#!/usr/bin/env python3
"""Рилс R-P1 «Кто кого содержит» (INF-13): хороплет 118 районов Беларуси,
раскрашенных по коэффициенту поддержки (SR), 2009 -> 2056.

Механически повторяет tools/render_reel_pyramid.py (образец из ТЗ Приложения
А): сцена-JSON (tools/reel_pension_scene.json) задаёт хронометраж/тексты,
render_frame() компонует кадр, render() пишет PNG-превью или пайпит сырые
RGB24-кадры в ffmpeg. Ключевое отличие от пирамиды — вместо бар-чарта здесь
хороплет: полигоны районов из web/public/data/geo/adm2.geojson загружаются
shapely (shapely.geometry.shape умеет и Polygon, и MultiPolygon одним
интерфейсом — 118 Polygon + 1 MultiPolygon, r-horacki), проецируются простой
аффинной проекцией (bbox + косинус-коррекция по широте, см. make_projector),
растеризуются PIL.ImageDraw.polygon(). Ни matplotlib, ни какая-либо ГИС-
библиотека не используются (запрет проекта на новые зависимости для этой
сдачи) - shapely/Pillow/numpy уже были в .venv до этого поручения.

Цветовая шкала - буквальный перенос web/components/pension/scale.ts
(SR_BREAKS, дивергентная, середина на 1,5) и hex-констант DIV_NEG/DIV_MID/
DIV_POS из web/lib/scales.ts (см. HEX_* ниже с комментарием-источником) -
тот же визуальный язык, что и на живой странице /research/pension.

Все числа в подписях кадра ({below20}/{below15}/{sr_karelicki}/{eligible-
Count}/{beyondCount}/{shiftAvg}) вычисляются на лету из web/public/data/
pension.json (см. sr_interp/compute_h3_stats) - не вписаны вручную в JSON,
чтобы не разойтись с опубликованными данными (тот же принцип, что и
web/components/pension/Findings.tsx, который тоже считает H1-H3 из
pension.json в момент рендера, а не хранит их как текст).

Запуск: python tools/render_reel_pension.py [--lang ru|be|all]
        [--dump-every N]   # превью-кадры вместо видео
Выход: build/reel_pension_<lang>.mp4 (CBR 12M, как у остальных рилсов INF-08/11)
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import shape

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
try:
    from etl.nightlights_frames import FONT_PATH  # noqa: E402  (вендоренный шрифт, кириллица+ў)
except ModuleNotFoundError:
    # etl.nightlights_frames импортирует rasterio на уровне модуля (растровый
    # стек Nightlights INF-08). rasterio не входит в список зависимостей этой
    # сдачи и не установлен в .venv INF-13 (то же самое известное, принятое
    # ограничение, из-за которого CI скипает тесты кадров рилса Nightlights -
    # см. коммит "CI: тесты кадров рилса skip без rasterio"). Тот же самый
    # путь к тому же самому вендоренному файлу шрифта, без импорта rasterio -
    # НЕ новая зависимость, только устойчивость к отсутствующей опциональной.
    FONT_PATH = ROOT / "data" / "raw" / "nightlights" / "fonts" / "DejaVuSans.ttf"

W, H = 1080, 1920
BG = (12, 12, 11)
INK = (238, 233, 222)
DIM = (150, 143, 130)
AMBER = (240, 205, 150)
NODATA = (46, 44, 40)          # район вне 118 (BY-HM, Минск-город - не входит в territories)
BORDER = (18, 17, 15)          # тонкая граница района
HIGHLIGHT = (255, 214, 120)    # обводка подсвеченного района (Кореличский)

# --- цветовая шкала SR: буквальный перенос web/components/pension/scale.ts
#     (SR_BREAKS) + web/lib/scales.ts (DIV_NEG/DIV_MID/DIV_POS, диапазон
#     10-11) - тот же дивергентный ряд, середина на пороге 1,5, что и на
#     живой карте /research/pension. Значения не зависят от темы (в scale.ts
#     это литеральные hex, а не CSS-переменные) - взяты как есть.
SR_BREAKS = [1.0, 1.17, 1.33, 1.45, 1.55, 1.75, 2.0, 2.5]


def _hx(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


DIV_NEG = [_hx("#f0b9b9"), _hx("#e57f7e"), _hx("#d03b3b"), _hx("#a02222")]
DIV_MID = _hx("#f0efec")
DIV_POS = [_hx("#b7d3f6"), _hx("#6da7ec"), _hx("#2a78d6"), _hx("#184f95")]
ACCENT = _hx("#3987e5")        # web/app/globals.css, --accent (тёмная тема) - для штриховки прогноза


def sr_color(v: float | None) -> tuple[int, int, int]:
    """Портирована 1:1 из srColor() в web/components/pension/scale.ts."""
    if v is None:
        return NODATA
    b = SR_BREAKS
    if v < b[0]:
        return DIV_NEG[3]
    if v < b[1]:
        return DIV_NEG[2]
    if v < b[2]:
        return DIV_NEG[1]
    if v < b[3]:
        return DIV_NEG[0]
    if v <= b[4]:
        return DIV_MID
    if v <= b[5]:
        return DIV_POS[0]
    if v <= b[6]:
        return DIV_POS[1]
    if v <= b[7]:
        return DIV_POS[2]
    return DIV_POS[3]


TERRITORY_YEARS = [2009, 2019, 2026, 2031, 2036, 2041, 2046, 2051, 2056]
SCENARIO = "base:official"     # заморожено в пререгистрации (docs/preregistration/pension-v0.1.md), см. Findings.tsx KEY

MAP_X0, MAP_Y0, MAP_W, MAP_H = 40, 430, 1000, 1010
LEGEND_Y = MAP_Y0 + MAP_H + 30
CAPTION_Y = LEGEND_Y + 90
SOURCE_Y = H - 60


def font(sz: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_PATH), sz)


def ru_num(v: float, nd: int = 2) -> str:
    """Запятая вместо точки - русская/белорусская типографика (как в
    docs/decisions/INF-13.md, methods/pension.md: «1,48», «58,5%»)."""
    return f"{v:.{nd}f}".replace(".", ",")


def fit_text(d: ImageDraw.ImageDraw, xy, text: str, sz: int, fill,
             maxw=W - 80, anchor="ma"):
    f = font(sz)
    while d.textlength(text, font=f) > maxw and sz > 20:
        sz -= 2
        f = font(sz)
    d.text(xy, text, font=f, fill=fill, anchor=anchor)


def wrap_center(d: ImageDraw.ImageDraw, y: int, text: str, sz: int, fill,
                 maxw=W - 100, lh=1.35) -> int:
    f = font(sz)
    words = text.split()
    lines, cur = [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if d.textlength(trial, font=f) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    for ln in lines:
        d.text((W / 2, y), ln, font=f, fill=fill, anchor="ma")
        y += int(sz * lh)
    return y


# ---------------------------------------------------------------- данные ---

def load_pension() -> dict:
    return json.loads((ROOT / "web/public/data/pension.json").read_text())


def load_scene() -> dict:
    return json.loads((ROOT / "tools/reel_pension_scene.json").read_text())


def sr_interp(series: list[float], year: float) -> float:
    """Линейная интерполяция между известными районными годами
    (2009,2019,2026,2031,...,2056) - тот же приём, что crossing_year()
    в etl/pension.py использует для года перехода (methods/pension.md §3
    п.4: «год перехода... линейной интерполяцией между известными точками
    ряда»). За пределами диапазона - клэмп к ближайшему краю."""
    yrs = TERRITORY_YEARS
    if year <= yrs[0]:
        return series[0]
    if year >= yrs[-1]:
        return series[-1]
    for i in range(len(yrs) - 1):
        if yrs[i] <= year <= yrs[i + 1]:
            k = (year - yrs[i]) / (yrs[i + 1] - yrs[i])
            return series[i] * (1 - k) + series[i + 1] * k
    return series[-1]


def sr_now_for(terr: dict, year: float, seg: dict, k: float) -> float:
    """SR района в текущем кадре с учётом сегмента сцены: если сегмент несёт
    поле "policy" c двумя разными вариантами (переключатель пенсионного
    возраста), плавно смешивает их по k (та же k, что используется для года
    в этом сегменте - в сегментах "policy" год зафиксирован на 2056, поэтому
    k однозначно читается как прогресс переключателя)."""
    pol = seg.get("policy", ["as_is", "as_is"])
    s = terr["sr"]
    if pol[0] == pol[1]:
        return sr_interp(s[pol[0]][SCENARIO], year)
    a = sr_interp(s[pol[0]][SCENARIO], year)
    b = sr_interp(s[pol[1]][SCENARIO], year)
    return a * (1 - k) + b * k


def year_dtype(year: float, dtype_map: dict[str, str]) -> str:
    for y in TERRITORY_YEARS:
        if abs(year - y) < 1e-6:
            return dtype_map[str(y)]
    return "interp"


def compute_h3_stats(territories: dict, threshold="1.5", horizon=2056):
    """Пересчёт H3 (docs/decisions/INF-13.md, запись «H3 технически
    опровергнута...») напрямую из crossing[as_is]/crossing[65_60] -
    идентично методу web/components/pension/Findings.tsx (не переиспользует
    её код, TS/Python, но та же логика и тот же ключ SCENARIO)."""
    eligible = beyond = 0
    shifts: list[float] = []
    for terr in territories.values():
        c_as = terr["crossing"]["as_is"][SCENARIO][threshold]
        if c_as is not None and c_as <= horizon:
            eligible += 1
            c_alt = terr["crossing"]["65_60"][SCENARIO][threshold]
            if c_alt is None:
                beyond += 1
            else:
                shifts.append(c_alt - c_as)
    avg_shift = sum(shifts) / len(shifts) if shifts else 0.0
    return eligible, beyond, avg_shift


# --------------------------------------------------------------- геометрия ---

def load_geo(territories: dict) -> tuple[list[dict], tuple[float, float, float, float]]:
    """Грузит adm2.geojson через shapely.geometry.shape (единый интерфейс
    для Polygon и MultiPolygon - в файле 118 Polygon + 1 MultiPolygon,
    r-horacki, см. проверку при разведке), считает bbox по ВСЕМ 119
    фичам (включая BY-HM - Минск-город, единственная не входящая в 118
    territories, дырка внутри r-minski)."""
    gj = json.loads((ROOT / "web/public/data/geo/adm2.geojson").read_text())
    feats = []
    minx = miny = 1e18
    maxx = maxy = -1e18
    for f in gj["features"]:
        gid = f["properties"]["id"]
        geom = shape(f["geometry"])
        subpolys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        rings = [list(p.exterior.coords) for p in subpolys]
        for ring in rings:
            for lon, lat in ring:
                minx, maxx = min(minx, lon), max(maxx, lon)
                miny, maxy = min(miny, lat), max(maxy, lat)
        feats.append({"id": gid, "rings": rings, "area": geom.area,
                      "in_territories": gid in territories})
    # Крупные районы рисуются первыми, мелкие (анклавы вроде BY-HM внутри
    # r-minski) - поверх; этого достаточно, чтобы «дыра» в r-minski не
    # рисовалась отдельной логикой punch-hole - PIL ImageDraw.polygon не
    # умеет кольца-дырки напрямую, а рисовать сверху меньший полигон -
    # эквивалентный и более простой результат при таком порядке отрисовки.
    feats.sort(key=lambda f: -f["area"])
    return feats, (minx, miny, maxx, maxy)


def make_projector(bbox, box_x0, box_y0, box_w, box_h):
    """Простая аффинная проекция bbox->пиксели с косинус-коррекцией по
    широте (Беларусь ~52-56 с.ш.: без коррекции долгота растягивала бы
    страну по горизонтали - 1 градус долготы на этой широте короче градуса
    широты примерно в cos(54°)~0.59 раза). Не проекция в ГИС-смысле (никакой
    новой библиотеки), просто масштаб по x, отличный от масштаба по y."""
    minx, miny, maxx, maxy = bbox
    mean_lat = (miny + maxy) / 2
    lat_corr = math.cos(math.radians(mean_lat))
    corr_w = (maxx - minx) * lat_corr
    corr_h = (maxy - miny)
    scale = min(box_w / corr_w, box_h / corr_h)
    used_w, used_h = corr_w * scale, corr_h * scale
    off_x = box_x0 + (box_w - used_w) / 2
    off_y = box_y0 + (box_h - used_h) / 2

    def proj(lon: float, lat: float) -> tuple[float, float]:
        x = off_x + (lon - minx) * lat_corr * scale
        y = off_y + (maxy - lat) * scale
        return (x, y)

    return proj


def precompute_pixels(feats: list[dict], proj) -> None:
    for f in feats:
        f["pixel_rings"] = [[proj(lon, lat) for lon, lat in ring] for ring in f["rings"]]


def make_hatch_overlay(w: int, h: int, color=ACCENT, alpha=64,
                        stripe=10, gap=18) -> Image.Image:
    """Диагональная 45-градусная штриховка - тот же приём, что
    .forecast-zone в web/app/globals.css (repeating-linear-gradient(45deg,
    ...)), просто отрисован вручную линиями (у PIL нет CSS-градиентов).
    Масштаб штрихов крупнее, чем на сайте (там штрихует 14px-полоску
    слайдера, здесь - карту ~1000px)."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    period = stripe + gap
    col = (*color, alpha)
    x = -h
    while x < w + h:
        d.line([(x, 0), (x + h, h)], fill=col, width=stripe)
        x += period
    return img


# ---------------------------------------------------------------- отрисовка ---

def draw_map(img: Image.Image, feats: list[dict], srs: dict[str, float]) -> None:
    d = ImageDraw.Draw(img)
    for f in feats:
        color = sr_color(srs.get(f["id"])) if f["in_territories"] else NODATA
        for ring in f["pixel_rings"]:
            d.polygon(ring, fill=color, outline=BORDER)


def draw_highlight(img: Image.Image, feats_by_id: dict[str, dict], gid: str) -> None:
    d = ImageDraw.Draw(img)
    f = feats_by_id.get(gid)
    if not f:
        return
    for ring in f["pixel_rings"]:
        d.line(ring + [ring[0]], fill=HIGHLIGHT, width=5)


def draw_legend(d: ImageDraw.ImageDraw, T: dict) -> None:
    colors = [DIV_NEG[3], DIV_NEG[2], DIV_NEG[1], DIV_NEG[0], DIV_MID,
              DIV_POS[0], DIV_POS[1], DIV_POS[2], DIV_POS[3]]
    n = len(colors)
    x0, y0, w, h = 140, LEGEND_Y, W - 280, 34
    sw = w / n
    for i, c in enumerate(colors):
        d.rectangle([x0 + i * sw, y0, x0 + (i + 1) * sw - 2, y0 + h], fill=c)
    d.text((x0, y0 + h + 8), T["legendLo"], font=font(22), fill=DIM, anchor="la")
    d.text((x0 + w, y0 + h + 8), T["legendHi"], font=font(22), fill=DIM, anchor="ra")
    d.text((x0 + w / 2, y0 + h + 8), T["legendMid"], font=font(22), fill=AMBER, anchor="ma")


def draw_toggle(d: ImageDraw.ImageDraw, T: dict, k: float) -> None:
    """Переключатель пенсионного возраста 63/58 -> 65/60 - визуальный аналог
    сегмент-контрола .seg на живой странице (PensionSlider/страница)."""
    y0, h = 250, 64
    w = 260
    gap = 20
    x0 = W / 2 - w - gap / 2
    x1 = W / 2 + gap / 2
    d.text((W / 2, y0 - 34), T["toggleLabel"], font=font(26), fill=DIM, anchor="ma")
    on_a = INK if k < 0.5 else DIM
    fill_a = AMBER if k < 0.5 else (30, 28, 24)
    on_b = DIM if k < 0.5 else INK
    fill_b = (30, 28, 24) if k < 0.5 else AMBER
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=10, fill=fill_a,
                        outline=AMBER, width=2)
    d.text((x0 + w / 2, y0 + h / 2), T["toggleAsIs"], font=font(32),
           fill=(20, 16, 10) if k < 0.5 else on_a, anchor="mm")
    d.rounded_rectangle([x1, y0, x1 + w, y0 + h], radius=10, fill=fill_b,
                        outline=AMBER, width=2)
    d.text((x1 + w / 2, y0 + h / 2), T["toggle6560"], font=font(32),
           fill=(20, 16, 10) if k >= 0.5 else on_b, anchor="mm")


def render_frame(gi: int, fps: int, pension: dict, feats: list[dict],
                 feats_by_id: dict, hatch: Image.Image, scene: dict,
                 lang: str, h3stats: tuple[int, int, float]) -> Image.Image:
    t = gi / fps
    duration = scene["format"]["durationSec"]
    T = scene["texts"][lang]
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    seg = next(s for s in scene["timeline"]
               if s["t"][0] <= t < s["t"][1] or s is scene["timeline"][-1])
    k = (t - seg["t"][0]) / max(seg["t"][1] - seg["t"][0], 1e-9)
    k = min(max(k, 0), 1)
    year = seg["year"][0] + (seg["year"][1] - seg["year"][0]) * k
    scene_id = seg["scene"]
    eligible, beyond, shift_avg = h3stats

    nat = pension["national"]
    nat_years = pension["years"]["national"]
    nat_sr = nat["sr"]["as_is"][SCENARIO]

    if scene_id == "hook":
        v0 = nat_sr[nat_years.index(2009)]
        v1 = nat_sr[-1]
        d.text((W / 2, 620), ru_num(v0), font=font(150), fill=INK, anchor="ma")
        d.text((W / 2, 800), "↓", font=font(90), fill=AMBER, anchor="ma")
        d.text((W / 2, 900), ru_num(v1), font=font(150), fill=AMBER, anchor="ma")
        wrap_center(d, 1140, T["hookLine"], 46, INK)
        wrap_center(d, 1400, T["mapSubtitle"], 30, DIM)
        d.line([(0, H - 6), (W * t / duration, H - 6)], fill=AMBER, width=6)
        return img

    if scene_id == "finale":
        d.text((W / 2, 260), T["brand"], font=font(80), fill=AMBER, anchor="ma")
        d.text((W / 2, 365), T["brandTag"], font=font(32), fill=INK, anchor="ma")
        d.text((W / 2, 480), T["sourceNote"], font=font(24), fill=DIM, anchor="ma")

        bx0, bx1 = 90, W - 90
        by0, by1 = 820, 1160
        d.rectangle([bx0, by0, bx1, by1], outline=AMBER, width=3)
        d.text((W / 2, by0 + 40), T["disclaimerTitle"], font=font(30),
               fill=AMBER, anchor="ma")
        wrap_center(d, by0 + 100, T["disclaimer"], 32, INK, maxw=bx1 - bx0 - 80)

        fit_text(d, (W / 2, 1500), T["ctaUrl"], 42, AMBER)
        d.line([(0, H - 6), (W * t / duration, H - 6)], fill=AMBER, width=6)
        return img

    # --- сцены с картой (observed / forecast / policy) ---
    srs = {tid: sr_now_for(terr, year, seg, k) for tid, terr in pension["territories"].items()}
    below20 = sum(1 for v in srs.values() if v < 2.0)
    below15 = sum(1 for v in srs.values() if v < 1.5)
    sr_karelicki = srs.get("r-karelicki", 0.0)

    is_forecast_look = scene_id in ("forecast", "policy")

    d.text((W / 2, 60), str(int(round(year))), font=font(92), fill=INK, anchor="ma")
    dtyp = year_dtype(year, pension["dtype"]["territory"])
    d.text((W / 2, 168), T["typeLabels"].get(dtyp, dtyp), font=font(28),
           fill=AMBER if dtyp == "f" else DIM, anchor="ma")
    if scene_id != "policy":
        # в сцене "policy" это место занимает переключатель возраста
        # (draw_toggle) - подпись карты здесь не рисуется, чтобы не
        # накладывался текст.
        d.text((W / 2, 202), T["mapSubtitle"], font=font(22), fill=DIM, anchor="ma")

    if is_forecast_look:
        f1 = font(28)
        tw = d.textlength(T["forecastBadge"], font=f1)
        d.rectangle([W - tw - 56, 26, W - 20, 66], fill=(30, 24, 16))
        d.text((W - 38, 32), T["forecastBadge"], font=f1, fill=AMBER, anchor="ra")

    if scene_id == "policy":
        draw_toggle(d, T, k)
        counter_label, counter_val = T["counterLabel15"], below15
        counter_y = 345
    elif is_forecast_look:
        counter_label, counter_val = T["counterLabel15"], below15
        counter_y = 250
    else:
        counter_label, counter_val = T["counterLabel20"], below20
        counter_y = 250
    fit_text(d, (W / 2, counter_y),
            f"{counter_label}: {counter_val} / 118", 44,
            AMBER if is_forecast_look else INK)

    draw_map(img, feats, srs)
    d = ImageDraw.Draw(img)

    if is_forecast_look:
        # штриховка поверх раскрашенной карты - визуальный аналог
        # .forecast-zone (globals.css): полупрозрачная диагональ + акцентная
        # полоса слева, "зона прогноза" отличима от наблюдаемого периода.
        img.paste(hatch, (MAP_X0, MAP_Y0), hatch)
        d.rectangle([MAP_X0 - 6, MAP_Y0, MAP_X0 - 2, MAP_Y0 + MAP_H], fill=ACCENT)

    draw_legend(d, T)

    for c in scene["callouts"][lang]:
        if not (c["t"][0] <= t < c["t"][1]):
            continue
        if "highlight" in c:
            draw_highlight(img, feats_by_id, c["highlight"])
            d = ImageDraw.Draw(img)
        ctx = {
            "year": int(round(year)),
            "below20": below20,
            "below15": below15,
            "sr_karelicki": ru_num(sr_karelicki, 2),
            "eligibleCount": eligible,
            "beyondCount": beyond,
            "shiftAvg": ru_num(shift_avg, 1),
        }
        text = c["text"].format(**ctx)
        f1 = font(34)
        maxw = W - 140
        while d.textlength(text, font=f1) > maxw and f1.size > 22:
            f1 = font(f1.size - 2)
        tw = d.textlength(text, font=f1)
        ty = CAPTION_Y
        d.rectangle([W / 2 - tw / 2 - 18, ty - 10, W / 2 + tw / 2 + 18, ty + 44],
                    fill=(30, 24, 16))
        d.text((W / 2, ty), text, font=f1, fill=AMBER, anchor="ma")

    d.text((W / 2, SOURCE_Y), T["sourceNote"], font=font(20), fill=DIM, anchor="ma")
    d.line([(0, H - 6), (W * t / duration, H - 6)], fill=AMBER, width=6)
    return img


def render(lang: str, dump_every: int) -> None:
    pension = load_pension()
    scene = load_scene()
    feats, bbox = load_geo(pension["territories"])
    proj = make_projector(bbox, MAP_X0, MAP_Y0, MAP_W, MAP_H)
    precompute_pixels(feats, proj)
    feats_by_id = {f["id"]: f for f in feats}
    hatch = make_hatch_overlay(MAP_W, MAP_H)
    h3stats = compute_h3_stats(pension["territories"])

    fps = scene["format"]["fps"]
    total = int(scene["format"]["durationSec"] * fps)
    out_dir = ROOT / "build"
    out_dir.mkdir(exist_ok=True)

    if dump_every:
        dd = out_dir / f"reel_pension_preview_{lang}"
        dd.mkdir(parents=True, exist_ok=True)
        for gi in range(0, total, dump_every):
            render_frame(gi, fps, pension, feats, feats_by_id, hatch, scene,
                        lang, h3stats).save(dd / f"f{gi:05d}.png")
        print(f"OK: превью в {dd}")
        return

    dst = out_dir / f"reel_pension_{lang}.mp4"
    cmd = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-c:v", "libx264", "-preset", "slow",
           "-b:v", "12M", "-minrate", "12M", "-maxrate", "12M",
           "-bufsize", "24M", "-x264-params", "nal-hrd=cbr",
           "-pix_fmt", "yuv420p", str(dst)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    import numpy as np
    for gi in range(total):
        img = render_frame(gi, fps, pension, feats, feats_by_id, hatch,
                           scene, lang, h3stats)
        proc.stdin.write(np.asarray(img, dtype="uint8").tobytes())
        if gi % 300 == 0:
            print(f"  [{lang}] кадр {gi}/{total}")
    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        raise SystemExit("ffmpeg error")
    print(f"OK: {dst} ({dst.stat().st_size / 1e6:.1f} МБ)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="all", choices=["ru", "be", "all"])
    ap.add_argument("--dump-every", type=int, default=0)
    args = ap.parse_args()
    for lang in (["ru", "be"] if args.lang == "all" else [args.lang]):
        render(lang, args.dump_every)


if __name__ == "__main__":
    main()
