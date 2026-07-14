#!/usr/bin/env python3
"""Рендер рилса Nightlights v3 (кодовый pipeline, аналог Remotion).

reel_story.json — единственный источник структуры: сцены, тайминги,
слои, тексты, маркировка. Кадры детерминированы (сеяно), субтитры
вшиваются из той же разбивки, что SRT/VTT (data/captions_timing.json).
Числа кейсов берутся из research_candidates.json и показываются только
при releaseApproved=true; национальные значения 2075 года подставляются
автоматически из forecast.json.

Запуск (требует numpy+Pillow+ffmpeg; поля - после etl.nightlights_visual
и etl.nightlights_demo):
  python video/nightlights-reel/render.py                # видео без звука
  python video/nightlights-reel/render.py --dump-every 45  # превью-кадры
Дальше mix_audio.py собирает voice/silent-версии.
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from etl.nightlights_frames import lut, VMAX, VNL_GAMMA, SEED, FONT_PATH  # noqa: E402

FIELDS = ROOT / "data" / "tmp" / "nl_fields"
NL = ROOT / "web" / "public" / "data" / "nightlights"

W, H = 1080, 1920
MAP_Y, MAP_W = 300, 1080

BG = (5, 4, 3)
INK = (238, 230, 214)
DIM = (150, 138, 118)
AMBER = (240, 205, 150)
BLUE = (86, 152, 185)
NEG = (224, 122, 104)
POS = (77, 189, 110)


def font(sz: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_PATH), sz)


class Ctx:
    """Общий контекст сцен: поля, геометрия, данные, помощники."""

    def __init__(self, captions="data/captions_timing.json"):
        self.story = json.loads((HERE / "data/reel_story.json").read_text())
        self.captions = json.loads((HERE / captions).read_text())
        self.night = json.loads(
            (ROOT / "web/public/data/nightlights_v2.json").read_text())
        self.cands = {c["id"]: c for c in json.loads(
            (NL / "research_candidates.json").read_text())["candidates"]}
        self.manifest = json.loads(
            (NL / "nightlights_manifest.json").read_text())
        fc = json.loads((ROOT / "web/public/data/forecast.json").read_text())
        by = fc["territories"]["BY"]
        self.nat2075 = {s: by[s]["pop"][-1] for s in
                        ("optimistic", "base", "negative")}
        self.table = lut()
        self.bounds = self.manifest["grid"]["bounds"]
        gw, gh = self.manifest["grid"]["width"], self.manifest["grid"]["height"]
        self.gw, self.gh = gw, gh
        kx = math.cos(math.radians((self.bounds[1] + self.bounds[3]) / 2))
        self.map_aspect = ((self.bounds[2] - self.bounds[0]) * kx) \
            / (self.bounds[3] - self.bounds[1])
        self.map_h = round(MAP_W / self.map_aspect)
        self._cache: dict[str, np.ndarray] = {}
        self._geo = None
        self.qr = Image.open(
            ROOT / "data/raw/nightlights/qr_nightlights.png")
        self.ui = Image.open(HERE / "data/ui_screenshot.png").convert("RGB")
        self.rng = np.random.default_rng(SEED + 33)

    # ---- поля и карта ----
    def field(self, key: str) -> np.ndarray:
        if key not in self._cache:
            if len(self._cache) > 8:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = np.load(FIELDS / f"{key}.npy").astype("float64")
        return self._cache[key]

    def norm(self, a: np.ndarray) -> np.ndarray:
        v = np.log1p(np.clip(a, 0, VMAX)) / math.log1p(VMAX)
        return np.clip(v, 0, 1) ** VNL_GAMMA

    def map_img(self, v: np.ndarray, w=MAP_W, h=None) -> Image.Image:
        h = h or self.map_h
        x = np.clip(v * 255 + self.rng.uniform(-0.8, 0.8, v.shape), 0, 255)
        img = Image.fromarray(x.astype("uint8"), "P")
        img.putpalette(self.table.flatten().tolist())
        return img.convert("RGB").resize((w, h), Image.Resampling.BILINEAR)

    def crop_map(self, v: np.ndarray, lon0, lat0, lon1, lat1,
                 w, h) -> Image.Image:
        """Зум-кроп поля по гео-рамке."""
        W0, S0, E0, N0 = self.bounds
        x0 = int((lon0 - W0) / (E0 - W0) * self.gw)
        x1 = int((lon1 - W0) / (E0 - W0) * self.gw)
        y0 = int((N0 - lat1) / (N0 - S0) * self.gh)
        y1 = int((N0 - lat0) / (N0 - S0) * self.gh)
        sub = v[max(y0, 0):y1, max(x0, 0):x1]
        x = np.clip(sub * 255, 0, 255)
        img = Image.fromarray(x.astype("uint8"), "P")
        img.putpalette(self.table.flatten().tolist())
        return img.convert("RGB").resize((w, h), Image.Resampling.BILINEAR)

    def to_map_xy(self, lon, lat, y_off=MAP_Y, w=MAP_W, h=None):
        h = h or self.map_h
        W0, S0, E0, N0 = self.bounds
        return ((lon - W0) / (E0 - W0) * w,
                y_off + (N0 - lat) / (N0 - S0) * h)

    def geo(self):
        if self._geo is None:
            g2 = json.loads(
                (ROOT / "web/public/data/geo/adm2.geojson").read_text())
            g1 = json.loads(
                (ROOT / "web/public/data/geo/adm1.geojson").read_text())
            feats = {f["properties"]["id"]: f for f in g2["features"]}
            feats.update({f["properties"]["id"]: f for f in g1["features"]})
            self._geo = {}
            for zid, f in feats.items():
                polys = (f["geometry"]["coordinates"]
                         if f["geometry"]["type"] == "MultiPolygon"
                         else [f["geometry"]["coordinates"]])
                self._geo[zid] = [p[0] for p in polys]
        return self._geo

    def outline(self, d: ImageDraw.ImageDraw, zid: str, color,
                width=4, y_off=MAP_Y):
        for ring in self.geo().get(zid, []):
            pts = [self.to_map_xy(lon, lat, y_off) for lon, lat in ring]
            d.line(pts + [pts[0]], fill=color, width=width)

    # ---- текст ----
    def center(self, d, text, y, sz, fill=INK, maxw=W - 100):
        f = font(sz)
        while d.textlength(text, font=f) > maxw and sz > 28:
            sz -= 3
            f = font(sz)
        d.text((W / 2, y), text, font=f, fill=fill, anchor="ma")
        return sz

    def subtitles(self, d, t: float):
        for c in self.captions:
            if c["start"] <= t < c["end"]:
                y = H - 210
                for ln in c["lines"]:
                    self.center(d, ln, y, 44, fill=INK)
                    y += 56
                return

    def badge(self, d, text, y=MAP_Y + 12, fill=DIM):
        f = font(30)
        tw = d.textlength(text, font=f)
        d.rectangle([16, y, 16 + tw + 20, y + 44], fill=(16, 11, 7))
        d.text((26, y + 6), text, font=f, fill=fill)

    def demo_marking(self, d):
        lines = ["УСИЛЕННАЯ ВИЗУАЛИЗАЦИЯ", "ДЕМОГРАФИЧЕСКОЙ КОНЦЕНТРАЦИИ",
                 "не прогноз спутникового радианса"]
        f1, f2 = font(34), font(27)
        wmax = max(d.textlength(lines[0], font=f1),
                   d.textlength(lines[1], font=f1),
                   d.textlength(lines[2], font=f2))
        x0 = W - wmax - 40
        d.rectangle([x0 - 10, MAP_Y + 8, W - 12, MAP_Y + 128],
                    fill=(16, 11, 7))
        d.text((x0, MAP_Y + 14), lines[0], font=f1, fill=AMBER)
        d.text((x0, MAP_Y + 50), lines[1], font=f1, fill=AMBER)
        d.text((x0, MAP_Y + 92), lines[2], font=f2, fill=DIM)

    def qr_block(self, img: Image.Image, d, size=260, y=None):
        y = y if y is not None else H - 560
        qr = self.qr.resize((size, size))
        img.paste(qr, ((W - size) // 2, y))
        d.text((W / 2, y + size + 10),
               "bymaps · /research/nightlights?case=…",
               font=font(30), fill=DIM, anchor="ma")


def ease(p: float) -> float:
    return p * p * (3 - 2 * p)


def load_scenes(ctx: Ctx):
    scenes = []
    for sc in ctx.story["scenes"]:
        mod = importlib.import_module(f"scenes.{sc['module']}")
        scenes.append((sc, mod.render))
    return scenes


def compose(ctx: Ctx, scenes, gi: int) -> Image.Image:
    """Кадр gi: сцена + QR-оверлеп + субтитры + прогресс."""
    fps = ctx.story["format"]["fps"]
    dur = ctx.story["format"]["durationSec"]
    t = gi / fps
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for sc, fn in scenes:
        if sc["start"] <= t < sc["end"] or (sc is scenes[-1][0]
                                            and t >= sc["end"]):
            p = (t - sc["start"]) / (sc["end"] - sc["start"])
            fn(ctx, img, d, min(max(p, 0.0), 1.0), t)
            break
    cta = ctx.story["scenes"][-1]
    if cta["qrOverlapFromSec"] <= t < cta["start"]:
        qr = ctx.qr.resize((150, 150))
        img.paste(qr, (W - 170, H - 320))
    ctx.subtitles(d, t)
    d.line([(0, H - 4), (W * t / dur, H - 4)], fill=AMBER, width=4)
    return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump-every", type=int, default=0)
    ap.add_argument("--out", default="renders/nightlights_reel_v3_video.mp4")
    ap.add_argument("--captions", default="data/captions_timing.json",
                    help="файл таймингов субтитров (condensed для "
                         "voice-версии)")
    args = ap.parse_args()

    ctx = Ctx(args.captions)
    fps = ctx.story["format"]["fps"]
    dur = ctx.story["format"]["durationSec"]
    total = int(dur * fps)
    scenes = load_scenes(ctx)

    def frame(gi: int) -> Image.Image:
        return compose(ctx, scenes, gi)

    if args.dump_every:
        dd = HERE / "renders" / "preview"
        dd.mkdir(parents=True, exist_ok=True)
        for gi in range(0, total, args.dump_every):
            frame(gi).save(dd / f"f{gi:05d}.png")
        print(f"OK: превью в {dd}")
        return

    dst = HERE / args.out
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-c:v", "libx264", "-preset", "slow", "-crf", "17",
           "-pix_fmt", "yuv420p", str(dst)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    for gi in range(total):
        proc.stdin.write(np.asarray(frame(gi), dtype="uint8").tobytes())
        if gi % 300 == 0:
            print(f"  кадр {gi}/{total}")
    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        raise SystemExit("ffmpeg error")
    print(f"OK: {dst} ({dst.stat().st_size / 1e6:.1f} МБ)")


if __name__ == "__main__":
    main()
