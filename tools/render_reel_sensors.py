#!/usr/bin/env python3
"""Рилс R-V1 «Второй сенсор» (INF-21): согласие официального ряда со
спутником (H1), опровержение «свет следует за людьми» (H2) и карта
расхождения света и населения 2013–2019.

Механика и визуальный язык — из tools/render_reel_pension.py (R-P1 v1.5):
шрифт, аффинная проекция, бренд-рамка, безопасная зона 4:5 импортируются
оттуда, а не копируются. Сцена — tools/reel_sensors_scene.json; все числа в
подписях ({n}, {rho}) вычисляются из web/public/data/sensors.json в момент
кадра, чтобы ролик не мог разойтись с опубликованными данными.

Цветовая шкала карты — та же, что на странице (web/components/SensorsView.tsx,
BREAKS/COLORS): дивергентная вокруг нуля, шаги — web/lib/scales.ts.

Запуск: python tools/render_reel_sensors.py [--lang ru|be|all]
        [--dump-every N]   # превью-кадры PNG вместо видео
Выход:  build/reel_sensors_<lang>.mp4 (H.264, CBR 12M, как у R-P1)
Нужен ffmpeg с libx264 в PATH (или в переменной FFMPEG).
"""
from __future__ import annotations

import argparse
import json
import math
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
font, fit_text, wrap_center, ru_num = rp.font, rp.fit_text, rp.wrap_center, rp.ru_num

# --- шкала карты: буквальный перенос из SensorsView.tsx --------------------
BREAKS = [-0.3, -0.15, -0.05, 0.05, 0.15, 0.3]
COLORS = [rp.DIV_NEG[3], rp.DIV_NEG[2], rp.DIV_NEG[0], rp.DIV_MID,
          rp.DIV_POS[0], rp.DIV_POS[2], rp.DIV_POS[3]]

MAP_BOX = (60, 560, 960, 760)            # x0, y0, w, h — внутри безопасной зоны
SIL_BOX = (190, 760, 700, 470)
PLOT = (170, 640, 820, 680)              # x0, y0, w, h — поле диаграммы рассеяния
# Пределы осей в лог-единицах; обе оси в одном масштабе, чтобы разброс света
# и населения сравнивался честно. Точки за пределами прижимаются к краю
# (в H1 — одна точка по оси спутника).
LIM_H1 = (-0.75, 0.75)
LIM_H2 = (-0.7, 1.05)
TICKS_PCT = (-50, 0, 50, 100)


def color_lo(v: float | None) -> tuple[int, int, int]:
    if v is None:
        return NODATA
    i = 0
    while i < len(BREAKS) and v >= BREAKS[i]:
        i += 1
    return COLORS[i]


# ------------------------------------------------------------------ данные ---

def load_data() -> dict:
    return json.loads((ROOT / "web/public/data/sensors.json").read_text())


def load_scene() -> dict:
    return json.loads((ROOT / "tools/reel_sensors_scene.json").read_text())


def lo_value(t: dict) -> float | None:
    """Метрика карты: на сколько изменение доли в свете обогнало изменение
    доли в населении за 2013–2019 (как метрика 'lo' на странице)."""
    if t.get("dL_1319") is None or t.get("dO_1319") is None:
        return None
    return t["dL_1319"] - t["dO_1319"]


def light_up_pop_down(data: dict) -> int:
    return sum(1 for t in data["territories"].values()
               if t["dL_1319"] > 0 > t["dO_1319"])


def sign_agree_og(data: dict) -> int:
    return sum(1 for t in data["territories"].values()
               if t.get("dO_9020") is not None and t.get("dG_9020") is not None
               and (t["dO_9020"] > 0) == (t["dG_9020"] > 0))


def rho_txt(v: float) -> str:
    return ru_num(v, 2).replace("-", "−")


# ---------------------------------------------------------------- геометрия ---

def prepare_geo(data: dict):
    feats, bbox = rp.load_geo(data["territories"])
    proj = rp.make_projector(bbox, *MAP_BOX)
    rp.precompute_pixels(feats, proj)
    return feats, None


def draw_map(img: Image.Image, feats: list[dict], data: dict) -> None:
    d = ImageDraw.Draw(img)
    T = data["territories"]
    for f in feats:
        color = color_lo(lo_value(T[f["id"]])) if f["in_territories"] else NODATA
        for ring in f["pixel_rings"]:
            d.polygon(ring, fill=color, outline=BORDER)


def _ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def placeholders(s: str, **kw) -> str:
    for k, v in kw.items():
        s = s.replace("{" + k + "}", str(v))
    return s


def scatter(d: ImageDraw.ImageDraw, pts: list[tuple[float, float]], shown: float,
            xlab: str, ylab: str, color, lim: tuple[float, float]) -> None:
    """Диаграмма рассеяния в лог-единицах с осями в процентах (одинаковые
    пределы по обеим осям). Точки за пределами прижимаются к краю."""
    x0, y0, w, h = PLOT
    lo, hi = lim
    def px(v): return x0 + (max(lo, min(hi, v)) - lo) / (hi - lo) * w
    def py(v): return y0 + h - (max(lo, min(hi, v)) - lo) / (hi - lo) * h
    d.rectangle([x0, y0, x0 + w, y0 + h], outline=(60, 57, 52), width=2)
    d.line([(px(0), y0), (px(0), y0 + h)], fill=(80, 76, 69), width=2)
    d.line([(x0, py(0)), (x0 + w, py(0))], fill=(80, 76, 69), width=2)
    for pc in TICKS_PCT:
        v = math.log(1 + pc / 100)
        if not lo + 0.05 < v < hi:
            continue
        lab = (f"{pc:+d} %" if pc else "0").replace("-", "−")
        d.line([(px(v), y0 + h), (px(v), y0 + h + 8)], fill=DIM, width=2)
        d.line([(x0 - 8, py(v)), (x0, py(v))], fill=DIM, width=2)
        d.text((px(v), y0 + h + 14), lab, font=font(24), fill=DIM, anchor="ma")
        d.text((x0 - 14, py(v)), lab, font=font(24), fill=DIM, anchor="rm")
    d.text((x0 + w / 2, y0 + h + 52), xlab, font=font(28), fill=DIM, anchor="ma")
    d.text((x0 + 14, y0 + 14), ylab, font=font(28), fill=DIM, anchor="la")
    n = int(round(len(pts) * shown))
    for x, y in pts[:n]:
        cx, cy = px(x), py(y)
        d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=color)


def points(data: dict, kx: str, ky: str) -> list[tuple[float, float]]:
    T = data["territories"]
    return [(T[z][kx], T[z][ky]) for z in sorted(T)
            if T[z].get(kx) is not None and T[z].get(ky) is not None]


# ------------------------------------------------------------------ сцены ---

def scene_intro(img, d, T, data, feats, p):
    rp.paste_country(img, feats, SIL_BOX, alpha=0.35 + 0.65 * _ease(p * 2))
    rp.draw_wordmark(d, T, y=360)
    wrap_center(d, 1300, T["title"], 64, INK, maxw=W - 140)


def scene_hook(img, d, T, data, feats, p):
    S, F = data["summary"], data["findings"]["H1"]
    fit_text(d, (W / 2, 400), T["hookKicker"], 48, DIM)
    d.text((W / 2, 520), str(sign_agree_og(data)), font=font(300),
           fill=AMBER, anchor="ma")
    fit_text(d, (W / 2, 880), placeholders(T["hookUnit"], n=S["n_og"]), 44, INK)
    if p > 0.35:
        wrap_center(d, 1060, placeholders(T["hookSub"], rho=rho_txt(F["rho"])),
                    42, DIM, maxw=W - 160)


def scene_h1(img, d, T, data, feats, p):
    fit_text(d, (W / 2, 340), T["h1Title"], 46, INK)
    F = data["findings"]["H1"]
    d.text((W / 2, 440), "ρ = " + rho_txt(F["rho"]), font=font(64), fill=AMBER, anchor="ma")
    scatter(d, points(data, "dO_9020", "dG_9020"), _ease(p / 0.6),
            T["h1X"], T["h1Y"], rp.DIV_POS[1], LIM_H1)


def scene_refuted(img, d, T, data, feats, p):
    F = data["findings"]["H2"]
    fit_text(d, (W / 2, 330), T["refutedKicker"], 50, AMBER)
    y = wrap_center(d, 410, T["refutedPred"], 34, DIM, maxw=W - 140)
    if p > 0.15:
        fit_text(d, (W / 2, y + 10), placeholders(T["refutedFact"], rho=rho_txt(F["rho"])),
                 44, INK)
    scatter(d, points(data, "dO_1319", "dL_1319"), _ease((p - 0.2) / 0.5),
            T["h2X"], T["h2Y"], AMBER, LIM_H2)


def scene_map(img, d, T, data, feats, p):
    fit_text(d, (W / 2, 330), T["mapTitle"], 52, INK)
    draw_map(img, feats, data)
    d = ImageDraw.Draw(img)
    fit_text(d, (W / 2, 1360), placeholders(T["mapCounter"], n=light_up_pop_down(data)),
             40, AMBER)
    fit_text(d, (W / 2, 1430), T["mapLegend"], 28, DIM)


def scene_finale(img, d, T, data, feats, p):
    rp.paste_country(img, feats, SIL_BOX, alpha=0.5)
    rp.draw_wordmark(d, T, y=360, kicker=False)
    wrap_center(d, 520, T["finaleNote"], 56, INK, maxw=W - 140)
    wrap_center(d, 1290, T["finaleCta"], 50, AMBER)
    fit_text(d, (W / 2, 1380), T["ctaUrl"], 32, INK)
    wrap_center(d, 1460, T["source"], 26, DIM, maxw=W - 160)


SCENES = {"intro": scene_intro, "hook": scene_hook, "scatterH1": scene_h1,
          "refuted": scene_refuted, "map": scene_map, "finale": scene_finale}


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
    SCENES[seg["scene"]](img, d, T, data, feats, p)
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
        dd = out_dir / f"reel_sensors_preview_{lang}"
        dd.mkdir(parents=True, exist_ok=True)
        for gi in range(0, total, dump_every):
            render_frame(gi, data, scene, feats, hatch, lang).save(dd / f"f{gi:05d}.png")
        print(f"OK: превью в {dd}")
        return
    ffmpeg = os.environ.get("FFMPEG", "ffmpeg")
    dst = out_dir / f"reel_sensors_{lang}.mp4"
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
