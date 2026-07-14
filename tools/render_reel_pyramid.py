#!/usr/bin/env python3
"""Рилс R-1 «Пирамида, которая переворачивается» (INF-11, P-12).

Кадры 1080x1920 из web/public/data/pyramids.json по хронометражу
tools/reel_pyramid_scene.json: хук (1959) -> морфинг 1959-2026 с
каллаутами (шрам войны, эхо, провал 90-х, перекос полов, основание) ->
будущее 2026-2075 с тремя сценариями-призраками -> финал-сравнение
трёх силуэтов + честная оговорка + CTA. Каждый модельный кадр несёт
бейдж «МОДЕЛЬ». Детерминированно; RU и BE мастера.

Запуск: python tools/render_reel_pyramid.py [--lang ru|be|all]
        [--dump-every N]   # превью-кадры вместо видео
Выход: build/reel_pyramid_<lang>.mp4 (CBR 12M, как в рилсах INF-08)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from etl.nightlights_frames import FONT_PATH  # noqa: E402  (вендоренный шрифт)

W, H = 1080, 1920
BG = (12, 12, 11)
INK = (238, 233, 222)
DIM = (150, 143, 130)
BLUE = (86, 152, 185)      # мужчины
COPPER = (215, 143, 87)    # женщины
POS = (77, 189, 110)       # оптимистичный
NEG = (224, 122, 104)      # негативный
AMBER = (240, 205, 150)

PYR_X, PYR_Y = 60, 430
PYR_W, PYR_H = W - 120, 1050
AXIS_W = 70


def font(sz: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_PATH), sz)


def fit_text(d: ImageDraw.ImageDraw, xy, text: str, sz: int, fill,
             maxw=W - 80, anchor="ma"):
    """Текст с ужатием под ширину кадра."""
    f = font(sz)
    while d.textlength(text, font=f) > maxw and sz > 22:
        sz -= 2
        f = font(sz)
    d.text(xy, text, font=f, fill=fill, anchor=anchor)


def wrap_center(d: ImageDraw.ImageDraw, y: int, text: str, sz: int, fill,
                maxw=W - 100, lh=1.35) -> int:
    """Многострочный центрированный текст по словам; возвращает низ."""
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


def load_data():
    d = json.loads((ROOT / "web/public/data/pyramids.json").read_text())
    scene = json.loads((ROOT / "tools/reel_pyramid_scene.json").read_text())
    return d, scene


def frame_for(data: dict, year: float, scn: str = "base") -> tuple[dict, str]:
    """Интерполированный кадр для дробного года + тип ближайшей серии."""
    s = data["series"]

    def rec(y: int):
        if y <= 2026:
            return s[str(min(max(y, 1959), 2026))]
        y5 = min(2075, max(2030, round(y / 5) * 5))
        return s[f"{y5}:{scn}"]

    y0 = int(year)
    if year <= 2026:
        r0, r1 = rec(y0), rec(min(y0 + 1, 2026))
        k = year - y0
    else:
        lo = min(2075, max(2030, int(year // 5) * 5))
        hi = min(2075, lo + 5)
        r0, r1 = s[f"{lo}:{scn}"], s[f"{hi}:{scn}"]
        k = 0 if hi == lo else (year - lo) / 5
    out = {sx: [a * (1 - k) + b * k for a, b in zip(r0[sx], r1[sx])]
           for sx in ("m", "f")}
    typ = (r0 if k < 0.5 else r1)["type"]
    return out, typ


def max_val(data: dict) -> float:
    m = 0
    for r in data["series"].values():
        m = max(m, max(r["m"]), max(r["f"]))
    return m


def draw_pyramid(d: ImageDraw.ImageDraw, rec: dict, mv: float,
                 groups: list[str], x=PYR_X, y=PYR_Y, w=PYR_W, h=PYR_H,
                 alpha_bars=True, outline_only=False, color_m=BLUE,
                 color_f=COPPER, labels=True):
    n = len(groups)
    row_h = h / n
    half = (w - AXIS_W) / 2
    for gi in range(n):
        ry = y + (n - 1 - gi) * row_h
        bm = rec["m"][gi] / mv * half
        bf = rec["f"][gi] / mv * half
        if outline_only:
            d.rectangle([x + half - bm, ry + 2, x + half, ry + row_h - 4],
                        outline=color_m, width=2)
            d.rectangle([x + half + AXIS_W, ry + 2,
                         x + half + AXIS_W + bf, ry + row_h - 4],
                        outline=color_f, width=2)
        else:
            d.rectangle([x + half - bm, ry + 2, x + half, ry + row_h - 4],
                        fill=color_m)
            d.rectangle([x + half + AXIS_W, ry + 2,
                         x + half + AXIS_W + bf, ry + row_h - 4],
                        fill=color_f)
        if labels and gi % 2 == 0:
            d.text((x + half + AXIS_W / 2, ry + row_h / 2), groups[gi],
                   font=font(24), fill=DIM, anchor="mm")


def cohort_rows(born_range, year, n=17):
    lo = max(0, min(int((year - born_range[1]) // 5), n - 1))
    hi = max(0, min(int((year - born_range[0]) // 5), n - 1))
    return range(min(lo, hi), max(lo, hi) + 1)


def render_frame(gi: int, fps: int, data, scene, lang: str,
                 mv: float) -> Image.Image:
    t = gi / fps
    T = scene["texts"][lang]
    groups = data["age_groups"]
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    seg = next(s for s in scene["timeline"]
               if s["t"][0] <= t < s["t"][1] or s is scene["timeline"][-1])
    k = (t - seg["t"][0]) / (seg["t"][1] - seg["t"][0])
    k = min(max(k, 0), 1)
    year = seg["year"][0] + (seg["year"][1] - seg["year"][0]) * k
    scene_id = seg["scene"]

    if scene_id == "finale":
        # три силуэта 2075 рядом
        y = wrap_center(d, 170, T["finale1"], 48, INK)
        wrap_center(d, y + 12, T["finale2"], 48, AMBER)
        mw, mh = 300, 700
        for i, (scn, col) in enumerate(
                (("optimistic", POS), ("base", AMBER), ("negative", NEG))):
            rec, _ = frame_for(data, 2075, scn)
            x0 = 60 + i * 330
            draw_pyramid(d, rec, mv, groups, x=x0, y=480, w=mw, h=mh,
                         color_m=col, color_f=col, labels=False)
            d.text((x0 + mw / 2, 480 + mh + 24), T["scenarios"][scn],
                   font=font(34), fill=col, anchor="ma")
            tot = sum(rec["m"]) + sum(rec["f"])
            d.text((x0 + mw / 2, 480 + mh + 70),
                   f"{tot / 1e6:.1f} {'млн' if lang == 'ru' else 'млн'}",
                   font=font(38), fill=INK, anchor="ma")
        wrap_center(d, 1400, T["disclaimer"], 30, DIM)
        fit_text(d, (W / 2, 1560), T["cta"], 40, INK)
        fit_text(d, (W / 2, 1622), T["ctaUrl"], 34, AMBER)
        d.line([(0, H - 6), (W * t / scene["format"]["durationSec"], H - 6)],
               fill=AMBER, width=6)
        return img

    rec, typ = frame_for(data, year, "base")

    # шапка
    d.text((W / 2, 90), str(int(round(year))), font=font(110), fill=INK,
           anchor="ma")
    d.text((W / 2, 235), T["typeLabels"].get(typ, typ), font=font(34),
           fill=AMBER if typ == "model" else DIM, anchor="ma")
    if scene_id == "hook":
        d.text((W / 2, 300), T["hook1"], font=font(50), fill=INK, anchor="ma")
        d.text((W / 2, 365), T["hook2"], font=font(50), fill=AMBER,
               anchor="ma")
    d.text((PYR_X + (PYR_W - AXIS_W) / 4, 360), T["menLabel"],
           font=font(32), fill=BLUE, anchor="ma")
    d.text((PYR_X + PYR_W - (PYR_W - AXIS_W) / 4, 360), T["womenLabel"],
           font=font(32), fill=COPPER, anchor="ma")

    # призраки сценариев в будущем
    if scene_id == "future" and year > 2027:
        for scn, col in (("optimistic", POS), ("negative", NEG)):
            grec, _ = frame_for(data, year, scn)
            draw_pyramid(d, grec, mv, groups, outline_only=True,
                         color_m=col, color_f=col, labels=False)
    draw_pyramid(d, rec, mv, groups)

    if typ == "model":
        f1 = font(34)
        tw = d.textlength(T["modelBadge"], font=f1)
        d.rectangle([W - tw - 60, PYR_Y - 68, W - 24, PYR_Y - 22],
                    fill=(30, 24, 16))
        d.text((W - 42, PYR_Y - 61), T["modelBadge"], font=f1, fill=AMBER,
               anchor="ra")

    # каллауты
    for c in scene["callouts"][lang]:
        if not (c["t"][0] <= t < c["t"][1]):
            continue
        n = len(groups)
        row_h = PYR_H / n
        if "cohortBorn" in c:
            rows = cohort_rows(c["cohortBorn"], year)
        elif "groupsTop" in c:
            rows = range(n - c["groupsTop"], n)
        else:
            rows = range(0, c.get("groupsBottom", 1))
        y0 = PYR_Y + (n - 1 - max(rows)) * row_h
        y1 = PYR_Y + (n - min(rows)) * row_h
        d.rectangle([PYR_X - 8, y0, PYR_X + PYR_W + 8, y1],
                    outline=AMBER, width=4)
        ty = max(360, y0 - 64)
        f1 = font(40)
        tw = d.textlength(c["text"], font=f1)
        d.rectangle([W / 2 - tw / 2 - 16, ty - 6, W / 2 + tw / 2 + 16,
                     ty + 50], fill=(30, 24, 16))
        d.text((W / 2, ty), c["text"], font=f1, fill=AMBER, anchor="ma")

    # сценарные подписи в будущем
    if scene_id == "future" and year > 2027:
        y0 = PYR_Y + PYR_H + 60
        for i, (scn, col) in enumerate(
                (("optimistic", POS), ("base", AMBER), ("negative", NEG))):
            d.text((W / 2 + (i - 1) * 300, y0), T["scenarios"][scn],
                   font=font(34), fill=col, anchor="ma")

    d.line([(0, H - 6), (W * t / scene["format"]["durationSec"], H - 6)],
           fill=AMBER, width=6)
    return img


def render(lang: str, dump_every: int) -> None:
    data, scene = load_data()
    fps = scene["format"]["fps"]
    total = int(scene["format"]["durationSec"] * fps)
    mv = max_val(data)
    out_dir = ROOT / "build"
    out_dir.mkdir(exist_ok=True)

    if dump_every:
        dd = out_dir / f"reel_pyramid_preview_{lang}"
        dd.mkdir(parents=True, exist_ok=True)
        for gi in range(0, total, dump_every):
            render_frame(gi, fps, data, scene, lang, mv).save(
                dd / f"f{gi:05d}.png")
        print(f"OK: превью в {dd}")
        return

    dst = out_dir / f"reel_pyramid_{lang}.mp4"
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
        img = render_frame(gi, fps, data, scene, lang, mv)
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
