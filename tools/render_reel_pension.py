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


# ------------------------------------------------- бренд-рамка (v1.1) ---
# Требование заказчика к v1.1: первый и последний кадры должны сами по себе
# отвечать «что это за проект и о чём ролик» - контур Беларуси + шрифтовой
# логотип BY MAPS + заголовок-крючок. Логотипа-знака проект не имеет и
# специально не вводит (новый знак пришлось бы согласовывать и катить на
# сайт, в фавиконку и во все пакеты) - используется шрифтовой логотип тем
# же вендоренным DejaVuSans, что и весь ролик, с разрядкой, плюс контур
# страны из того же adm2.geojson. Тот же приём уже заложен в хиро лендинга
# (handoff/06_brand_ui/COLOR_AND_BRAND_REQUIREMENTS.md, A-2: «подложка -
# едва заметный контур Беларуси... из имеющегося adm0-полигона»).

GHOST = (56, 52, 47)           # «недостающий» человек в пиктограмме сцены hook
SIL_FILL = (33, 37, 46)        # заливка силуэта страны (чуть светлее фона)
SIL_EDGE = (198, 150, 90)      # кромка силуэта: медный из палитры бренда
INTRO_MAP_BOX = (110, 800, 860, 780)     # x0, y0, w, h
FINALE_MAP_BOX = (170, 570, 740, 640)

_SIL_CACHE: dict[tuple, Image.Image] = {}


def country_layer(feats: list[dict], box: tuple) -> Image.Image:
    """Силуэт Беларуси одним контуром: объединение всех 119 полигонов
    adm2.geojson (unary_union - shapely уже зависимость этого рендера,
    новых нет), спроецированное тем же make_projector, что и карта в
    основной части ролика. Результат кэшируется - геометрия статична,
    считать её на каждый из 1350 кадров незачем."""
    key = (box, len(feats))
    if key in _SIL_CACHE:
        return _SIL_CACHE[key]
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    minx = miny = 1e18
    maxx = maxy = -1e18
    polys = []
    for f in feats:
        for ring in f["rings"]:
            if len(ring) < 4:
                continue
            polys.append(Polygon(ring).buffer(0))
            for lon, lat in ring:
                minx, maxx = min(minx, lon), max(maxx, lon)
                miny, maxy = min(miny, lat), max(maxy, lat)
    uni = unary_union(polys)
    geoms = list(uni.geoms) if uni.geom_type == "MultiPolygon" else [uni]
    proj = make_projector((minx, miny, maxx, maxy), *box)

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for g in geoms:
        pts = [proj(lon, lat) for lon, lat in g.exterior.coords]
        if len(pts) > 2:
            d.polygon(pts, fill=(*SIL_FILL, 255), outline=(*SIL_EDGE, 255))
            d.line(pts + [pts[0]], fill=(*SIL_EDGE, 255), width=4, joint="curve")
    _SIL_CACHE[key] = img
    return img


def paste_country(img: Image.Image, feats: list[dict], box: tuple,
                  alpha: float = 1.0) -> None:
    lay = country_layer(feats, box)
    if alpha < 0.999:
        lay = lay.copy()
        lay.putalpha(lay.getchannel("A").point(lambda v: int(v * alpha)))
    img.paste(lay, (0, 0), lay)


def tracked_text(d: ImageDraw.ImageDraw, xy, text: str, sz: int, fill,
                 track: float = 0.16, stroke: int = 0) -> float:
    """Текст с разрядкой, центрированный по xy. У PIL нет letter-spacing,
    поэтому символы ставятся вручную - это и делает из обычного DejaVuSans
    узнаваемый шрифтовой логотип, а не просто строку текста."""
    f = font(sz)
    widths = [d.textlength(ch, font=f) for ch in text]
    sp = sz * track
    total = sum(widths) + sp * max(len(text) - 1, 0)
    x = xy[0] - total / 2
    for ch, w in zip(text, widths):
        d.text((x, xy[1]), ch, font=f, fill=fill, anchor="la",
               stroke_width=stroke, stroke_fill=fill)
        x += w + sp
    return total


def draw_person(img: Image.Image, x: float, y: float, h: float, color,
                frac: float = 1.0, outline: bool = False) -> float:
    """Пиктограмма человека (голова + плечи), нарисованная примитивами PIL.
    frac < 1 обрезает фигуру по ширине - так «полтора работающих» читается
    буквально, без округления до целых людей. Возвращает ширину фигуры."""
    w = h * 0.46
    lay = Image.new("RGBA", (int(w) + 4, int(h) + 4), (0, 0, 0, 0))
    dd = ImageDraw.Draw(lay)
    r = h * 0.16
    cx = (w + 4) / 2
    if outline:
        dd.ellipse([cx - r, 2, cx + r, 2 + 2 * r], outline=(*color, 255), width=3)
        dd.rounded_rectangle([2, 2 + 2.6 * r, w + 2, h + 2], radius=w * 0.42,
                             outline=(*color, 255), width=3)
    else:
        dd.ellipse([cx - r, 2, cx + r, 2 + 2 * r], fill=(*color, 255))
        dd.rounded_rectangle([2, 2 + 2.6 * r, w + 2, h + 2], radius=w * 0.42,
                             fill=(*color, 255))
    if frac < 0.999:
        cut = max(2, int((w + 4) * max(frac, 0.0)))
        lay = lay.crop((0, 0, cut, int(h) + 4))
    img.paste(lay, (int(x), int(y)), lay)
    return w


def draw_ratio_row(img: Image.Image, d: ImageDraw.ImageDraw, y: int,
                   label: str, value: float, shown: float) -> None:
    """Строка «N работающих : 1 пожилой». Цвет фигур работающих берётся из
    той же шкалы sr_color, что красит карту в основной части ролика -
    зритель видит те же цвета, что через секунду увидит на хороплете."""
    d.text((110, y), label, font=font(30), fill=DIM, anchor="la")
    col = sr_color(value)
    icon_h, step, x0, top = 150, 104, 110, y + 46
    full = int(shown)
    rest = shown - full
    # Серый «недостающий» человек в незакрытой ячейке: именно он делает
    # видимым, что 0,84 - это МЕНЬШЕ одного работающего, а не «почти один».
    draw_person(img, x0 + full * step, top, icon_h, GHOST)
    if value < 1.0:
        # Район, где работающих меньше, чем пожилых: недостающего человека
        # обводим янтарным - «вот сколько должно было быть».
        draw_person(img, x0 + full * step, top, icon_h, AMBER, outline=True)
    for i in range(full):
        draw_person(img, x0 + i * step, top, icon_h, col)
    if rest > 0.02:
        draw_person(img, x0 + full * step, top, icon_h, col, frac=rest)
    d.line([(546, top - 6), (546, top + icon_h + 6)], fill=(64, 60, 52), width=3)
    draw_person(img, 600, top, icon_h, AMBER)
    lit = tuple(int(c + (INK[i] - c) * 0.35) for i, c in enumerate(col))
    d.text((1010, top + icon_h / 2 - 42), ru_num(shown), font=font(76),
           fill=lit, anchor="ra")


def draw_district_dots(img: Image.Image, d: ImageDraw.ImageDraw, y: int,
                       values: list[float], shown: int) -> None:
    """118 районов = 118 клеток, отсортированных по числу работающих на
    пожилого и покрашенных той же шкалой sr_color. Пять самых тёмно-красных
    слева - это и есть районы, где работающих меньше, чем пожилых."""
    per_row, cell, gap = 20, 40, 8
    grid_w = per_row * cell + (per_row - 1) * gap - (cell + gap) * 0
    x0 = (W - (per_row * (cell + gap) - gap)) / 2
    for i, v in enumerate(values[:shown]):
        cx = x0 + (i % per_row) * (cell + gap)
        cy = y + (i // per_row) * (cell + gap)
        d.rectangle([cx, cy, cx + cell, cy + cell], fill=sr_color(v))
        if v < 1.0:
            d.rectangle([cx - 2, cy - 2, cx + cell + 2, cy + cell + 2],
                        outline=AMBER, width=3)


CHRON_BOX = (190, 180, 700, 700)      # карта в сцене «хроника»: x0, y0, w, h
CHRON_N = 10                          # сколько районов показываем
CHRON_DIM = (34, 33, 30)              # остальные 108 районов гаснут
_CHRON_CACHE: list | None = None


def chronicle_rows(pension: dict) -> list[dict]:
    """Десять районов с самым низким SR к 2056 году - «хроника». Для каждого:
    SR 2009 (перепись) -> SR 2056 (прогноз) и год, в котором район проходит
    отметку 1,0 (если проходит до 2056-го). Всё считается из pension.json,
    порядок - строго по SR 2056, без ручного отбора «самых depressive»."""
    global _CHRON_CACHE
    if _CHRON_CACHE is not None:
        return _CHRON_CACHE
    rows = []
    for tid, terr in pension["territories"].items():
        s = terr["sr"]["as_is"][SCENARIO]
        yr = None
        for i in range(len(TERRITORY_YEARS) - 1):
            a, b = s[i], s[i + 1]
            if a >= 1.0 > b:
                kk = (a - 1.0) / (a - b)
                yr = TERRITORY_YEARS[i] + kk * (TERRITORY_YEARS[i + 1]
                                                - TERRITORY_YEARS[i])
                break
        rows.append({"id": tid, "name": terr["name"].replace(" район", "")
                                                    .replace(" раён", ""),
                     "sr09": s[0], "sr56": s[-1], "cross": yr})
    rows.sort(key=lambda r: r["sr56"])
    _CHRON_CACHE = rows[:CHRON_N]
    return _CHRON_CACHE


def precompute_chron_pixels(feats: list[dict]) -> None:
    if feats and "chron_rings" in feats[0]:
        return
    minx = miny = 1e18
    maxx = maxy = -1e18
    for f in feats:
        for ring in f["rings"]:
            for lon, lat in ring:
                minx, maxx = min(minx, lon), max(maxx, lon)
                miny, maxy = min(miny, lat), max(maxy, lat)
    proj = make_projector((minx, miny, maxx, maxy), *CHRON_BOX)
    for f in feats:
        f["chron_rings"] = [[proj(lon, lat) for lon, lat in ring]
                            for ring in f["rings"]]


def draw_chronicle(img: Image.Image, d: ImageDraw.ImageDraw, T: dict,
                   pension: dict, feats: list[dict], tl: float) -> None:
    """Сцена «хроника»: страна гаснет в серый, десять районов загораются по
    очереди своим цветом со шкалы карты, внизу синхронно набирается список
    с числами и годом перехода."""
    rows = chronicle_rows(pension)
    precompute_chron_pixels(feats)
    step, first = 0.42, 0.35
    lit = max(0, min(CHRON_N, int((tl - first) / step) + 1))
    lit_ids = {r["id"] for r in rows[:lit]}
    colors = {r["id"]: sr_color(r["sr56"]) for r in rows}

    tracked_text(d, (W / 2, 46), T["brand"], 34, AMBER, track=0.22)
    wrap_center(d, 100, T["chronTitle"], 40, INK, maxw=W - 120)

    for f in feats:
        col = colors[f["id"]] if f["id"] in lit_ids else CHRON_DIM
        for ring in f["chron_rings"]:
            d.polygon(ring, fill=col, outline=BORDER)
    for f in feats:
        if f["id"] in lit_ids:
            for ring in f["chron_rings"]:
                d.line(ring + [ring[0]], fill=HIGHLIGHT, width=3)

    y0, rh = 920, 82
    for i, r in enumerate(rows[:lit]):
        y = y0 + i * rh
        fresh = tl - (first + i * step) < 0.35
        col = HIGHLIGHT if fresh else INK
        d.rectangle([70, y + 14, 92, y + 50], fill=colors[r["id"]])
        d.text((116, y + 8), r["name"], font=font(36), fill=col, anchor="la")
        d.text((700, y + 12), f"{ru_num(r['sr09'])} → {ru_num(r['sr56'])}",
               font=font(34), fill=DIM, anchor="ra")
        tail = (T["chronCross"].format(year=int(round(r["cross"])))
                if r["cross"] else T["chronNoCross"])
        d.text((1010, y + 12), tail, font=font(30),
               fill=AMBER if r["cross"] else DIM, anchor="ra")
    if lit >= CHRON_N and tl > first + CHRON_N * step + 0.3:
        d.text((W / 2, 1790), T["chronFoot"], font=font(30), fill=DIM,
               anchor="ma")


_EVENTS_CACHE: list | None = None


def crossing_events(pension: dict) -> list[tuple[float, str]]:
    """Районы, где к 2056 году работающих меньше, чем пожилых (SR < 1,0),
    и год, в котором каждый из них проходит эту отметку. Год считается
    линейной интерполяцией между известными точками ряда - тем же приёмом,
    что crossing_year() в etl/pension.py и sr_interp() выше.

    Список сознательно строится по условию «SR(2056) < 1,0», а не «когда-либо
    пересёк 1,0»: ровно так посчитаны опубликованные «5 из 118» в отчёте
    INF-13 и на странице. Мостовский район пересекает отметку в 2050-м, но к
    2056-му возвращается к 1,00 - в опубликованную пятёрку он не входит и в
    ролике не показывается."""
    global _EVENTS_CACHE
    if _EVENTS_CACHE is not None:
        return _EVENTS_CACHE
    out = []
    for terr in pension["territories"].values():
        s = terr["sr"]["as_is"][SCENARIO]
        if s[-1] >= 1.0:
            continue
        yr = None
        for i in range(len(TERRITORY_YEARS) - 1):
            a, b = s[i], s[i + 1]
            if a >= 1.0 > b:
                kk = (a - 1.0) / (a - b)
                yr = TERRITORY_YEARS[i] + kk * (TERRITORY_YEARS[i + 1]
                                                - TERRITORY_YEARS[i])
                break
        if yr is not None:
            out.append((yr, terr["name"].replace(" район", "")
                                        .replace(" раён", "")))
    out.sort()
    _EVENTS_CACHE = out
    return out


def draw_events_panel(d: ImageDraw.ImageDraw, T: dict,
                      events: list[tuple[float, str]], year: float) -> None:
    """Панель «районы, где работающих меньше, чем пожилых»: наполняется
    прямо во время пролёта карты по годам - зритель видит не итог, а момент,
    когда каждый район проходит отметку. Только что появившаяся строка
    подсвечивается янтарным."""
    shown = [e for e in events if year >= e[0]]
    if not shown:
        return
    x0, y0, x1 = 588, 452, 1052
    y1 = y0 + 52 + 34 * len(shown)
    d.rectangle([x0, y0, x1, y1], fill=(14, 14, 13), outline=AMBER, width=2)
    d.text(((x0 + x1) / 2, y0 + 12), T["eventsTitle"], font=font(23),
           fill=AMBER, anchor="ma")
    for i, (yr, name) in enumerate(shown):
        fresh = year - yr < 2.5
        d.text((x0 + 22, y0 + 52 + i * 34), f"{int(round(yr))}  ·  {name}",
               font=font(27), fill=AMBER if fresh else INK, anchor="la")


def draw_wordmark(d: ImageDraw.ImageDraw, T: dict, y: int = 96,
                  sz: int = 62, kicker: bool = True) -> None:
    tracked_text(d, (W / 2, y), T["brand"], sz, AMBER, track=0.22, stroke=1)
    if kicker:
        d.text((W / 2, y + sz + 22), T["brandTag"], font=font(28), fill=INK,
               anchor="ma")
        if T.get("brandKicker"):
            d.text((W / 2, y + sz + 62), T["brandKicker"], font=font(24),
                   fill=DIM, anchor="ma")


# ---------------------------------------------------------------- отрисовка ---

def draw_map(img: Image.Image, feats: list[dict], srs: dict[str, float]) -> None:
    d = ImageDraw.Draw(img)
    for f in feats:
        color = sr_color(srs.get(f["id"])) if f["in_territories"] else NODATA
        for ring in f["pixel_rings"]:
            d.polygon(ring, fill=color, outline=BORDER)


def draw_highlight(img: Image.Image, feats_by_id: dict[str, dict], gid: str,
                   label: str | None = None) -> None:
    """Обводка района. v1.4: обводка вдвое толще, с тёмным подбоем и
    выноской-подписью - тонкий контур в 5 px на телефоне не читался
    (замечание автора: «Кореличский не показан»)."""
    d = ImageDraw.Draw(img)
    f = feats_by_id.get(gid)
    if not f:
        return
    for ring in f["pixel_rings"]:
        d.line(ring + [ring[0]], fill=BG, width=14)
    for ring in f["pixel_rings"]:
        d.line(ring + [ring[0]], fill=HIGHLIGHT, width=8)
    if not label:
        return
    xs = [p[0] for r in f["pixel_rings"] for p in r]
    ys = [p[1] for r in f["pixel_rings"] for p in r]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    lx, ly = cx, min(ys) - 92          # подпись над районом
    fnt = font(34)
    tw = d.textlength(label, font=fnt)
    lx = min(max(lx, tw / 2 + 30), W - tw / 2 - 30)
    d.line([(cx, min(ys) - 6), (lx, ly + 44)], fill=HIGHLIGHT, width=4)
    d.rectangle([lx - tw / 2 - 16, ly, lx + tw / 2 + 16, ly + 48],
                fill=(26, 20, 12), outline=HIGHLIGHT, width=3)
    d.text((lx, ly + 6), label, font=fnt, fill=HIGHLIGHT, anchor="ma")


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

    if scene_id == "intro":
        # Титульная карточка: логотип -> заголовок -> пояснение -> контур
        # страны. Всё, кроме контура, стоит в кадре с нулевой секунды -
        # зритель не должен ждать проявления, чтобы понять, что смотрит.
        draw_wordmark(d, T)
        d.line([(W / 2 - 120, 268), (W / 2 + 120, 268)], fill=AMBER, width=3)

        y = wrap_center(d, 350, T["introHeadline"], 78, INK, maxw=W - 120,
                        lh=1.18)
        rule = min(1.0, max(0.0, (t - 0.25) / 0.9)) * 520
        if rule > 2:
            d.line([(W / 2 - rule / 2, y + 26), (W / 2 + rule / 2, y + 26)],
                   fill=AMBER, width=7)
        wrap_center(d, y + 80, T["introSub"], 36, DIM, maxw=W - 140, lh=1.4)

        # Контур виден уже на нулевом кадре (это обложка ролика в ленте),
        # доводка до полной непрозрачности - за 0,6 с.
        paste_country(img, feats, INTRO_MAP_BOX,
                      alpha=min(1.0, 0.6 + t / 0.6 * 0.4))
        d.text((W / 2, 1620), T["introMeta"], font=font(27), fill=DIM,
               anchor="ma")
        fit_text(d, (W / 2, 1700), T["ctaUrl"], 36, AMBER)
        d.line([(0, H - 6), (W * t / duration, H - 6)], fill=AMBER, width=6)
        return img

    if scene_id == "hook":
        # v1.2: вместо двух чисел на чёрном - пиктограммы «работающие на
        # одного пожилого» и лента 118 районов. Задача сцены - показать,
        # что 1,4 работающего это СРЕДНЕЕ, а в пяти районах работающих
        # будет меньше, чем пожилых. Все числа и название худшего района
        # берутся из pension.json, руками не вписаны.
        tl = t - seg["t"][0]
        tracked_text(d, (W / 2, 60), T["brand"], 38, AMBER, track=0.22)
        wrap_center(d, 140, T["hookLine"], 40, INK, maxw=W - 120)

        srs56 = {tid: sr_interp(terr["sr"]["as_is"][SCENARIO], 2056)
                 for tid, terr in pension["territories"].items()}
        worst_id = min(srs56, key=lambda k: srs56[k])
        worst_v = srs56[worst_id]
        worst_name = pension["territories"][worst_id]["name"]
        below10 = sum(1 for v in srs56.values() if v < 1.0)
        v2009 = nat_sr[nat_years.index(2009)]
        v2056 = nat_sr[-1]

        rows = [(0.10, T["scaleRow1"], v2009),
                (0.90, T["scaleRow2"], v2056),
                (1.70, T["scaleRow3"].format(name=worst_name), worst_v)]
        for i, (start, label, val) in enumerate(rows):
            if tl < start:
                continue
            grow = min(1.0, (tl - start) / 0.55)
            draw_ratio_row(img, d, 300 + i * 250, label, val, val * grow)

        if tl >= 2.60:
            vals = sorted(srs56.values())
            shown = int(len(vals) * min(1.0, (tl - 2.60) / 0.6))
            draw_district_dots(img, d, 1150, vals, shown)
            d.text((W / 2, 1450), T["scaleDots"], font=font(26), fill=DIM,
                   anchor="ma")
        if tl >= 3.20:
            ev = crossing_events(pension)
            wrap_center(d, 1545,
                        T["scaleWorst"].format(
                            below10=below10,
                            firstYear=int(round(ev[0][0])) if ev else "—"),
                        42, AMBER, maxw=W - 120)

        d.line([(0, H - 6), (W * t / duration, H - 6)], fill=AMBER, width=6)
        return img

    if scene_id == "chronicle":
        draw_chronicle(img, d, T, pension, feats, t - seg["t"][0])
        d.line([(0, H - 6), (W * t / duration, H - 6)], fill=AMBER, width=6)
        return img

    if scene_id == "finale":
        # Зеркало интро: тот же логотип, тот же контур страны - зритель
        # закрывает ролик тем же кадром, каким открыл. Вывод считается из
        # pension.json, а не вписан в сцену (тот же принцип, что у callouts).
        draw_wordmark(d, T)
        d.line([(W / 2 - 120, 268), (W / 2 + 120, 268)], fill=AMBER, width=3)

        srs56 = {tid: sr_interp(terr["sr"]["as_is"][SCENARIO], 2056)
                 for tid, terr in pension["territories"].items()}
        lead = T["finaleLead"].format(year=2056,
                                      below15=sum(1 for v in srs56.values()
                                                  if v < 1.5))
        y = wrap_center(d, 340, lead, 46, AMBER, maxw=W - 120, lh=1.3)

        paste_country(img, feats, FINALE_MAP_BOX,
                      alpha=min(1.0, 0.3 + (t - seg["t"][0]) / 0.8 * 0.7))

        bx0, bx1 = 90, W - 90
        by0 = 1280
        d.rectangle([bx0, by0, bx1, by0 + 258], outline=AMBER, width=3)
        d.text((W / 2, by0 + 34), T["disclaimerTitle"], font=font(30),
               fill=AMBER, anchor="ma")
        wrap_center(d, by0 + 92, T["disclaimer"], 32, INK, maxw=bx1 - bx0 - 80)

        d.text((W / 2, 1650), T["finaleCtaLabel"], font=font(30), fill=INK,
               anchor="ma")
        fit_text(d, (W / 2, 1700), T["ctaUrl"], 42, AMBER)
        d.text((W / 2, 1800), T["sourceNote"], font=font(24), fill=DIM,
               anchor="ma")
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
    draw_events_panel(d, T, crossing_events(pension), year)

    for c in scene["callouts"][lang]:
        if not (c["t"][0] <= t < c["t"][1]):
            continue
        if "highlight" in c:
            hid = c["highlight"]
            hname = pension["territories"].get(hid, {}).get("name", "")
            draw_highlight(img, feats_by_id, hid, hname)
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
