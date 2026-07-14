#!/usr/bin/env python3
"""Instagram-рилс «Пирамида» (негативный сценарий) — согласованная
с автором версия с полноэкранными модальными окнами.

Отличия от базового R-1 (render_reel_pyramid.py):
- модальные окна: фон уходит в туман (blur + затемнение), год замирает,
  карточка почти на весь экран с крупным текстом (5 c чтения,
  fade 0,4 c) — шесть модалок, включая «Где мужчины?»;
- контур Беларуси едва заметной подложкой позади пирамиды;
- цветовая драматургия: в модельном сегменте 2026-2075 палитра
  выцветает к «пустынной» серой по мере падения населения
  (9,1 -> 4,3 млн), красный - только акцент (бейдж сценария, счётчик);
- честная оговорка и CTA в финале.

Запуск: python tools/render_reel_pyramid_ig.py [--lang ru]
        [--dump-every N]
Выход: build/reel_pyramid_ig_ru.mp4 (1080x1920, 30 fps, CBR 12M)
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import render_reel_pyramid as R  # noqa: E402  (общие примитивы)

W, H = R.W, R.H
GREY = (150, 143, 133)          # «пустынный» тон выцветания
OUTLINE_COL = (44, 43, 40)      # контур Беларуси (едва заметный)


def lerp_color(c1, c2, k: float):
    return tuple(round(a + (b - a) * k) for a, b in zip(c1, c2))


def load_outline() -> list[list[tuple[float, float]]]:
    """Внешние кольца областей -> контур страны в координатах кадра."""
    g = json.loads(
        (ROOT / "web/public/data/geo/adm1.geojson").read_text())
    rings = []
    lons, lats = [], []
    for f in g["features"]:
        polys = (f["geometry"]["coordinates"]
                 if f["geometry"]["type"] == "MultiPolygon"
                 else [f["geometry"]["coordinates"]])
        for p in polys:
            rings.append(p[0])
            for lon, lat in p[0]:
                lons.append(lon)
                lats.append(lat)
    w0, e0, s0, n0 = min(lons), max(lons), min(lats), max(lats)
    kx = math.cos(math.radians((s0 + n0) / 2))
    aspect = ((e0 - w0) * kx) / (n0 - s0)
    # вписываем в зону пирамиды
    bw = R.PYR_W * 0.94
    bh = bw / aspect
    bx = (W - bw) / 2
    by = R.PYR_Y + (R.PYR_H - bh) / 2
    out = []
    for ring in rings:
        out.append([(bx + (lon - w0) / (e0 - w0) * bw,
                     by + (n0 - lat) / (n0 - s0) * bh)
                    for lon, lat in ring])
    return out


def fade_palette(total: float) -> tuple[tuple, tuple, float]:
    """(цвет М, цвет Ж, k выцветания) по населению кадра: 9,06 млн ->
    полный цвет, 4,33 млн -> пустынный серый."""
    k = (9.06e6 - total) / (9.06e6 - 4.33e6)
    k = min(max(k, 0.0), 1.0) * 0.8      # не до полной серости
    return (lerp_color(R.BLUE, GREY, k),
            lerp_color(R.COPPER, GREY, k), k)


def draw_base(d, img, data, scene, year: float, mv, groups, seg,
              outline) -> None:
    """Обычный кадр: контур страны, шапка, пирамида, подсветки."""
    scn = scene["scenario"]
    T = scene["texts"]
    is_model = year > 2026
    rec, typ = R.frame_for(data, year, scn if is_model else "base")
    total = sum(rec["m"]) + sum(rec["f"])

    # контур Беларуси подложкой
    for ring in outline:
        d.line(ring + [ring[0]], fill=OUTLINE_COL, width=3)

    cm, cf, fade = (R.BLUE, R.COPPER, 0.0)
    if is_model:
        cm, cf, fade = fade_palette(total)

    d.text((W / 2, 84), str(int(round(year))), font=R.font(110),
           fill=R.INK, anchor="ma")
    if is_model:
        badge_col = lerp_color(R.AMBER, R.NEG, min(fade * 1.4, 1.0))
        d.text((W / 2, 232), T["scenarioBadge"], font=R.font(36),
               fill=badge_col, anchor="ma")
    else:
        d.text((W / 2, 232), T["typeLabels"].get(typ, typ),
               font=R.font(34), fill=R.DIM, anchor="ma")
    d.text((R.PYR_X + (R.PYR_W - R.AXIS_W) / 4, 350), T["menLabel"],
           font=R.font(32), fill=cm, anchor="ma")
    d.text((R.PYR_X + R.PYR_W - (R.PYR_W - R.AXIS_W) / 4, 350),
           T["womenLabel"], font=R.font(32), fill=cf, anchor="ma")

    R.draw_pyramid(d, rec, mv, groups, color_m=cm, color_f=cf)

    # подсветка когорты/групп в истории
    n = len(groups)
    row_h = R.PYR_H / n
    rows = None
    if seg.get("highlightBorn"):
        rows = R.cohort_rows(tuple(seg["highlightBorn"]), year)
    elif seg.get("highlightTop"):
        rows = range(n - seg["highlightTop"], n)
    if rows is not None:
        y0 = R.PYR_Y + (n - 1 - max(rows)) * row_h
        y1 = R.PYR_Y + (n - min(rows)) * row_h
        d.rectangle([R.PYR_X - 8, y0, R.PYR_X + R.PYR_W + 8, y1],
                    outline=R.AMBER, width=4)

    # счётчик населения (в модели наливается тревожным)
    cnt_col = R.INK if not is_model else \
        lerp_color(R.INK, R.NEG, min(fade * 1.2, 1.0))
    d.text((W / 2, R.PYR_Y + R.PYR_H + 46),
           f"{total / 1e6:.1f} {T['million']}",
           font=R.font(46), fill=cnt_col, anchor="ma")

    if scene_hook := (seg["scene"] == "hook"):
        _ = scene_hook
        d.text((W / 2, 300), T["hook1"], font=R.font(50), fill=R.INK,
               anchor="ma")
        d.text((W / 2, 366), T["hook2"], font=R.font(50), fill=R.AMBER,
               anchor="ma")


def draw_modal(img: Image.Image, scene, modal_id: str,
               k_fade: float) -> Image.Image:
    """Модалка поверх кадра: туман по k_fade (0..1) + карточка."""
    m = scene["modals"][modal_id]
    blur = img.filter(ImageFilter.GaussianBlur(10 * k_fade))
    dim = ImageEnhance.Brightness(blur).enhance(1 - 0.55 * k_fade)
    if k_fade < 1:
        img = Image.blend(img, dim, k_fade)
    else:
        img = dim
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    mx0, my0, mx1, my1 = 70, 470, W - 70, 1380
    alpha = round(255 * k_fade)
    cd.rounded_rectangle([mx0, my0, mx1, my1], radius=28,
                         fill=(26, 26, 25, alpha),
                         outline=(*R.AMBER, alpha), width=3)
    cd.text(((mx0 + mx1) / 2, my0 + 56), m["title"], font=R.font(64),
            fill=(*R.AMBER, alpha), anchor="ma")
    f = R.font(42)
    words, lines, cur = m["text"].split(), [], ""
    for wd in words:
        t2 = (cur + " " + wd).strip()
        if cd.textlength(t2, font=f) <= (mx1 - mx0 - 120) or not cur:
            cur = t2
        else:
            lines.append(cur)
            cur = wd
    lines.append(cur)
    yy = my0 + 178
    for ln in lines:
        cd.text(((mx0 + mx1) / 2, yy), ln, font=f,
                fill=(*R.INK, alpha), anchor="ma")
        yy += 62
    cd.text(((mx0 + mx1) / 2, my1 - 88), m["context"], font=R.font(32),
            fill=(*R.DIM, alpha), anchor="ma")
    return Image.alpha_composite(img.convert("RGBA"), card).convert("RGB")


def render_frame(gi: int, fps: int, data, scene, mv, groups,
                 outline) -> Image.Image:
    t = gi / fps
    T = scene["texts"]
    dur = scene["format"]["durationSec"]
    seg = next(s for s in scene["timeline"]
               if s["t"][0] <= t < s["t"][1] or s is scene["timeline"][-1])
    k = (t - seg["t"][0]) / (seg["t"][1] - seg["t"][0])
    k = min(max(k, 0.0), 1.0)
    year = seg["year"][0] + (seg["year"][1] - seg["year"][0]) * k

    img = Image.new("RGB", (W, H), R.BG)
    d = ImageDraw.Draw(img)
    draw_base(d, img, data, scene, year, mv, groups, seg, outline)

    if seg["scene"] == "modal":
        fade = scene["modalFadeSec"]
        tt = t - seg["t"][0]
        rest = seg["t"][1] - t
        k_fade = min(tt / fade, rest / fade, 1.0)
        k_fade = min(max(k_fade, 0.0), 1.0)
        img = draw_modal(img, scene, seg["modal"], k_fade)
        d = ImageDraw.Draw(img)

    if seg["scene"] == "finale":
        # оговорка + CTA поверх финального кадра (ниже счётчика)
        R.wrap_center(d, 1620, T["disclaimer"], 30, R.DIM)
        R.fit_text(d, (W / 2, 1730), T["cta"], 38, R.INK)
        R.fit_text(d, (W / 2, 1790), T["ctaUrl"], 36, R.AMBER)

    d.line([(0, H - 6), (W * t / dur, H - 6)], fill=R.AMBER, width=6)
    return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="ru", choices=["ru"])
    ap.add_argument("--dump-every", type=int, default=0)
    args = ap.parse_args()

    data, _ = R.load_data()
    scene = json.loads(
        (ROOT / "tools/reel_pyramid_ig_scene.json").read_text())
    fps = scene["format"]["fps"]
    total = int(scene["format"]["durationSec"] * fps)
    mv = R.max_val(data)
    groups = data["age_groups"]
    outline = load_outline()
    out_dir = ROOT / "build"
    out_dir.mkdir(exist_ok=True)

    if args.dump_every:
        dd = out_dir / "reel_pyramid_ig_preview"
        dd.mkdir(parents=True, exist_ok=True)
        for gi in range(0, total, args.dump_every):
            render_frame(gi, fps, data, scene, mv, groups, outline).save(
                dd / f"f{gi:05d}.png")
        print(f"OK: превью в {dd}")
        return

    dst = out_dir / f"reel_pyramid_ig_{args.lang}.mp4"
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
        img = render_frame(gi, fps, data, scene, mv, groups, outline)
        proc.stdin.write(np.asarray(img, dtype="uint8").tobytes())
        if gi % 300 == 0:
            print(f"  кадр {gi}/{total}")
    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        raise SystemExit("ffmpeg error")
    print(f"OK: {dst} ({dst.stat().st_size / 1e6:.1f} МБ)")


if __name__ == "__main__":
    main()
