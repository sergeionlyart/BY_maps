#!/usr/bin/env python3
"""Рилс R-S1 «Карта, где не хватает мужчин» (INF-21): хороплет 118 районов
по соотношению полов в 25–39 (2009 → 2056), сцена опровержения главной
гипотезы и карта 70+.

Механика и визуальный язык — из tools/render_reel_pension.py (R-P1 v1.5):
шрифт, аффинная проекция, бренд-рамка, безопасная зона 4:5 импортируются
оттуда, а не копируются. Сцена — tools/reel_sexratio_scene.json; все числа
в подписях ({n}, {rho}, медианы, пояса) вычисляются из
web/public/data/sexratio.json в момент кадра, чтобы ролик не мог разойтись
с опубликованными данными.

Цветовая шкала — та же, что на странице (web/components/SexRatioView.tsx):
дивергентная вокруг паритета 100 для 25–39 и секвенциальная для 70+, шаги —
web/lib/scales.ts.

Запуск: python tools/render_reel_sexratio.py [--lang ru|be|all]
        [--dump-every N]   # превью-кадры PNG вместо видео
Выход:  build/reel_sexratio_<lang>.mp4 (H.264, CBR 12M, как у R-P1)
Нужен ffmpeg с libx264 в PATH (или в переменной FFMPEG).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import render_reel_pension as rp  # noqa: E402  (общие примитивы R-P1)

W, H = rp.W, rp.H
BG, INK, DIM, AMBER = rp.BG, rp.INK, rp.DIM, rp.AMBER
NODATA, BORDER = rp.NODATA, rp.BORDER
SAFE_TOP, SAFE_BOT = rp.SAFE_TOP, rp.SAFE_BOT
font, fit_text, wrap_center, ru_num = rp.font, rp.fit_text, rp.wrap_center, rp.ru_num

CORE = "base:official"
CENSUS = (2009, 2019)
NODES = [2009, 2019, 2026, 2031, 2036, 2041, 2046, 2051, 2056]

# --- шкалы: буквальный перенос из SexRatioView.tsx -------------------------
_hx = rp._hx
DIV_BREAKS = [92, 96, 99, 101, 104, 108, 115]
DIV_COLORS = [rp.DIV_POS[3], rp.DIV_POS[2], rp.DIV_POS[1], rp.DIV_MID,
              rp.DIV_NEG[1], rp.DIV_NEG[2], rp.DIV_NEG[3]]
SEQ = [_hx(h) for h in ("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
                        "#256abf", "#1c5cab", "#104281", "#0d366b")]
OLD_BREAKS = [34, 38, 42, 46, 50]
OLD_COLORS = [SEQ[7], SEQ[6], SEQ[4], SEQ[2], SEQ[1], SEQ[0]]

MAP_BOX = (60, 560, 960, 760)            # x0, y0, w, h — внутри безопасной зоны
SIL_BOX = (190, 760, 700, 470)


def color_2539(v: float | None) -> tuple[int, int, int]:
    if v is None:
        return NODATA
    i = 0
    while i < len(DIV_BREAKS) - 1 and v >= DIV_BREAKS[i]:
        i += 1
    return DIV_COLORS[min(i, len(DIV_COLORS) - 1)]


def color_70(v: float | None) -> tuple[int, int, int]:
    if v is None:
        return NODATA
    i = 0
    while i < len(OLD_BREAKS) and v >= OLD_BREAKS[i]:
        i += 1
    return OLD_COLORS[i]


# ------------------------------------------------------------------ данные ---

def load_data() -> dict:
    return json.loads((ROOT / "web/public/data/sexratio.json").read_text())


def load_scene() -> dict:
    return json.loads((ROOT / "tools/reel_sexratio_scene.json").read_text())


def node_value(terr: dict, metric: str, year: int) -> float | None:
    if year in CENSUS:
        return terr["summary"][str(year)][metric]
    return terr["forecast_summary"][CORE][str(year)][metric]


def value_at(terr: dict, metric: str, year: float) -> float | None:
    """Линейная интерполяция между узлами — плавный переход карты."""
    if year <= NODES[0]:
        return node_value(terr, metric, NODES[0])
    for a, b in zip(NODES, NODES[1:]):
        if a <= year <= b:
            va, vb = node_value(terr, metric, a), node_value(terr, metric, b)
            if va is None or vb is None:
                return va if vb is None else vb
            k = (year - a) / (b - a)
            return va + (vb - va) * k
    return node_value(terr, metric, NODES[-1])


def male_surplus_count(data: dict, year: float) -> int:
    return sum(1 for t in data["territories"].values()
               if (value_at(t, "r2539", year) or 0) > 100.0)


def median_r70(data: dict, year: float) -> float:
    xs = sorted(v for v in (value_at(t, "r70", year)
                            for t in data["territories"].values()) if v is not None)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


# ---------------------------------------------------------------- геометрия ---

def prepare_geo(data: dict):
    feats, bbox = rp.load_geo(data["territories"])
    proj = rp.make_projector(bbox, *MAP_BOX)
    rp.precompute_pixels(feats, proj)
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    for f in feats:
        for ring in f["pixel_rings"]:
            md.polygon(ring, fill=255)
    hatch = rp.make_hatch_overlay(W, H)
    hatch_masked = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hatch_masked.paste(hatch, (0, 0), Image.composite(
        hatch.getchannel("A"), Image.new("L", (W, H), 0), mask))
    return feats, hatch_masked


def draw_map(img: Image.Image, feats: list[dict], data: dict, metric: str,
             year: float) -> None:
    d = ImageDraw.Draw(img)
    T = data["territories"]
    colorize = color_2539 if metric == "r2539" else color_70
    for f in feats:
        color = colorize(value_at(T[f["id"]], metric, year)) \
            if f["in_territories"] else NODATA
        for ring in f["pixel_rings"]:
            d.polygon(ring, fill=color, outline=BORDER)


# ------------------------------------------------------------------ сцены ---

def _ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def year_along(years: list[int], p: float) -> float:
    """Позиция на списке узлов с паузой на каждом (первые 40 % сегмента
    кадр стоит — читатель успевает увидеть год)."""
    if len(years) == 1:
        return float(years[0])
    k = min(p, 0.9999) * (len(years) - 1)
    i = int(k)
    frac = _ease((k - i - 0.4) / 0.6)
    return years[i] + (years[i + 1] - years[i]) * frac


def placeholders(s: str, **kw) -> str:
    for k, v in kw.items():
        s = s.replace("{" + k + "}", str(v))
    return s



def scene_intro(img, d, T, data, feats, p):
    rp.paste_country(img, feats, SIL_BOX, alpha=0.35 + 0.65 * _ease(p * 2))
    rp.draw_wordmark(d, T, y=360)
    wrap_center(d, 1300, T["title"], 72, INK)


def scene_hook(img, d, T, data, feats, p):
    v = data["country"]["sex_ratio_2019"]
    d.text((W / 2, 520), ru_num(v, 0), font=font(300),
           fill=AMBER, anchor="ma")
    d.text((W / 2, 880), T["hookUnit"], font=font(48), fill=INK, anchor="ma")
    if p > 0.35:
        wrap_center(d, 1060, T["hookSub"], 44, DIM, maxw=W - 160)


def scene_map2539(img, d, T, data, feats, hatch, p, years):
    year = year_along(years, p)
    fit_text(d, (W / 2, 330), T["map2539Title"], 52, INK)
    draw_map(img, feats, data, "r2539", year)
    if year > 2019.5:
        img.paste(hatch, (0, 0), hatch)
    d = ImageDraw.Draw(img)
    yy = int(round(year))
    d.text((W / 2, 410), str(yy), font=font(76), fill=INK, anchor="ma")
    tag = T["model"] if yy > 2019 else T["census"]
    d.text((W / 2, 498), tag, font=font(28),
           fill=rp.ACCENT if yy > 2019 else DIM, anchor="ma")
    fit_text(d, (W / 2, 1360), placeholders(
        T["map2539Counter"], n=male_surplus_count(data, year)), 44, AMBER)
    fit_text(d, (W / 2, 1430), T["map2539Legend"], 30, DIM)


def scene_refuted(img, d, T, data, feats, p):
    F = data["findings"]["H1"]
    belts = data["posthoc"]["belts_median_r2539"]
    fit_text(d, (W / 2, 330), T["refutedKicker"], 50, AMBER)
    y = wrap_center(d, 430, T["refutedPred"], 38, DIM, maxw=W - 140)
    if p > 0.15:
        wrap_center(d, y + 20, placeholders(
            T["refutedFact"], rho=ru_num(F["spearman_rho"], 2).replace("-", "−")),
            46, INK)
    # мини-график: столбики — ОТКЛОНЕНИЕ медианы от паритета 100 (вверх —
    # мужской перевес, вниз — женский). Базовая линия столбика = 100, а не
    # обрезанная ось: иначе 99,4 против 107,3 выглядело бы как разница в разы.
    x0, x1, ybase, unit = 140, 940, 1180, 26.0     # unit: пикселей на пункт
    n = len(belts)
    slot = (x1 - x0) / n
    bw = slot * 0.62
    top = max(belts, key=lambda b: b["median"])
    grow = _ease((p - 0.25) / 0.45)
    d.line([(x0 - 20, ybase), (x1 + 20, ybase)], fill=DIM, width=2)
    d.text((x0 - 28, ybase), "100", font=font(24), fill=DIM, anchor="rm")
    for i, b in enumerate(belts):
        dev = (b["median"] - 100.0) * unit * grow
        cx = x0 + slot * (i + 0.5)
        col = AMBER if b is top else (120, 112, 98)
        y_top, y_bot = (ybase - dev, ybase) if dev >= 0 else (ybase, ybase - dev)
        d.rounded_rectangle([cx - bw / 2, y_top, cx + bw / 2, max(y_bot, y_top + 2)],
                            radius=6, fill=col)
        if grow > 0.95:
            ly, anc = (y_top - 12, "mb") if dev >= 0 else (y_bot + 12, "ma")
            d.text((cx, ly), ru_num(b["median"], 1), font=font(30), fill=INK, anchor=anc)
        lab = b["belt"].replace("-", "–")
        lab = ("> " + lab.rstrip("–")) if lab.endswith("–") else lab
        d.text((cx, ybase + 70), lab, font=font(26), fill=DIM, anchor="ma")
    d.text((W / 2, ybase + 110), T["beltUnit"], font=font(24), fill=DIM, anchor="ma")
    fit_text(d, (W / 2, 820), T["refutedBelts"], 28, DIM)
    if p > 0.7:
        wrap_center(d, 1420, T["refutedNote"], 36, INK, maxw=W - 140)


def scene_map70(img, d, T, data, feats, p, years):
    year = year_along(years, p)
    fit_text(d, (W / 2, 330), T["map70Title"], 52, INK)
    draw_map(img, feats, data, "r70", year)
    d = ImageDraw.Draw(img)
    yy = int(round(year))
    d.text((W / 2, 410), str(yy), font=font(76), fill=INK, anchor="ma")
    tag = T["model"] if yy > 2019 else T["census"]
    d.text((W / 2, 498), tag, font=font(28),
           fill=rp.ACCENT if yy > 2019 else DIM, anchor="ma")
    med = median_r70(data, year)
    d.text((W / 2, 1345), ru_num(med, 0), font=font(110), fill=AMBER, anchor="ma")
    fit_text(d, (W / 2, 1470), T["map70Unit"], 34, INK)
    if p > 0.55:
        fit_text(d, (W / 2, 1525), T["map70Sub"], 28, DIM)


def scene_finale(img, d, T, data, feats, p):
    rp.paste_country(img, feats, SIL_BOX, alpha=0.5)
    rp.draw_wordmark(d, T, y=360, kicker=False)
    wrap_center(d, 520, T["title"], 64, INK)
    wrap_center(d, 1290, T["finaleCta"], 50, AMBER)
    fit_text(d, (W / 2, 1380), T["ctaUrl"], 32, INK)
    wrap_center(d, 1460, T["source"], 26, DIM, maxw=W - 160)


def render_frame(gi: int, data: dict, scene: dict, feats, hatch,
                 lang: str) -> Image.Image:
    fps = scene["format"]["fps"]
    t = gi / fps
    T = scene["texts"][lang]
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    seg = next((s for s in scene["timeline"] if s["t"][0] <= t < s["t"][1]),
               scene["timeline"][-1])
    a, b = seg["t"]
    p = (t - a) / (b - a)
    name = seg["scene"]
    if name == "intro":
        scene_intro(img, d, T, data, feats, p)
    elif name == "hook":
        scene_hook(img, d, T, data, feats, p)
    elif name == "map2539":
        scene_map2539(img, d, T, data, feats, hatch, p, seg["years"])
    elif name == "refuted":
        scene_refuted(img, d, T, data, feats, p)
    elif name == "map70":
        scene_map70(img, d, T, data, feats, p, seg["years"])
    else:
        scene_finale(img, d, T, data, feats, p)
    d = ImageDraw.Draw(img)
    rp.draw_frame_bands(d, T, top=True)
    # плавное появление каждой сцены (0,35 с из фона)
    fade = _ease((t - a) / 0.35)
    if fade < 1.0:
        img = Image.blend(Image.new("RGB", (W, H), BG), img, fade)
    return img


def render(lang: str, dump_every: int) -> None:
    data = load_data()
    scene = load_scene()
    feats, hatch = prepare_geo(data)
    fps = scene["format"]["fps"]
    total = int(scene["format"]["durationSec"] * fps)
    out_dir = ROOT / "build"
    out_dir.mkdir(exist_ok=True)
    if dump_every:
        dd = out_dir / f"reel_sexratio_preview_{lang}"
        dd.mkdir(parents=True, exist_ok=True)
        for gi in range(0, total, dump_every):
            render_frame(gi, data, scene, feats, hatch, lang).save(dd / f"f{gi:05d}.png")
        print(f"OK: превью в {dd}")
        return
    ffmpeg = os.environ.get("FFMPEG", "ffmpeg")
    dst = out_dir / f"reel_sexratio_{lang}.mp4"
    cmd = [ffmpeg, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-c:v", "libx264", "-preset", "slow",
           "-b:v", "12M", "-minrate", "12M", "-maxrate", "12M",
           "-bufsize", "24M", "-x264-params", "nal-hrd=cbr",
           "-pix_fmt", "yuv420p", str(dst)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for gi in range(total):
        img = render_frame(gi, data, scene, feats, hatch, lang)
        proc.stdin.write(img.tobytes())
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
