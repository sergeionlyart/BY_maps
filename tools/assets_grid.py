#!/usr/bin/env python3
"""Библиотека иллюстраций INF-15 «Полотно»: один тезис — один кадр.

Каждый ассет собирается из данных проекта (web/public/data/grid.json,
grid_story.json, grid_frames/*.webp) — ни одно число не вписано руками.
Ассеты используются двумя способами: как иллюстрации к статье и как кадры
итогового ролика (порядок и хронометраж задаёт отдельный манифест).

Композиция — полноэкранная 16:9 (1920x1080): визуал слева на всю высоту
кадра, тезис и график справа. Это НЕ вертикальная вёрстка в центре кадра
(так была собрана версия v1 — она читалась как вертикальное видео с
полями).

Запуск:
    python tools/assets_grid.py --all
    python tools/assets_grid.py --id rule500
    python tools/assets_grid.py --all --motion     # + анимированные версии
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "web" / "public" / "data"
DEFAULT_FONT = ROOT / "data" / "raw" / "nightlights" / "fonts" / "DejaVuSans.ttf"
DEFAULT_OUT = ROOT / "build" / "assets" / "grid"

W, H = 1920, 1080
MARGIN = 72

# Левая панель (визуал) и правая колонка (тезис + график)
LP = (MARGIN, 150, MARGIN + 960, 1000)
RC_X0, RC_X1 = 1096, W - MARGIN
RC_W = RC_X1 - RC_X0

# Палитра проекта (globals.css + tools/reel_grid_scene.json)
BG = (10, 11, 24)
PANEL = (16, 18, 34)
LINE = (46, 52, 70)
INK = (250, 253, 250)
DIM = (156, 170, 182)
MUTE = (110, 122, 136)
ACCENT = (60, 165, 175)
POS = (108, 196, 168)
NEG = (224, 122, 104)
MODEL = (196, 168, 108)


class Ctx:
    def __init__(self, data: Path, font: Path):
        self.dir = data
        self.geo = data / "geo"
        self.frames = data / "grid_frames"
        self.grid = json.loads((data / "grid.json").read_text())
        self.story = json.loads((data / "grid_story.json").read_text())
        self.meta = json.loads((self.frames / "meta.json").read_text())
        self._f: dict[int, ImageFont.FreeTypeFont] = {}
        self._font_path = font
        self._json: dict[str, dict] = {}

    def load(self, rel: str) -> dict:
        if rel not in self._json:
            self._json[rel] = json.loads((self.dir / rel).read_text())
        return self._json[rel]

    def font(self, sz: int) -> ImageFont.FreeTypeFont:
        if sz not in self._f:
            self._f[sz] = ImageFont.truetype(str(self._font_path), sz)
        return self._f[sz]

    def frame(self, name: str) -> Image.Image:
        return Image.open(self.frames / name).convert("RGB")

    def lonlat_px(self, lon: float, lat: float) -> tuple[float, float]:
        w0, s0, e0, n0 = self.meta["bounds_lonlat"]
        return ((lon - w0) / (e0 - w0) * self.meta["width"],
                (n0 - lat) / (n0 - s0) * self.meta["height"])

    def crop_belarus(self, img: Image.Image) -> tuple[Image.Image, tuple[int, int]]:
        """Кадр GHS-POP шире страны (границы тайлов). Обрезаем до реального
        охвата Беларуси, иначе карта тонет в пустых полях."""
        x0, _ = self.lonlat_px(22.8, 56.3)
        x1, _ = self.lonlat_px(33.0, 51.1)
        box = (int(x0), 0, int(x1), img.size[1])
        return img.crop(box), (box[0], box[1])


# --- примитивы --------------------------------------------------------------
def txt(d, xy, s, f, fill=INK, anchor="la"):
    d.text(xy, s, font=f, fill=fill, anchor=anchor)


def wrap(d, s, f, max_w):
    out, cur = [], ""
    for w_ in s.split():
        t = (cur + " " + w_).strip()
        if d.textlength(t, font=f) <= max_w or not cur:
            cur = t
        else:
            out.append(cur)
            cur = w_
    if cur:
        out.append(cur)
    return out


def para(d, c: Ctx, x, y, s, size, fill=INK, max_w=RC_W, lead=1.24):
    f = c.font(size)
    for line in wrap(d, s, f, max_w):
        txt(d, (x, y), line, f, fill)
        y += int(size * lead)
    return y


def chrome(canvas: Image.Image, c: Ctx, badge: str, badge_col=ACCENT,
           source: str = "") -> ImageDraw.ImageDraw:
    d = ImageDraw.Draw(canvas)
    txt(d, (MARGIN, 58), "BY MAPS · ПОЛОТНО · INF-15", c.font(22), ACCENT)
    if badge:
        f = c.font(20)
        tw = int(d.textlength(badge, font=f))
        d.rounded_rectangle([W - MARGIN - tw - 30, 50, W - MARGIN, 90], 8,
                            outline=badge_col, width=2)
        txt(d, (W - MARGIN - tw // 2 - 15, 70), badge, f, badge_col, anchor="mm")
    d.line([(MARGIN, 108), (W - MARGIN, 108)], fill=LINE, width=1)
    if source:
        d.line([(MARGIN, 1006), (W - MARGIN, 1006)], fill=LINE, width=1)
        txt(d, (MARGIN, 1024), source, c.font(19), MUTE)
    return d


def map_panel(canvas: Image.Image, c: Ctx, img: Image.Image, box=LP,
              caption: str | None = None, frame_col=LINE, crop: bool = True):
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([x0, y0, x1, y1], 14, fill=PANEL, outline=frame_col, width=2)
    cropped = c.crop_belarus(img)[0] if crop else img
    inner_w, inner_h = x1 - x0 - 28, y1 - y0 - 28 - (44 if caption else 0)
    s = min(inner_w / cropped.size[0], inner_h / cropped.size[1])
    m = cropped.resize((int(cropped.size[0] * s), int(cropped.size[1] * s)), Image.LANCZOS)
    mx = x0 + (x1 - x0 - m.size[0]) // 2
    my = y0 + 14
    canvas.paste(m, (mx, my))
    if caption:
        d = ImageDraw.Draw(canvas)
        txt(d, ((x0 + x1) // 2, y1 - 30), caption, c.font(22), DIM, anchor="mm")
    return (mx, my, s)


def bars(d, c: Ctx, x, y0, rows, w=RC_W, row_h=74, label_w=300) -> int:
    """Диверг. столбики от общего нуля: убыль — тёплый, рост — холодный,
    нейтральная середина = сама ось. Значения подписаны у концов (их мало),
    подписи рядов — текстовым токеном, не цветом ряда."""
    vmax = max(abs(v) for _, v in rows)
    y = y0
    zero = x + label_w + 150
    span_r = x + w - zero - 130
    span_l = zero - (x + label_w) - 40
    has_neg = any(v < 0 for _, v in rows)
    has_pos = any(v >= 0 for _, v in rows)
    span = min(span_r, span_l) if (has_neg and has_pos) else (span_l if has_neg else span_r)
    for label, v in rows:
        txt(d, (x, y + 16), label, c.font(24), DIM)
        bw = max(3, int(abs(v) / vmax * span))
        col = POS if v >= 0 else NEG
        if v >= 0:
            d.rounded_rectangle([zero + 2, y + 8, zero + bw, y + 48], 4, fill=col)
            txt(d, (zero + bw + 16, y + 12), f"+{v:.1f}%".replace(".", ","), c.font(28), INK)
        else:
            d.rounded_rectangle([zero - bw, y + 8, zero - 2, y + 48], 4, fill=col)
            txt(d, (zero + 16, y + 12), f"−{abs(v):.1f}%".replace(".", ","), c.font(28), INK)
        y += row_h
    d.line([(zero, y0 + 4), (zero, y - 22)], fill=(78, 86, 102), width=2)
    return y


def hero(d, c: Ctx, x, y, value: str, label: str, col=INK) -> int:
    txt(d, (x, y), value, c.font(96), col)
    y += 118
    return para(d, c, x, y, label, 24, DIM)


def fmt_int(n) -> str:
    return f"{int(round(n)):,}".replace(",", " ")


def pc(v) -> str:
    return f"{v:.1f}".replace(".", ",") + "%"


# --- ассеты -----------------------------------------------------------------
SRC = ("GHS-POP R2023A (JRC, Еврокомиссия), 1975–2020, приведено к рядам Белстата · "
       "клетка 1 км · by-population-maps.vercel.app/research/grid")
SRC_ROAD = ("GHS-POP R2023A + OpenStreetMap (магистрали и гидрография, 2026) · "
            "by-population-maps.vercel.app/research/grid")


def a_rule500(c: Ctx) -> Image.Image:
    b = {(x["lo"], x["hi"]): x for x in c.story["c004_density_bands"]["bands"]}
    top = b[(2000, None)]
    canvas = Image.new("RGB", (W, H), BG)
    d = chrome(canvas, c, "ДАННЫЕ 1975–2020", ACCENT, SRC)
    map_panel(canvas, c, c.frame("story_rule500_1975.webp"),
              caption="1975 год · синим — где было меньше 500 чел/км², оранжевым — 500 и больше")
    d = ImageDraw.Draw(canvas)
    y = 172
    txt(d, (RC_X0, y), "НАХОДКА 1", c.font(24), ACCENT)
    y = para(d, c, RC_X0, y + 44, "Правило пятисот", 54) + 18
    y = para(d, c, RC_X0, y,
             "Изменение населения 1975 → 2020 в зависимости от того, сколько людей "
             "было в квадрате в 1975 году.", 25, DIM) + 34
    y = bars(d, c, RC_X0, y,
             [("5–25 чел/км²", b[(5, 25)]["change_pct"]),
              ("25–100", b[(25, 100)]["change_pct"]),
              ("100–500", b[(100, 500)]["change_pct"]),
              ("500–2 000", b[(500, 2000)]["change_pct"]),
              ("больше 2 000", top["change_pct"])]) + 16
    para(d, c, RC_X0, y,
         f"Граница проходит по 500 человек на км² — плотности обычной деревенской "
         f"улицы. Сегодня {fmt_int(top['n_cells'])} квадратов, меньше половины процента "
         f"страны, держат {pc(top['share_2020_pct'])} населения.", 25, INK)
    return canvas


def a_matrix(c: Ctx) -> Image.Image:
    m = {g["id"]: g for g in c.story["c006_river_road_matrix"]["groups"]}
    riv = c.story["c007_river_distance"]
    canvas = Image.new("RGB", (W, H), BG)
    d = chrome(canvas, c, "ДАННЫЕ 1975–2020", ACCENT, SRC_ROAD)
    map_panel(canvas, c, c.frame("story_matrix_2020.webp"),
              caption="зелёное — река и дорога рядом · синее — река без дороги")
    d = ImageDraw.Draw(canvas)
    y = 172
    txt(d, (RC_X0, y), "НАХОДКА 2", c.font(24), ACCENT)
    y = para(d, c, RC_X0, y + 44, "Держит не вода и не асфальт, а пересечение", 54) + 18
    y = para(d, c, RC_X0, y,
             f"В пяти километрах от реки живёт {pc(riv['share_near_5km_pct']['2020'])} "
             f"страны — «далеко от воды» в Беларуси почти не бывает. Значит, разницу "
             f"объясняет не вода.", 25, DIM) + 34
    y = bars(d, c, RC_X0, y,
             [("река + дорога", m["both"]["change_pct"]),
              ("река без дороги", m["river_only"]["change_pct"]),
              ("ни реки, ни дороги", m["neither"]["change_pct"])],
             label_w=340) + 16
    para(d, c, RC_X0, y,
         f"Группа «река плюс дорога» — {pc(m['both']['share_2020_pct'])} населения "
         f"на {pc(m['both']['area_share_pct'])} территории. Единственная, которая за "
         f"45 лет выросла.", 25, INK)
    return canvas


def a_voids(c: Ctx) -> Image.Image:
    r = c.story["raions"]
    by = {x["name_ru"]: x for x in r["shrunk_most"]}
    canvas = Image.new("RGB", (W, H), BG)
    d = chrome(canvas, c, "ДАННЫЕ 1975–2020", ACCENT, SRC)
    mx, my, s = map_panel(canvas, c, c.frame("pop_2020.webp"),
                          caption="2020 год")
    d = ImageDraw.Draw(canvas)
    ox, _ = c.lonlat_px(22.8, 56.3)
    regions = [("1", 29.0, 51.3, 31.7, 53.1), ("2", 23.6, 52.5, 26.3, 54.4),
               ("3", 26.0, 51.4, 30.2, 52.6)]
    for label, w0, s0, e0, n0 in regions:
        px0, py0 = c.lonlat_px(w0, n0)
        px1, py1 = c.lonlat_px(e0, s0)
        rect = [mx + (px0 - ox) * s, my + py0 * s, mx + (px1 - ox) * s, my + py1 * s]
        d.rounded_rectangle(rect, 8, outline=NEG, width=3)
        d.ellipse([rect[0] - 16, rect[1] - 16, rect[0] + 16, rect[1] + 16], fill=NEG)
        txt(d, (rect[0], rect[1]), label, c.font(22), (20, 12, 12), anchor="mm")
    y = 172
    txt(d, (RC_X0, y), "ГДЕ ПУСТЕЕТ", c.font(24), ACCENT)
    y = para(d, c, RC_X0, y + 44, "Три разные пустоты", 54) + 18
    y = para(d, c, RC_X0, y,
             f"Из {r['n_raions_total']} районов {r['n_raions_shrunk']} потеряли "
             f"население, {r['n_raions_shrunk_40pct_or_more']} из них — больше сорока "
             f"процентов. Причины у них разные.", 25, DIM) + 40
    items = [
        ("1", "Чернобыльский юго-восток", NEG,
         f"Брагинский {pc(abs(by['Брагинский район']['change_pct']))} · "
         f"Наровлянский {pc(abs(by['Наровлянский район']['change_pct']))} · "
         f"Хойникский {pc(abs(by['Хойникский район']['change_pct']))} — у этой пустоты есть дата"),
        ("2", "Запад и северо-запад", MODEL,
         "Ивьевский 59,1% · Зельвенский 58,6% · Щучинский 58,2% — здесь не было аварии, "
         "люди уезжали по одному два поколения"),
        ("3", "Полесские болота", ACCENT,
         "Никогда не были густо населены: убыль добила то, чего и так было мало"),
    ]
    for n, title, col, body in items:
        d.ellipse([RC_X0, y + 2, RC_X0 + 34, y + 36], fill=col)
        txt(d, (RC_X0 + 17, y + 19), n, c.font(22), (16, 14, 18), anchor="mm")
        txt(d, (RC_X0 + 50, y + 2), title, c.font(30), INK)
        y = para(d, c, RC_X0 + 50, y + 44, body, 23, DIM, max_w=RC_W - 50) + 26
    return canvas


def a_islands(c: Ctx) -> Image.Image:
    sc = c.grid["national"]["settlement_components"]
    canvas = Image.new("RGB", (W, H), BG)
    d = chrome(canvas, c, "ДАННЫЕ + МОДЕЛЬ", MODEL, SRC)
    half_w = (LP[2] - LP[0] - 16) // 2
    panel_h = int((half_w - 28) / 1.198) + 72      # пропорция обрезанного кадра
    top = LP[1] + ((LP[3] - LP[1]) - panel_h) // 2
    for i, (name, key, label, col) in enumerate([
            ("story_islands_1975.webp", "1975", "1975 — наблюдение", LINE),
            ("story_islands_2050_base_A.webp", "2050:base:A", "2050 — модель", MODEL)]):
        x0 = LP[0] + i * (half_w + 16)
        map_panel(canvas, c, c.frame(name), box=(x0, top, x0 + half_w, top + panel_h),
                  caption=label, frame_col=col)
    d = ImageDraw.Draw(canvas)
    y = 172
    txt(d, (RC_X0, y), "ЧТО ПРОИСХОДИТ С ТКАНЬЮ", c.font(24), ACCENT)
    y = para(d, c, RC_X0, y + 44, "Полотно рвётся на лоскуты", 54) + 24
    y = hero(d, c, RC_X0, y, f"{fmt_int(sc['1975']['n_components'])} → "
             f"{fmt_int(sc['2050:base:A']['n_components'])}",
             "отдельных «островов» расселения — связных пятен, где живут люди. "
             "Островов становится больше: ткань не редеет равномерно, а рвётся.") + 34
    y = para(d, c, RC_X0, y,
             f"Крупнейший остров при этом сжимается: "
             f"{pc(sc['1975']['largest_share_of_area'] * 100)} площади страны в 1975 году, "
             f"{pc(sc['2020']['largest_share_of_area'] * 100)} в 2020-м, "
             f"{pc(sc['2050:base:A']['largest_share_of_area'] * 100)} к 2050-му. "
             f"Людей в нём — почти половина страны.", 25, INK) + 26
    para(d, c, RC_X0, y,
         "Для человека внутри лоскута это расписание автобуса: маршрут через четыре "
         "деревни становится маршрутом через две.", 23, DIM)
    return canvas


def a_nightlights(c: Ctx) -> Image.Image:
    g3 = c.grid["validation"]["g3_nightlights_crosscheck"]
    canvas = Image.new("RGB", (W, H), BG)
    d = chrome(canvas, c, "ПРОВЕРКА НЕ ПРОЙДЕНА", NEG,
               "Источники: официальные ряды Белстата и ночная светимость VIIRS VNL v2.1 "
               "(исследование INF-08), 2012–2020 · by-population-maps.vercel.app/research/grid")
    y = 190
    txt(d, (MARGIN, y), "ЧТО У НАС НЕ СОШЛОСЬ", c.font(24), ACCENT)
    y = para(d, c, MARGIN, y + 46, "Мы проверили карту независимым сенсором — и провалились", 60,
             max_w=W - 2 * MARGIN) + 26
    y = para(d, c, MARGIN, y,
             "Логика была простая: откуда уезжают люди, там должно темнеть. Порог согласия "
             "мы объявили заранее — не меньше 70% районов.", 27, DIM, max_w=1200) + 60

    # bullet-график: факт против заранее объявленного порога
    bx0, bx1 = MARGIN, W - MARGIN
    track_y = y + 40
    d.rounded_rectangle([bx0, track_y, bx1, track_y + 56], 8, fill=(24, 26, 42))
    fill_w = int((bx1 - bx0) * g3["pct_agree"] / 100)
    d.rounded_rectangle([bx0, track_y, bx0 + fill_w, track_y + 56], 8, fill=NEG)
    thr_x = bx0 + int((bx1 - bx0) * g3["threshold_pct"] / 100)
    d.line([(thr_x, track_y - 22), (thr_x, track_y + 78)], fill=INK, width=3)
    txt(d, (thr_x, track_y - 34), f"порог {int(g3['threshold_pct'])}%", c.font(24), INK, anchor="mb")
    txt(d, (bx0 + fill_w + 20, track_y + 12), pc(g3["pct_agree"]), c.font(34), INK)
    txt(d, (bx0, track_y + 92), "согласие направления изменений: население вниз → свет вниз",
        c.font(23), DIM)

    y = track_y + 170
    col_w = (W - 2 * MARGIN - 80) // 3
    cards = [
        (f"{g3['n_agree']} из {g3['n_raions']}", "районов, где официальная численность и "
         "светимость менялись в одну сторону", NEG),
        ("63,9%", "районов, где людей стало меньше, а света больше — самый частый расклад", MODEL),
        ("открытый вопрос", "статус вывода о концентрации населения: не «доказано», "
         "а «пока не подтверждено»", ACCENT),
    ]
    for i, (val, lab, col) in enumerate(cards):
        x = MARGIN + i * (col_w + 40)
        d.rounded_rectangle([x, y, x + col_w, y + 190], 12, fill=PANEL, outline=LINE, width=2)
        f = c.font(46 if len(val) < 12 else 30)
        txt(d, (x + 28, y + 30), val, f, col)
        para(d, c, x + 28, y + 100, lab, 22, DIM, max_w=col_w - 56)
    return canvas


# --- дополнительные примитивы: карты-хороплеты, кропы, линейный график ------
FRAME_W, FRAME_H = 857, 514


def _ramp(stops, t: float):
    t = max(0.0, min(1.0, t))
    n = len(stops) - 1
    i = min(int(t * n), n - 1)
    f = t * n - i
    a, b = stops[i], stops[i + 1]
    return tuple(int(a[k] + (b[k] - a[k]) * f) for k in range(3))


# секвенциальная шкала (один тон, светлее -> темнее) — для величины
SEQ = [(214, 240, 242), (140, 208, 214), (72, 168, 180), (34, 116, 130), (16, 68, 82)]
# дивергентная пара + нейтральная середина — для знака изменения
DIV_NEG = [(160, 58, 44), (206, 96, 78), (234, 158, 142)]
DIV_MID = (58, 62, 78)
DIV_POS = [(150, 214, 190), (92, 186, 156), (46, 140, 116)]


def div_color(v: float, lim: float = 80.0):
    if v is None:
        return (34, 36, 50)
    t = max(-1.0, min(1.0, v / lim))
    if abs(t) < 0.04:
        return DIV_MID
    ramp = DIV_POS if t > 0 else DIV_NEG
    a = abs(t)
    idx = 0 if a < 0.33 else (1 if a < 0.66 else 2)
    return ramp[idx]


def seq_color(v: float, lo: float, hi: float):
    if v is None:
        return (34, 36, 50)
    import math
    t = (math.log(max(v, lo)) - math.log(lo)) / (math.log(hi) - math.log(lo))
    return _ramp(SEQ, t)


def choropleth(c: Ctx, values: dict, color_fn, outline=(14, 16, 28)) -> Image.Image:
    """Хороплет районов в системе координат кадра GHS-POP (857x514), чтобы
    он проходил через тот же crop_belarus и совмещался с растровыми кадрами."""
    img = Image.new("RGB", (FRAME_W, FRAME_H), (8, 9, 20))
    d = ImageDraw.Draw(img)
    geo = c.load("geo/adm2.geojson")
    for ft in geo["features"]:
        tid = ft["properties"]["id"]
        col = color_fn(values.get(tid))
        g = ft["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            pts = [c.lonlat_px(x, y) for x, y in poly[0]]
            if len(pts) > 2:
                d.polygon(pts, fill=col, outline=outline)
    return img


def crop_region(c: Ctx, img: Image.Image, w0, s0, e0, n0) -> Image.Image:
    x0, y0 = c.lonlat_px(w0, n0)
    x1, y1 = c.lonlat_px(e0, s0)
    return img.crop((int(x0), int(y0), int(x1), int(y1)))


def region_panel(canvas: Image.Image, c: Ctx, img: Image.Image, box,
                 caption=None, frame_col=LINE):
    """Как map_panel, но для уже обрезанного фрагмента (без crop_belarus)."""
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([x0, y0, x1, y1], 14, fill=PANEL, outline=frame_col, width=2)
    iw, ih = x1 - x0 - 28, y1 - y0 - 28 - (44 if caption else 0)
    s = min(iw / img.size[0], ih / img.size[1])
    m = img.resize((int(img.size[0] * s), int(img.size[1] * s)), Image.LANCZOS)
    canvas.paste(m, (x0 + (x1 - x0 - m.size[0]) // 2, y0 + 14))
    if caption:
        d = ImageDraw.Draw(canvas)
        txt(d, ((x0 + x1) // 2, y1 - 30), caption, c.font(22), DIM, anchor="mm")


def legend_row(d, c: Ctx, x, y, items, sw=26):
    for label, col in items:
        d.rounded_rectangle([x, y, x + sw, y + sw], 5, fill=col)
        txt(d, (x + sw + 12, y + 2), label, c.font(21), DIM)
        x += sw + 18 + int(d.textlength(label, font=c.font(21))) + 26
    return y + sw + 16


def line_chart(d, c: Ctx, box, xs, ys, threshold=None, thr_label="",
               obs_until=None, y_lo=None, y_hi=None):
    x0, y0, x1, y1 = box
    y_lo = y_lo if y_lo is not None else min(ys) * 0.9
    y_hi = y_hi if y_hi is not None else max(ys) * 1.05
    d.rounded_rectangle([x0, y0, x1, y1], 12, fill=PANEL, outline=LINE, width=2)

    def px(i):
        return x0 + 60 + (x1 - x0 - 90) * (xs[i] - xs[0]) / (xs[-1] - xs[0])

    def py(v):
        return y1 - 46 - (y1 - y0 - 76) * (v - y_lo) / (y_hi - y_lo)

    if threshold is not None:
        ty = py(threshold)
        for xx in range(int(x0) + 60, int(x1) - 30, 14):
            d.line([(xx, ty), (xx + 7, ty)], fill=(120, 132, 148), width=2)
        txt(d, (x0 + 66, ty + 10), thr_label, c.font(20), DIM)
    pts = [(px(i), py(v)) for i, v in enumerate(ys)]
    cut = len(xs) if obs_until is None else sum(1 for x in xs if x <= obs_until)
    d.line(pts[:cut], fill=ACCENT, width=4, joint="curve")
    if cut < len(pts):
        seg = pts[cut - 1:]
        for i in range(len(seg) - 1):
            if i % 2 == 0:
                d.line([seg[i], seg[i + 1]], fill=MODEL, width=4)
    for i, (cx, cy) in enumerate(pts):
        col = ACCENT if i < cut else MODEL
        d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=col)
    for i in (0, len(xs) - 1):
        txt(d, (px(i), y1 - 34), str(xs[i]), c.font(20), MUTE,
            anchor="ma" if i == 0 else "ma")
    txt(d, (px(0), py(ys[0]) - 40), f"{ys[0]:.2f}".replace(".", ","), c.font(24), INK)
    txt(d, (px(len(xs) - 1) - 10, py(ys[-1]) - 44),
        f"{ys[-1]:.2f}".replace(".", ","), c.font(24), MODEL, anchor="ra")


# --- ассеты: экспозиция -----------------------------------------------------
def a_cover(c: Ctx) -> Image.Image:
    r = c.story["raions"]
    canvas = Image.new("RGB", (W, H), BG)
    img, _ = c.crop_belarus(c.frame("pop_2020.webp"))
    s = H / img.size[1]
    m = img.resize((int(img.size[0] * s), H), Image.LANCZOS)
    canvas.paste(m, (W - m.size[0] - 40, 0))
    veil = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vd = ImageDraw.Draw(veil)
    for i in range(0, 1180):
        vd.line([(i, 0), (i, H)], fill=(10, 11, 24, max(0, 255 - int(i * 0.19))))
    canvas.paste(Image.alpha_composite(canvas.convert("RGBA"), veil).convert("RGB"), (0, 0))
    d = ImageDraw.Draw(canvas)
    txt(d, (MARGIN, 58), "BY MAPS · ИССЛЕДОВАНИЕ INF-15", c.font(22), ACCENT)
    y = para(d, c, MARGIN, 300, "Страна не вымирает.", 86, max_w=980)
    y = para(d, c, MARGIN, y + 4, "Она переезжает.", 86, max_w=980) + 40
    y = para(d, c, MARGIN, y,
             "Мы разобрали Беларусь на 207 тысяч квадратов по километру и посмотрели, "
             "что происходило в каждом из них с 1975 года.", 30, DIM, max_w=900) + 46
    txt(d, (MARGIN, y), f"{r['national_change_pct']:+.1f}%".replace(".", ","), c.font(64), POS)
    txt(d, (MARGIN + 300, y), f"{r['n_raions_shrunk']} из {r['n_raions_total']}", c.font(64), NEG)
    txt(d, (MARGIN, y + 82), "население страны\nза 45 лет", c.font(22), DIM)
    txt(d, (MARGIN + 300, y + 82), "районов при этом\nпотеряли людей", c.font(22), DIM)
    txt(d, (MARGIN, H - 56), SRC, c.font(19), MUTE)
    return canvas


def a_paradox(c: Ctx) -> Image.Image:
    r = c.story["raions"]
    canvas = Image.new("RGB", (W, H), BG)
    d = chrome(canvas, c, "ДАННЫЕ 1975–2020", ACCENT, SRC)
    y = 190
    txt(d, (MARGIN, y), "С ЧЕГО ВСЁ НАЧАЛОСЬ", c.font(24), ACCENT)
    y = para(d, c, MARGIN, y + 46, "Два числа, которые не сходятся друг с другом", 60,
             max_w=W - 2 * MARGIN) + 50
    cards = [
        (f"{r['national_pop_1975'] / 1e6:.2f}".replace(".", ",") + " → " +
         f"{r['national_pop_2020'] / 1e6:.2f}".replace(".", ",") + " млн",
         "население Беларуси в 1975 и 2020 годах. За сорок пять лет — "
         f"{r['national_change_pct']:+.1f}%".replace(".", ",") + ". Ничего не произошло.", POS),
        (f"{r['n_raions_shrunk']} из {r['n_raions_total']}",
         f"районов за те же годы потеряли население. "
         f"{r['n_raions_shrunk_40pct_or_more']} из них — больше сорока процентов. "
         "Каждый второй район опустел вдвое.", NEG),
    ]
    cw = (W - 2 * MARGIN - 60) // 2
    for i, (val, lab, col) in enumerate(cards):
        x = MARGIN + i * (cw + 60)
        d.rounded_rectangle([x, y, x + cw, y + 300], 14, fill=PANEL, outline=LINE, width=2)
        f = c.font(72 if len(val) < 16 else 56)
        txt(d, (x + 36, y + 44), val, f, col)
        para(d, c, x + 36, y + 150, lab, 25, DIM, max_w=cw - 72)
    y += 350
    para(d, c, MARGIN, y,
         "Оба верны одновременно. Разгадка в том, что мы привыкли задавать вопрос "
         "«сколько», а надо задавать вопрос «где».", 32, INK, max_w=W - 2 * MARGIN)
    return canvas


def a_grid_vs_raion(c: Ctx) -> Image.Image:
    T = c.grid["territories"]
    ch = {}
    for k, v in T.items():
        s0 = v["pop_grid_sum"].get("1975")
        s1 = v["pop_grid_sum"].get("2020")
        if s0:
            ch[k] = 100 * (s1 - s0) / s0
    canvas = Image.new("RGB", (W, H), BG)
    d = chrome(canvas, c, "ОДНИ И ТЕ ЖЕ ДАННЫЕ", ACCENT, SRC)
    half_w = (LP[2] - LP[0] - 16) // 2
    panel_h = int((half_w - 28) / 1.198) + 72
    top = LP[1] + ((LP[3] - LP[1]) - panel_h) // 2
    region_panel(canvas, c, c.crop_belarus(choropleth(c, ch, lambda v: div_color(v)))[0],
                 (LP[0], top, LP[0] + half_w, top + panel_h),
                 caption="118 районов, каждый одним цветом")
    region_panel(canvas, c, c.crop_belarus(c.frame("pop_2020.webp"))[0],
                 (LP[0] + half_w + 16, top, LP[2], top + panel_h),
                 caption="те же люди по квадратам 1×1 км")
    d = ImageDraw.Draw(canvas)
    y = 172
    txt(d, (RC_X0, y), "ЗАЧЕМ КИЛОМЕТРОВАЯ СЕТКА", c.font(24), ACCENT)
    y = para(d, c, RC_X0, y + 44, "Район одним цветом — это удобно и это лжёт", 50) + 24
    y = para(d, c, RC_X0, y,
             "Внутри одного района может быть город, который растёт, и тридцать деревень, "
             "которые исчезают. На карте районов получится ровное бледное пятно «минус "
             "двенадцать процентов».", 26, DIM) + 30
    y = para(d, c, RC_X0, y,
             "Мы взяли открытый набор Европейской комиссии, где население мира разложено по "
             "квадратам километр на километр, вырезали Беларусь и привели итог по каждому "
             "району к официальной статистике Белстата.", 26, INK) + 34
    y = legend_row(d, c, RC_X0, y,
                   [("сильная убыль", DIV_NEG[0]), ("около нуля", DIV_MID), ("рост", DIV_POS[2])])
    para(d, c, RC_X0, y + 10,
         "Важно: карта отвечает на вопрос «где», но не проверяет ответ на вопрос «сколько» — "
         "итог по району остаётся официальной цифрой.", 23, MUTE)
    return canvas


def a_half598(c: Ctx) -> Image.Image:
    half = c.story["half_population_area_km2"]
    area = c.story["country_area_km2"]
    canvas = Image.new("RGB", (W, H), BG)
    d = chrome(canvas, c, "ДАННЫЕ 1975–2020", ACCENT, SRC)
    # площадная метафора: большой квадрат — страна, маленький — 598 км²
    box = (MARGIN, 190, MARGIN + 810, 1000)
    d.rounded_rectangle(box, 14, fill=PANEL, outline=LINE, width=2)
    side = 700
    bx, by = box[0] + 55, box[1] + 60
    d.rectangle([bx, by, bx + side, by + side], outline=ACCENT, width=2)
    txt(d, (bx + 12, by + 12), f"вся Беларусь · {fmt_int(area)} км² по расчётной сетке",
        c.font(21), DIM)
    import math
    for key, col, lab in (("1975", MUTE, "1975"), ("2020", NEG, "2020"),
                          ("2050:base:A", MODEL, "2050 · модель")):
        k = math.sqrt(half[key] / area) * side
        d.rectangle([bx, by + side - k, bx + k, by + side], fill=col)
    txt(d, (bx + 30, by + side - 44), "598 км²", c.font(24), INK)
    y = 172
    txt(d, (RC_X0, y), "МАСШТАБ КОНЦЕНТРАЦИИ", c.font(24), ACCENT)
    y = para(d, c, RC_X0, y + 44, "Половина страны живёт на 598 км²", 54) + 26
    y = hero(d, c, RC_X0, y, f"{fmt_int(half['1975'])} → {fmt_int(half['2020'])} км²",
             "столько территории вмещало половину всех жителей Беларуси в 1975 и в 2020 годах") + 30
    y = para(d, c, RC_X0, y,
             f"Это {100 * half['2020'] / area:.2f}".replace(".", ",") +
             "% территории страны. К 2050 году по базовому сценарию модель даёт "
             f"{fmt_int(half['2050:base:A'])} км².", 26, INK) + 24
    legend_row(d, c, RC_X0, y, [("1975", MUTE), ("2020", NEG), ("2050 · модель", MODEL)])
    return canvas


# --- ассеты: аргументация ---------------------------------------------------
def a_roads(c: Ctx) -> Image.Image:
    b = c.story["c005_highway_distance"]["bands"]
    canvas = Image.new("RGB", (W, H), BG)
    d = chrome(canvas, c, "ДАННЫЕ 1975–2020", ACCENT, SRC_ROAD)
    base = c.frame("pop_2020.webp").copy()
    hw = c.load("geo/grid_highways.geojson")
    dd = ImageDraw.Draw(base)
    for ft in hw["features"]:
        g = ft["geometry"]
        parts = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
        for part in parts:
            pts = [c.lonlat_px(x, y) for x, y in part]
            if len(pts) > 1:
                dd.line(pts, fill=(232, 168, 96), width=2)
    map_panel(canvas, c, base, caption="2020 год · оранжевым — магистрали")
    d = ImageDraw.Draw(canvas)
    y = 172
    txt(d, (RC_X0, y), "ГИПОТЕЗА 2: ДОРОГИ", c.font(24), ACCENT)
    y = para(d, c, RC_X0, y + 44, "Полоса вдоль асфальта", 54) + 20
    y = para(d, c, RC_X0, y,
             "Берём каждый квадрат, смотрим, насколько он далеко от ближайшей магистрали, "
             "и складываем население по поясам.", 25, DIM) + 34
    y = bars(d, c, RC_X0, y,
             [("до 2 км", b[0]["change_pct"]), ("2–5 км", b[1]["change_pct"]),
              ("5–10 км", b[2]["change_pct"]), ("10–20 км", b[3]["change_pct"])],
             label_w=260) + 18
    para(d, c, RC_X0, y,
         "Резкий градиент в первые десять километров от асфальта, дальше убыль перестаёт "
         "нарастать. Оговорка: карта раскладывает людей по снимкам застройки, а застройка "
         "стоит вдоль дорог — часть связи заложена в методе.", 24, INK)
    return canvas


def a_rivers(c: Ctx) -> Image.Image:
    riv = c.story["c007_river_distance"]
    b = riv["bands"]
    canvas = Image.new("RGB", (W, H), BG)
    d = chrome(canvas, c, "ДАННЫЕ 1975–2020", ACCENT, SRC_ROAD)
    map_panel(canvas, c, c.frame("story_river_buffer.webp"),
              caption="синим — пятикилометровая полоса вдоль рек")
    d = ImageDraw.Draw(canvas)
    y = 172
    txt(d, (RC_X0, y), "ГИПОТЕЗА 1: РЕКИ", c.font(24), ACCENT)
    y = para(d, c, RC_X0, y + 44, "Гипотеза, которую пришлось переписать", 52) + 20
    y = para(d, c, RC_X0, y,
             f"Мы думали: плотность держится вдоль рек. Оказалось, что проверить это в такой "
             f"формулировке нельзя — в пяти километрах от воды живёт "
             f"{pc(riv['share_near_5km_pct']['2020'])} страны.", 25, DIM) + 34
    y = bars(d, c, RC_X0, y,
             [(f"{x['lo']}–{x['hi']} км" if x["hi"] else f"дальше {x['lo']} км",
               x["change_pct"]) for x in b], label_w=260) + 18
    riv_2_5_change = f"{b[1]['change_pct']:+.1f}%".replace(".", ",")
    para(d, c, RC_X0, y,
         f"Больше всего людей по-прежнему живёт у самой кромки воды ({pc(b[0]['share_2020_pct'])} "
         f"страны в первых двух километрах) — это несколько больших городов прямо на реке. А "
         f"пояс 2–5 км, вторая терраса выше паводка, — единственный растущий: {riv_2_5_change}.",
         24, INK)
    return canvas


def a_cities_check(c: Ctx) -> Image.Image:
    ic = c.story["c006_river_road_matrix"]["independent_check"]
    cities = c.story["c007_river_distance"]["cities"]
    canvas = Image.new("RGB", (W, H), BG)
    d = chrome(canvas, c, "НЕЗАВИСИМАЯ ПРОВЕРКА", POS,
               "Официальные численности городов и посёлков, переписи 1989 и 2019 · "
               "by-population-maps.vercel.app/research/grid")
    base = choropleth(c, {}, lambda v: (26, 28, 42))
    dd = ImageDraw.Draw(base)
    for ct in cities:
        x, y_ = c.lonlat_px(ct["lon"], ct["lat"])
        col = POS if ct["group"] == "both" else MODEL
        dd.ellipse([x - 7, y_ - 7, x + 7, y_ + 7], fill=col, outline=(10, 12, 24))
    map_panel(canvas, c, base, caption="зелёным — города на пересечении реки и дороги")
    d = ImageDraw.Draw(canvas)
    y = 172
    txt(d, (RC_X0, y), "ПРОВЕРИЛИ СЕБЯ", c.font(24), ACCENT)
    y = para(d, c, RC_X0, y + 44,
             "Повторили расчёт на источнике, не связанном со спутником", 46) + 24
    y = para(d, c, RC_X0, y,
             f"{ic['n_cities_total']} городов и городских посёлков по переписям "
             f"{ic['years'][0]} и {ic['years'][1]} годов. {ic['n_both']} из них попали в "
             f"группу «река плюс дорога».", 25, DIM) + 36
    for lab, val, col in (("на пересечении", ic["both_median_change_pct"], POS),
                          (f"остальные {ic['n_rest']} города", ic["rest_median_change_pct"], NEG)):
        txt(d, (RC_X0, y), f"{val:+.1f}%".replace(".", ","), c.font(64), col)
        txt(d, (RC_X0 + 300, y + 22), f"медиана изменения\n{lab}", c.font(23), DIM)
        y += 108
    y += 12
    p_str = f"{ic['p_value']:.2f}".replace(".", ",")
    thr_str = f"{ic['p_threshold']}".replace(".", ",")
    para(d, c, RC_X0, y,
         f"Направление подтвердилось (p = {p_str} при пороге {thr_str}), но группа сравнения — "
         f"всего {ic['n_rest']} города из 197. Поэтому мы говорим «наблюдение», а не «закон».",
         24, INK)
    return canvas


def a_moved(c: Ctx) -> Image.Image:
    r = c.story["raions"]
    grew = {x["name_ru"]: x for x in r["grew_most"]}
    canvas = Image.new("RGB", (W, H), BG)
    d = chrome(canvas, c, "ДАННЫЕ 1975–2020", ACCENT, SRC)
    half_w = (LP[2] - LP[0] - 16) // 2
    reg = (26.4, 53.2, 28.7, 54.7)
    a75 = crop_region(c, c.frame("pop_1975.webp"), *reg)
    a20 = crop_region(c, c.frame("pop_2020.webp"), *reg)
    panel_h = int((half_w - 28) / (a75.size[0] / a75.size[1])) + 72
    top = LP[1] + ((LP[3] - LP[1]) - panel_h) // 2
    region_panel(canvas, c, a75, (LP[0], top, LP[0] + half_w, top + panel_h),
                 caption="Минская агломерация, 1975")
    region_panel(canvas, c, a20, (LP[0] + half_w + 16, top, LP[2], top + panel_h),
                 caption="она же, 2020")
    d = ImageDraw.Draw(canvas)
    y = 172
    txt(d, (RC_X0, y), "КУДА УЕХАЛИ", c.font(24), ACCENT)
    y = para(d, c, RC_X0, y + 44, "Страна не уменьшилась — она переехала", 52) + 26
    y = bars(d, c, RC_X0, y,
             [("Брестский район", grew["Брестский район"]["change_pct"]),
              ("Минский район", grew["Минский район"]["change_pct"]),
              ("Гродненский район", grew["Гродненский район"]["change_pct"]),
              ("Смолевичский район", grew["Смолевичский район"]["change_pct"])],
             label_w=380) + 20
    para(d, c, RC_X0, y,
         "Пока 99 районов теряли людей, двадцать других росли — и именно в них сегодня "
         "живут две трети страны. Изменилось не сколько. Изменилось где.", 26, INK)
    return canvas


# --- ассеты: следствия ------------------------------------------------------
def a_network(c: Ctx) -> Image.Image:
    T = c.grid["territories"]
    vals = {}
    for k, v in T.items():
        n = (v.get("network_per_capita") or {}).get("road_km_per_1000")
        if n:
            vals[k] = n
    c3 = c.grid["validation"]["c3_correlation"]
    g6 = c.grid["validation"]["g6_network"]
    # ρ считается по 118 районам без г. Минска (BY-HM) - у него отдельный
    # адм. статус и на порядок меньше нагрузка на сеть, см. docs/notes/
    # grid_network_findings.md §3-4. Разброс ниже поэтому тоже без Минска,
    # иначе диапазон и коэффициент относятся к разным выборкам.
    raion_vals = {k: v for k, v in vals.items() if k != "BY-HM"}
    lo_v, hi_v = min(raion_vals.values()), max(raion_vals.values())
    ratio = int(hi_v / lo_v)
    canvas = Image.new("RGB", (W, H), BG)
    d = chrome(canvas, c, "СНИМОК 2026", ACCENT, SRC_ROAD)
    map_panel(canvas, c, choropleth(c, vals, lambda v: seq_color(v, 1.0, 60.0)),
              caption="км дорог на 1000 жителей района · темнее — больше")
    d = ImageDraw.Draw(canvas)
    y = 172
    txt(d, (RC_X0, y), "ЧТО ОСТАЁТСЯ ПОСЛЕ ЛЮДЕЙ", c.font(24), ACCENT)
    y = para(d, c, RC_X0, y + 44, "Дороги остаются, плательщики уезжают", 52) + 26
    y = hero(d, c, RC_X0, y, f"ρ = {c3['spearman_rho']:.2f}".replace(".", ","),
             "связь между глубиной убыли района и километрами дороги на одного "
             f"оставшегося жителя, {c3['n_raions']} районов", NEG) + 24
    y = para(d, c, RC_X0, y,
             f"Среди районов разброс — от {lo_v:.1f}".replace(".", ",") +
             f" до {hi_v:.1f}".replace(".", ",") +
             f" км на тысячу жителей: между крайними разница больше чем в {ratio} раз. "
             f"Сеть построена под расселение 1975 года, а содержат её жители 2026-го.",
             25, INK) + 24
    para(d, c, RC_X0, y,
         f"Снимок OpenStreetMap: {fmt_int(g6['osm_total_km'])} км против "
         f"{fmt_int(g6['official_total_km'])} км официальной статистики — расхождение "
         f"{abs(g6['delta_pct']):.1f}".replace(".", ",") + "%, в пределах допуска.", 23, MUTE)
    return canvas


def a_pension(c: Ctx) -> Image.Image:
    p = c.load("pension.json")
    years = p["years"]["national"]
    sr = p["national"]["sr"]["as_is"]["base:official"]
    TY = p["years"]["territory"]
    T = p["territories"]

    def below(year, thr):
        i = TY.index(year)
        return sum(1 for v in T.values()
                   if v.get("sr") and v["sr"]["as_is"]["base:official"][i] is not None
                   and v["sr"]["as_is"]["base:official"][i] < thr)

    canvas = Image.new("RGB", (W, H), BG)
    d = chrome(canvas, c, "ИССЛЕДОВАНИЕ INF-13", ACCENT,
               "Переписи 2009 и 2019, официальные оценки, прогноз v2026.4 (базовый сценарий, "
               "официальный ряд) · by-population-maps.vercel.app/research/pension")
    y = 190
    txt(d, (MARGIN, y), "ПОЧЕМУ ЭТО НЕ ПРО ДЕНЬГИ", c.font(24), ACCENT)
    y = para(d, c, MARGIN, y + 46, "Деньги перераспределяются. Руки — нет.", 60,
             max_w=W - 2 * MARGIN) + 20
    y = para(d, c, MARGIN, y,
             "Сколько работающих приходится на одного человека старше трудоспособного "
             "возраста — по стране, 1989–2056.", 26, DIM, max_w=1100) + 26
    line_chart(d, c, (MARGIN, y, MARGIN + 1080, y + 420), years, sr,
               threshold=1.5, thr_label="1,5 — критическая отметка", obs_until=2026,
               y_lo=1.2, y_hi=3.1)
    cx = MARGIN + 1140
    yy = y + 10
    for val, lab, col in ((f"{below(2046, 1.5)} из {len(T)}",
                           "районов ниже полутора работающих на пожилого к 2046 году", NEG),
                          (f"{below(2056, 1.5)} из {len(T)}",
                           "к 2056 году", NEG),
                          (f"{below(2056, 1.0)}", "районов, где работающих станет меньше, "
                           "чем пожилых", MODEL)):
        txt(d, (cx, yy), val, c.font(52), col)
        yy = para(d, c, cx, yy + 66, lab, 23, DIM, max_w=W - MARGIN - cx) + 26
    para(d, c, MARGIN, y + 450,
         "Пенсию платят из общего котла — она дойдёт куда угодно. Врач, учитель и электрик "
         "живут там же, где работают. Услуга в пустеющем районе не дорожает — она исчезает.",
         28, INK, max_w=1080)
    return canvas


def a_service_math(c: Ctx) -> Image.Image:
    canvas = Image.new("RGB", (W, H), BG)
    d = chrome(canvas, c, "МЕХАНИКА", ACCENT,
               "Схема механизма, а не расчёт · количественная часть — на "
               "by-population-maps.vercel.app/research/grid")
    y = 200
    txt(d, (MARGIN, y), "ПОЧЕМУ ЭТО САМОПОДДЕРЖИВАЮЩИЙСЯ ПРОЦЕСС", c.font(24), ACCENT)
    y = para(d, c, MARGIN, y + 46, "Как из района исчезает услуга", 60,
             max_w=W - 2 * MARGIN) + 50
    steps = [
        ("Уезжает семья", "в классе на двоих меньше, у автобуса на двоих меньше"),
        ("Закрывается класс", "школа переходит на подвоз, маршрут удлиняется"),
        ("Уезжает следующая", "теперь отъезд разумнее, чем ожидание"),
        ("Порог пройден", "ниже 500 человек на км² услуга не окупается ничем"),
    ]
    bw = (W - 2 * MARGIN - 3 * 40) // 4
    for i, (t1, t2) in enumerate(steps):
        x = MARGIN + i * (bw + 40)
        col = NEG if i == 3 else LINE
        d.rounded_rectangle([x, y, x + bw, y + 250], 14, fill=PANEL, outline=col, width=2)
        txt(d, (x + 28, y + 30), f"{i + 1}", c.font(30), ACCENT)
        yy = para(d, c, x + 28, y + 76, t1, 30, INK, max_w=bw - 56)
        para(d, c, x + 28, yy + 12, t2, 22, DIM, max_w=bw - 56)
        if i < 3:
            txt(d, (x + bw + 20, y + 118), "→", c.font(40), MUTE, anchor="mm")
    y += 300
    para(d, c, MARGIN, y,
         "Экономисты называют это положительной обратной связью. На карте она выглядит так: "
         "светлое становится ярче, тёмное — темнее, а серединных оттенков со временем всё "
         "меньше. Работает и в обратную сторону — но разворот начинается не с уговоров "
         "остаться, а с честной карты того, где люди есть на самом деле.", 30, INK,
         max_w=W - 2 * MARGIN)
    return canvas


# --- ассеты: будущее и финал ------------------------------------------------
def a_future(c: Ctx) -> Image.Image:
    nat = c.grid["national"]
    canvas = Image.new("RGB", (W, H), BG)
    d = chrome(canvas, c, "МОДЕЛЬ · БАЗОВЫЙ СЦЕНАРИЙ", MODEL, SRC)
    map_panel(canvas, c, c.frame("pop_2050_base_A.webp"),
              caption="2050 год · модельный кадр", frame_col=MODEL, crop=False)
    d = ImageDraw.Draw(canvas)
    y = 172
    txt(d, (RC_X0, y), "ЧТО ДАЛЬШЕ", c.font(24), ACCENT)
    y = para(d, c, RC_X0, y + 44, "Не предсказание, а «что будет, если»", 52) + 26
    b5_20 = nat["area_share_below"]["5"]["2020"] * 100
    b5_50 = nat["area_share_below"]["5"]["2050:base:A"] * 100
    y = hero(d, c, RC_X0, y, f"{pc(b5_20)} → {pc(b5_50)}",
             "доля территории, где живёт меньше пяти человек на квадратный километр: "
             "2020 год и модель 2050 года", MODEL) + 24
    y = para(d, c, RC_X0, y,
             "Мы взяли районный прогноз проекта и разложили его по клеткам двумя способами; "
             "три сценария — три набора предположений о рождаемости, смертности и отъезде.",
             25, DIM) + 24
    para(d, c, RC_X0, y,
         f"Квадратов, где живёт хотя бы пять человек, было "
         f"{fmt_int(c.story['cells_ge5_pop']['1975'])}, стало "
         f"{fmt_int(c.story['cells_ge5_pop']['2020'])}, к 2050 году останется "
         f"{fmt_int(c.story['cells_ge5_pop']['2050:base:A'])}.", 25, INK)
    return canvas


def a_even_best(c: Ctx) -> Image.Image:
    m = {g["id"]: g for g in c.story["c006_river_road_matrix"]["groups"]}
    canvas = Image.new("RGB", (W, H), BG)
    d = chrome(canvas, c, "МОДЕЛЬ · БАЗОВЫЙ СЦЕНАРИЙ", MODEL, SRC_ROAD)
    y = 200
    txt(d, (MARGIN, y), "ВЫВОД ИЗ ПРОГНОЗНОЙ ЧАСТИ", c.font(24), ACCENT)
    y = para(d, c, MARGIN, y + 46, "Хорошая география перестаёт спасать", 66,
             max_w=W - 2 * MARGIN) + 40
    txt(d, (MARGIN, y), f"{m['both']['change_2050_pct']:+.1f}%".replace(".", ","),
        c.font(150), NEG)
    para(d, c, MARGIN + 560, y + 30,
         "теряет к 2050 году группа «река плюс дорога» — единственная, которая росла "
         "последние сорок пять лет", 30, INK, max_w=W - MARGIN - 560 - MARGIN)
    y += 210
    y = bars(d, c, MARGIN, y,
             [("река + дорога", m["both"]["change_2050_pct"]),
              ("река без дороги", m["river_only"]["change_2050_pct"]),
              ("ни реки, ни дороги", m["neither"]["change_2050_pct"])],
             w=W - 2 * MARGIN, label_w=380) + 20
    para(d, c, MARGIN, y,
         "Пока страна перераспределялась внутри себя, пересечение реки и дороги собирало "
         "людей со всей остальной территории. Когда собирать становится не с кого, начинает "
         "убывать и оно.", 30, DIM, max_w=W - 2 * MARGIN)
    return canvas


def a_conclusions(c: Ctx) -> Image.Image:
    c3 = c.grid["validation"]["c3_correlation"]
    canvas = Image.new("RGB", (W, H), BG)
    d = chrome(canvas, c, "ИТОГ", ACCENT, SRC)
    y = 180
    txt(d, (MARGIN, y), "ЧТО МЫ СЧИТАЕМ УСТАНОВЛЕННЫМ", c.font(24), ACCENT)
    y = para(d, c, MARGIN, y + 46, "Три вывода", 60, max_w=W - 2 * MARGIN) + 44
    items = [
        ("Разговор о «вымирании» описывает не то, что происходит",
         "Численность страны за 45 лет практически не изменилась. Изменилась география: "
         "страна сжалась в несколько десятков плотных пятен и разошлась по швам между ними. "
         "Это другой процесс — с другими последствиями и другими способами на него влиять."),
        ("У пустеющей территории остаётся инфраструктура, а платить за неё некому",
         f"Это не будущая проблема, а текущая: связь ρ = {c3['spearman_rho']:.2f}".replace(".", ",") +
         " между глубиной убыли и километрами дороги на жителя посчитана на данных 2026 года."),
        ("Это не приговор, а следствие правил",
         "Правило пятисот работает в обе стороны. В европейских странах есть территории, "
         "которые перешли порог обратно. Начинается разворот не с уговоров остаться, "
         "а с честной карты того, где люди есть на самом деле."),
    ]
    for i, (t1, t2) in enumerate(items):
        d.ellipse([MARGIN, y + 4, MARGIN + 44, y + 48], fill=ACCENT)
        txt(d, (MARGIN + 22, y + 26), str(i + 1), c.font(26), (10, 12, 24), anchor="mm")
        yy = para(d, c, MARGIN + 70, y, t1, 36, INK, max_w=W - 2 * MARGIN - 70)
        y = para(d, c, MARGIN + 70, yy + 12, t2, 25, DIM, max_w=W - 2 * MARGIN - 70) + 40
    return canvas


def a_verify(c: Ctx) -> Image.Image:
    g3 = c.grid["validation"]["g3_nightlights_crosscheck"]
    canvas = Image.new("RGB", (W, H), BG)
    d = chrome(canvas, c, "", ACCENT, "")
    y = 300
    txt(d, (W // 2, y), "И САМОЕ ВАЖНОЕ", c.font(26), ACCENT, anchor="ma")
    y += 70
    f = c.font(110)
    txt(d, (W // 2, y), "Не верьте. Проверьте.", f, INK, anchor="ma")
    y += 190
    for line in ["Данные, код расчёта, допущения, инструкция для воспроизведения одной",
                 "командой и промпты для проверяющих ИИ-агентов — открыты целиком.",
                 f"Проверка ночными огнями у нас не прошла ({pc(g3['pct_agree'])} при пороге "
                 f"{int(g3['threshold_pct'])}%) — мы написали об этом подробнее,",
                 "чем о том, что прошло. Найдите у нас ошибку — мы её опубликуем."]:
        txt(d, (W // 2, y), line, c.font(30), DIM, anchor="ma")
        y += 46
    y += 40
    txt(d, (W // 2, y), "by-population-maps.vercel.app/research/grid", c.font(38), ACCENT,
        anchor="ma")
    txt(d, (W // 2, H - 90), "BY MAPS · ИССЛЕДОВАНИЕ INF-15 «ПОЛОТНО» · ДАННЫЕ CC BY 4.0",
        c.font(21), MUTE, anchor="ma")
    return canvas


ASSETS = {
    "cover":        ("Обложка: страна не вымирает — она переезжает", a_cover),
    "paradox":      ("Два числа, которые не сходятся", a_paradox),
    "grid_vs_raion": ("Зачем километровая сетка", a_grid_vs_raion),
    "half598":      ("Половина страны на 598 км²", a_half598),
    "rule500":      ("Правило пятисот", a_rule500),
    "rivers":       ("Гипотеза, которую пришлось переписать", a_rivers),
    "roads":        ("Полоса вдоль асфальта", a_roads),
    "matrix":       ("Пересечение реки и дороги", a_matrix),
    "cities_check": ("Независимая проверка на 197 городах", a_cities_check),
    "voids":        ("Три разные пустоты", a_voids),
    "moved":        ("Страна не уменьшилась — она переехала", a_moved),
    "islands":      ("Полотно рвётся на лоскуты", a_islands),
    "network":      ("Дороги остаются, плательщики уезжают", a_network),
    "pension":      ("Деньги перераспределяются, руки — нет", a_pension),
    "service_math": ("Как из района исчезает услуга", a_service_math),
    "future":       ("Не предсказание, а «что будет, если»", a_future),
    "even_best":    ("Хорошая география перестаёт спасать", a_even_best),
    "nightlights":  ("Провал проверки ночными огнями", a_nightlights),
    "conclusions":  ("Три вывода", a_conclusions),
    "verify":       ("Не верьте. Проверьте.", a_verify),
}


def motion_islands(c: Ctx, out: Path) -> None:
    """Единственный анимированный ассет пилота: острова расселения,
    1975 → 2050, по 1,1 с на кадр."""
    years = ["1975", "1980", "1985", "1990", "1995", "2000",
             "2005", "2010", "2015", "2020", "2050_base_A"]
    sc = c.grid["national"]["settlement_components"]
    frames = []
    for yk in years:
        key = "2050:base:A" if yk.startswith("2050") else yk
        model = yk.startswith("2050")
        canvas = Image.new("RGB", (W, H), BG)
        d = chrome(canvas, c, "МОДЕЛЬ" if model else "ДАННЫЕ", MODEL if model else ACCENT, SRC)
        map_panel(canvas, c, c.frame(f"story_islands_{yk}.webp"),
                  caption=("2050 — модель" if model else yk),
                  frame_col=MODEL if model else LINE)
        d = ImageDraw.Draw(canvas)
        y = 172
        txt(d, (RC_X0, y), "ЧТО ПРОИСХОДИТ С ТКАНЬЮ", c.font(24), ACCENT)
        y = para(d, c, RC_X0, y + 44, "Полотно рвётся на лоскуты", 54) + 30
        hero(d, c, RC_X0, y, fmt_int(sc[key]["n_components"]),
             "отдельных «островов» расселения — связных пятен, где живут люди")
        txt(d, (RC_X0, 700), f"крупнейший остров: "
            f"{pc(sc[key]['largest_share_of_area'] * 100)} площади страны",
            c.font(25), DIM)
        frames.append(canvas)
    p = subprocess.Popen(
        ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", "30", "-i", "-", "-c:v", "libx264", "-preset", "medium",
         "-b:v", "10M", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for img in frames:
        buf = img.tobytes()
        for _ in range(33):
            p.stdin.write(buf)
    p.stdin.close()
    p.wait()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--font", type=Path, default=DEFAULT_FONT)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--id", action="append")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--motion", action="store_true")
    args = ap.parse_args()
    c = Ctx(args.data_dir, args.font)
    args.out.mkdir(parents=True, exist_ok=True)
    ids = args.id or (list(ASSETS) if args.all else [])
    for i in ids:
        title, fn = ASSETS[i]
        img = fn(c)
        p = args.out / f"{i}.png"
        img.save(p)
        print(f"{i:12} {title:38} → {p}")
    if args.motion:
        p = args.out / "islands_motion.mp4"
        motion_islands(c, p)
        print(f"{'islands':12} {'анимация 1975→2050':38} → {p}")


if __name__ == "__main__":
    main()
