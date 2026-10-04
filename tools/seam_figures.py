"""Иллюстрации «Шва на карте» (карточки 1600x900 в стиле статьи INF-15).

Вход: data/raw/seam/cells.csv.gz, web/public/data/seam.json,
      data/raw/seam/units/twins.csv (если есть).
Выход: web/public/content/img/seam/*.webp

Запуск: python tools/seam_figures.py   (нужны matplotlib, numpy, rasterio)
"""
from __future__ import annotations

import csv
import gzip
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch
from rasterio.warp import transform_geom
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "public" / "content" / "img" / "seam"
SEAM = json.loads((ROOT / "web" / "public" / "data" / "seam.json").read_text())
EST = SEAM["estimates"]

BG, PANEL, FRAME = "#0b0e1a", "#0e1222", "#2a3247"
INK, MUTED, TEAL = "#f2f4f8", "#9aa3b5", "#4fb8c4"
POS, NEG, BYC, NBC = "#66c2a5", "#e07a68", "#4a86e8", "#e8a33d"
SEGS = ["PL", "LT", "LV", "RU", "UA"]
SEG_RU = {"PL": "Польша", "LT": "Литва", "LV": "Латвия", "RU": "Россия", "UA": "Украина"}
FOOT = ("Данные: WSF Evolution (DLR), GHSL R2023A (JRC), Li et al. v10, VIIRS VNL, GLAD cropland · "
        "ячейка 1 км, полоса ±50 км · by-population-maps.vercel.app")
plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK, "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": FRAME})


def mn(x: str) -> str:
    return x.replace("-", "\u2212").replace(".", ",")


def est(y, s, spec="main"):
    for e in EST:
        if e["outcome"] == y and e["seg"] == s and e["spec"] == spec:
            return e
    return None


def card(kicker, title, subtitle, body, badge, footer=FOOT, left=None, left_caption=""):
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=BG)
    fig.text(0.0375, 0.935, "BY MAPS · ШОВ НА КАРТЕ", color=TEAL, fontsize=13.5, va="center")
    fig.add_artist(FancyBboxPatch((0.84, 0.915), 0.1225, 0.04, boxstyle="round,pad=0.004,rounding_size=0.008",
                                  transform=fig.transFigure, fc=BG, ec=TEAL, lw=1.3))
    fig.text(0.90125, 0.935, badge, color=TEAL, fontsize=12, ha="center", va="center")
    fig.add_artist(plt.Line2D([0.0375, 0.9625], [0.9, 0.9], color=FRAME, lw=1, transform=fig.transFigure))
    fig.add_artist(plt.Line2D([0.0375, 0.9625], [0.068, 0.068], color=FRAME, lw=1, transform=fig.transFigure))
    fig.text(0.0375, 0.042, footer, color=MUTED, fontsize=10.2, va="center")
    fig.add_artist(FancyBboxPatch((0.0375, 0.075), 0.5, 0.79, boxstyle="round,pad=0.004,rounding_size=0.01",
                                  transform=fig.transFigure, fc=PANEL, ec=FRAME, lw=1.2, zorder=-5))
    if left_caption:
        fig.text(0.2875, 0.098, left_caption, color=MUTED, fontsize=11.5, ha="center", va="center")
    x0 = 0.57
    fig.text(x0, 0.83, kicker, color=TEAL, fontsize=15, va="center")
    fig.text(x0, 0.755, title, color=INK, fontsize=33, va="center")
    fig.text(x0, 0.665, subtitle, color=MUTED, fontsize=15, va="top", linespacing=1.45, wrap=True)
    nlines = body.count("\n") + 1
    fig.text(x0, 0.115 + nlines * 0.034, body, color=INK, fontsize=14.2, va="top", linespacing=1.5)
    if left:
        left(fig)
    return fig


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{name}.png"
    fig.savefig(p, dpi=100, facecolor=BG)
    plt.close(fig)
    from PIL import Image
    Image.open(p).convert("RGB").save(OUT / f"{name}.webp", "WEBP", quality=88, method=6)
    p.unlink()
    print("ok", name)


# ------------------------------------------------------------------ данные карт
def load_cells():
    xs, ys, crop03, crop19, side, d = [], [], [], [], [], []
    with gzip.open(ROOT / "data" / "raw" / "seam" / "cells.csv.gz", "rt") as fh:
        for r in csv.DictReader(fh):
            if abs(float(r["d_km"])) > 50:
                continue
            xs.append(float(r["x3035"])); ys.append(float(r["y3035"]))
            crop03.append(float(r["crop_2003"])); crop19.append(float(r["crop_2019"]))
            side.append(r["side"]); d.append(float(r["d_km"]))
    return (np.array(xs), np.array(ys), np.array(crop03), np.array(crop19), np.array(side), np.array(d))


def outlines():
    by = unary_union([shape(f["geometry"]) for f in
                      json.load(open(ROOT / "web" / "public" / "data" / "geo" / "adm1.geojson"))["features"]])
    nb = json.load(open(ROOT / "data" / "raw" / "seam" / "neighbors_adm0.geojson"))["features"]
    to = lambda g: shape(transform_geom("EPSG:4326", "EPSG:3035", mapping(g)))
    return to(by), [to(shape(f["geometry"])) for f in nb]


def draw_geom(ax, g, **kw):
    geoms = getattr(g, "geoms", [g])
    for p in geoms:
        if p.geom_type == "Polygon":
            x, y = p.exterior.xy
            ax.plot(x, y, **kw)
        elif p.geom_type == "MultiPolygon":
            draw_geom(ax, p, **kw)


CELLS = load_cells()
BY_OUT, NB_OUT = outlines()


from matplotlib.colors import LinearSegmentedColormap
CM_LEVEL = LinearSegmentedColormap.from_list("lvl", ["#151b2c", "#1f4f4a", "#3f8f6b", "#8cc084", "#e6f2a2"])
CM_DIV = LinearSegmentedColormap.from_list("div", ["#b8613a", "#7a4630", "#1a2033", "#2e6f63", "#66d1b0"])


def raster(values, res=1250.0):
    xs, ys = CELLS[0], CELLS[1]
    x0, y0 = xs.min(), ys.min()
    ix = ((xs - x0) // res).astype(int)
    iy = ((ys - y0) // res).astype(int)
    W, H = ix.max() + 1, iy.max() + 1
    sm = np.zeros((H, W)); n = np.zeros((H, W))
    np.add.at(sm, (iy, ix), values); np.add.at(n, (iy, ix), 1)
    img = np.where(n > 0, sm / np.maximum(n, 1), np.nan)
    return img[::-1], (x0, x0 + W * res, y0, y0 + H * res)


def country_labels(ax):
    xs, ys, c03, c19, side, d = CELLS
    names = {"BY": "Беларусь", **SEG_RU}
    for k, nm in names.items():
        m = (side == k) & (np.abs(d) > 20) & (np.abs(d) < 45)
        if k == "BY":
            continue
        if m.sum() > 50:
            ax.text(np.median(xs[m]), np.median(ys[m]), nm, color=INK, fontsize=11, ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.25", fc=BG, ec="none", alpha=0.75))
    ax.text(np.median(xs), np.median(ys), "Беларусь", color=MUTED, fontsize=13, ha="center", va="center")


def map_axes(fig):
    ax = fig.add_axes([0.045, 0.125, 0.485, 0.73], facecolor=PANEL)
    xs, ys = CELLS[0], CELLS[1]
    ax.set_xlim(xs.min() - 5000, xs.max() + 5000)
    ax.set_ylim(ys.min() - 5000, ys.max() + 5000)
    ax.set_aspect("equal")
    ax.axis("off")
    return ax


# ------------------------------------------------------------------ карточки
def fig_cover():
    def left(fig):
        ax = map_axes(fig)
        xs, ys, c03, c19, side, d = CELLS
        img, ext = raster(c19 * 100)
        ax.imshow(img, extent=ext, cmap=CM_LEVEL, vmin=0, vmax=75, interpolation="nearest")
        draw_geom(ax, BY_OUT, color=INK, lw=1.2)
        country_labels(ax)
    fig = card("ИССЛЕДОВАНИЕ", "Шов на карте",
               "Беларусь и пять соседей по обе стороны\nграницы: застройка, огни и поля\nв полосе ±50 км, 1990–2024.",
               "Ландшафт по обе стороны линии одинаковый,\nправила с 1991 года — разные. Если на самой\n"
               "линии есть скачок, его создала не география,\nа государство. Мы проверили 234 тыс. квадратов\n"
               "по 1 км вдоль всех пяти границ.",
               "1990–2024", left=left, left_caption="Доля пашни в квадрате 1 км, 2019 · чем зеленее, тем больше полей")
    save(fig, "cover")


def fig_fields():
    vals = {s: est("C_0319", s) for s in SEGS}
    def left(fig):
        ax = map_axes(fig)
        xs, ys, c03, c19, side, d = CELLS
        img, ext = raster((c19 - c03) * 100)
        ax.imshow(img, extent=ext, cmap=CM_DIV, vmin=-25, vmax=25, interpolation="nearest")
        draw_geom(ax, BY_OUT, color=INK, lw=1.2)
        country_labels(ax)
    body_lines = []
    fig = card("НАХОДКА 1", "Шов виден в полях",
               "Скачок изменения доли пашни 2003 → 2019,\nсосед минус Беларусь, п.п.",
               "Литовская и латвийская стороны после 2004 года\nвернули поля быстрее белорусской, российская —\n"
               "продолжала их терять. С Польшей скачка нет.\nЛожные границы в 30 км у Литвы, Латвии\nи России скачка не дают.",
               "ДАННЫЕ 2003–2019", left=left,
               left_caption="Изменение доли пашни 2003→2019 · зелёный — прибавилось, коричневый — убыло")
    ax = fig.add_axes([0.655, 0.295, 0.30, 0.30], facecolor=BG)
    names = [SEG_RU[s] for s in SEGS]
    taus = [vals[s]["tau"] for s in SEGS]
    ses = [vals[s]["se"] for s in SEGS]
    sig = [vals[s]["p"] < 0.05 for s in SEGS]
    cols = [(POS if t > 0 else NEG) if g else MUTED for t, g in zip(taus, sig)]
    yy = np.arange(len(SEGS))[::-1]
    ax.barh(yy, taus, color=cols, height=0.62)
    ax.errorbar(taus, yy, xerr=[1.96 * s for s in ses], fmt="none", ecolor=INK, lw=1, capsize=3)
    ax.axvline(0, color=MUTED, lw=1)
    ax.set_yticks(yy); ax.set_yticklabels(names, fontsize=13, color=INK)
    for y, t, s, g in zip(yy, taus, ses, sig):
        edge = t + (1.96 * s if t >= 0 else -1.96 * s)
        ax.text(edge + (0.8 if t >= 0 else -0.8), y, mn(f"{t:+.1f}") + ("" if g else " (н/з)"),
                va="center", ha="left" if t >= 0 else "right", fontsize=12.5, color=INK)
    ax.set_xlim(-17, 27)
    ax.tick_params(axis="x", labelsize=10)
    for sp in ["top", "right", "left"]:
        ax.spines[sp].set_visible(False)
    save(fig, "fields")


def profile_panel(fig, rect, y, segs, ylab, ylim=None, show_fit=True):
    prof = SEAM["profiles"][y]
    n = len(segs)
    w = rect[2] / n
    for i, s in enumerate(segs):
        ax = fig.add_axes([rect[0] + i * w + 0.006, rect[1], w - 0.014, rect[3]], facecolor=PANEL)
        pts = prof[s]
        d = np.array([p["d"] for p in pts]); v = np.array([p["y"] for p in pts]); nn = np.array([p["n"] for p in pts])
        ax.scatter(d[d < 0], v[d < 0], s=10, color=BYC)
        ax.scatter(d[d > 0], v[d > 0], s=10, color=NBC)
        if show_fit:
            for m, col in [((d < 0) & (d >= -25), BYC), ((d > 0) & (d <= 25), NBC)]:
                if m.sum() > 2:
                    k = np.polyfit(d[m], v[m], 1, w=np.sqrt(nn[m]))
                    xx = np.linspace(d[m].min(), d[m].max(), 10)
                    ax.plot(xx, np.polyval(k, xx), color=col, lw=2)
        ax.axvline(0, color=INK, lw=0.8, ls=":")
        ax.set_title(SEG_RU[s], color=INK, fontsize=12)
        ax.tick_params(labelsize=8.5)
        if ylim:
            ax.set_ylim(*ylim)
        if i == 0:
            ax.set_ylabel(ylab, fontsize=10)
        else:
            ax.set_yticklabels([])
        ax.set_xticks([-50, 0, 50])
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)


def fig_houses():
    def left(fig):
        profile_panel(fig, [0.05, 0.2, 0.47, 0.6], "B_9015", SEGS, "Δ ln застройки 1990→2015")
    fig = card("НАХОДКА 2", "В домах шва нет",
               "Рост застройки 1990 → 2015 по спутниковому\nряду WSF: по обе стороны линии он одинаков.",
               "Ни на одной из пяти границ скачок не значим.\nНовые дома, дачи и фермы появлялись с\n"
               "одинаковой скоростью по обе стороны. Плюс\nу Литвы держится не на линии, а на\nпригородах Вильнюса.",
               "ДАННЫЕ 1990–2015", left=left,
               left_caption="Синие точки — Беларусь, оранжевые — сосед · км от границы")
    save(fig, "houses")


def fig_lights():
    def left(fig):
        profile_panel(fig, [0.05, 0.53, 0.47, 0.3], "L_1924", ["PL", "LT", "LV", "RU", "UA"], "Δ ln огней 2019→2024")
        profile_panel(fig, [0.05, 0.17, 0.47, 0.3], "L_9212", ["PL", "LT", "LV", "RU", "UA"], "Δ ln огней 1992→2012")
    ua = est("L_1924", "UA"); ru = est("L_0412", "RU"); ua2 = est("L_0412", "UA")
    t_ua, t_ua2, t_ru = (mn(f"{e['tau']:+.2f}") for e in (ua, ua2, ru))
    fig = card("НАХОДКА 3", "Огни: два разлома",
               "Вверху — 2019 → 2024, внизу — 1992 → 2012.",
               f"С 2019 года украинская сторона у линии\nпотеряла свет (скачок {t_ua} лог. пункта):\n"
               "это война и закрытая граница, а не экономика.\n"
               f"В 2004–2012 белорусская сторона светлела\nбыстрее украинской ({t_ua2}) и российской\n({t_ru}, но неустойчиво к засветке).",
               "ДАННЫЕ 1992–2024", left=left,
               left_caption="Огни: гармонизированный ряд Li et al. v10 · км от границы")
    save(fig, "lights")


def fig_light_policy():
    def left(fig):
        ax = fig.add_axes([0.09, 0.2, 0.42, 0.6], facecolor=PANEL)
        yy = np.arange(len(SEGS))[::-1]
        for spec, off, col, lab in [("main", 0.15, TEAL, "застройка + население"),
                                    ("built_only", -0.15, NBC, "только застройка")]:
            e = [est("I_2019", s, spec) for s in SEGS]
            t = [x["tau"] for x in e]; se = [x["se"] for x in e]
            ax.errorbar(t, yy + off, xerr=[1.96 * s for s in se], fmt="o", color=col, ecolor=col, capsize=3, label=lab)
        ax.axvline(0, color=INK, lw=1)
        ax.set_yticks(yy); ax.set_yticklabels([SEG_RU[s] for s in SEGS], color=INK, fontsize=12)
        ax.set_xlabel("скачок яркости у линии, сосед − Беларусь (лог. пункты)", fontsize=10.5)
        ax.legend(facecolor=PANEL, edgecolor=FRAME, labelcolor=INK, fontsize=10, loc="lower right")
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)
    fig = card("НАХОДКА 4", "Огни не врут",
               "Светится ли Беларусь ярче при той же\nзастройке? Гипотеза «освещение — политика».",
               "Нет. При равной застройке и населении яркость\nпо обе стороны линии одинакова на всех пяти\n"
               "границах. Значит, ночные огни здесь можно\nсравнивать через границу — проверка метода,\nна котором стоит и INF-08.",
               "VIIRS 2019", left=left,
               left_caption="Точка — оценка скачка, черта — 95% интервал")
    save(fig, "light_policy")


def fig_scorecard():
    H = SEAM["hypotheses"]
    rows = [("H1", "Скачок в росте застройки на ≥3 из 5 границ", H["H1"]["verdict"]),
            ("H2", "Соседи (кроме Польши) теряют пашню быстрее", H["H2"]["verdict"]),
            ("H3", "Беларусь ярче при той же застройке", H["H3"]["verdict"]),
            ("H4", "Украинская сторона темнеет после 2019", H["H4"]["verdict"]),
            ("H5", "Население: соседи теряют быстрее (описательно)", SEAM.get("units", {}).get("verdict", "см. раздел про пары"))]
    def left(fig):
        y = 0.78
        for code, txt, v in rows:
            col = POS if v.startswith("подтвержд") else (NBC if v.startswith("частич") else NEG)
            fig.text(0.07, y, code, color=TEAL, fontsize=18, va="center")
            fig.text(0.12, y, txt, color=INK, fontsize=14, va="center")
            fig.text(0.12, y - 0.045, v, color=col, fontsize=13, va="center")
            y -= 0.13
    fig = card("ПРОВЕРКА", "Что не подтвердилось",
               "Гипотезы записаны до расчёта\n(docs/preregistration/seam-v0.1.md).",
               "Три из четырёх формальных гипотез не прошли.\nЭто тоже результат: застройка и свет у\n"
               "границ ведут себя одинаково, а различие\nгосударственных моделей видно в другом —\nв судьбе полей.",
               "ПРЕРЕГИСТРАЦИЯ", left=left, left_caption="Вердикты — по правилам, записанным до расчёта")
    save(fig, "scorecard")


TWIN_SERIES = {
    "Браслав ↔ Игналина и Краслава": [
        ("BY", ["r-braslauski"], "Браславский р-н"),
        ("LT", ["LT-SSR-ignalinskij_r", "LT-45+LT-30"], "Игналина + Висагинас"),
        ("LV", ["LV0600202+LV0601000+LV0604300"], "Краслава + Дагда + Аглона"),
    ],
    "Гродно ↔ Сокулка": [
        ("BY", ["r-hrodzienski#admin"], "Гродненский р-н без Гродно"),
        ("PL", ["PL-2011 (powiat sokólski)"], "Сокульский повят"),
    ],
    "Столин ↔ Ровенское Полесье": [
        ("BY", ["r-stolinski"], "Столинский р-н"),
        ("UA", ["UA-RIV-dubrovickij_old"], "Дубровицкий р-н"),
        ("UA", ["UA-RIV-zarichnenskij_old"], "Заречненский р-н"),
    ],
    "Россоны ↔ Псковщина": [
        ("BY", ["r-rasonski"], "Россонский р-н"),
        ("RU", ["RU-PSK-sebezhskij_r"], "Себежский р-н"),
        ("RU", ["RU-PSK-nevelskij_r"], "Невельский р-н"),
    ],
}
NB_COLORS = ["#e8a33d", "#e07a68"]


def fig_twins():
    p = ROOT / "data" / "raw" / "seam" / "units" / "twins.csv"
    if not p.exists():
        print("twins.csv нет — пропуск")
        return
    data = {}
    for r in csv.DictReader(open(p, encoding="utf-8")):
        if r.get("population"):
            data.setdefault(r["unit_id"], {})[int(r["year"])] = float(r["population"])

    def series(ids):
        out = {}
        for uid in ids:
            out.update(data.get(uid, {}))
        return dict(sorted(out.items()))

    def left(fig):
        n = len(TWIN_SERIES)
        h = 0.70 / n
        for i, (g, items) in enumerate(TWIN_SERIES.items()):
            ax = fig.add_axes([0.07, 0.835 - (i + 1) * h + 0.025, 0.255, h - 0.05], facecolor=PANEL)
            k = 0
            labels = []
            for cc, ids, label in items:
                ser = series(ids)
                if not ser:
                    continue
                yrs = sorted(ser)
                base = ser[yrs[0]]
                col = BYC if cc == "BY" else NB_COLORS[min(k, 1)]
                if cc != "BY":
                    k += 1
                vals = [ser[y] / base * 100 for y in yrs]
                ax.plot(yrs, vals, "-o", color=col, ms=3.2, lw=2)
                labels.append([vals[-1], f"{label} ({cc}, {yrs[-1]}) {mn(f'{vals[-1] - 100:+.0f}')}%", col])
            labels.sort(key=lambda t: -t[0])
            for j in range(1, len(labels)):          # разнести подписи по вертикали
                if labels[j - 1][0] - labels[j][0] < 7.5:
                    labels[j][0] = labels[j - 1][0] - 7.5
            for yv, txt, col in labels:
                ax.text(2027.6, yv, txt, color=col, fontsize=9, va="center", clip_on=False)
            ax.axhline(100, color=MUTED, lw=0.6, ls=":")
            ax.set_xlim(1987, 2027)
            ax.set_ylim(38, 108)
            ax.tick_params(labelsize=8)
            ax.set_title(g, color=INK, fontsize=10.5, loc="left")
            for sp in ["top", "right"]:
                ax.spines[sp].set_visible(False)

    comp = SEAM.get("units", {}).get("comparison", {})
    def c(sg):
        x = comp.get(sg, {})
        return (mn(f"{x.get('nb_median', 0):+.1f}"), mn(f"{x.get('by_median', 0):+.1f}"))
    lt, lv, pl, ru, ua = (c(s) for s in ["LT", "LV", "PL", "RU", "UA"])
    fig = card("ПАРЫ-БЛИЗНЕЦЫ", "Соседи через линию",
               "Официальное население районов-соседей,\nпервый год (1988–1990) = 100.",
               f"Медианный темп убыли в полосе 50 км,\n% в год, сосед / Беларусь:\n"
               f"Литва {lt[0]} / {lt[1]}, Латвия {lv[0]} / {lv[1]},\n"
               f"Польша {pl[0]} / {pl[1]}, Украина {ua[0]} / {ua[1]},\n"
               f"Россия {ru[0]} / {ru[1]} — почти одинаково.\n"
               "Беларусь — посередине между соседями.",
               "1988–2026", left=left,
               footer="Данные: переписи 1988/1989 (GUS, Демоскоп), Белстат, GUS BDL, OSP Литвы, CSP Латвии, "
                      "Росстат (БД ПМО), Госстат Украины · в скобках — последний доступный год",
               left_caption="Официальные ряды; у стран разные определения населения")
    save(fig, "twins")


if __name__ == "__main__":
    fig_cover(); fig_fields(); fig_houses(); fig_lights(); fig_light_policy(); fig_scorecard(); fig_twins()
