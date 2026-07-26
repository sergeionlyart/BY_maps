#!/usr/bin/env python3
"""Рилс INF-15 «Полотно»: собирается из тех же данных, что и страница
(web/public/data/grid_frames/*.webp + grid.json + network_metrics.json),
не рисуется руками.

35-45 c, 1080x1920, RU/BE. Таймлапс 1975->2050 (наблюдаемые кадры + база/
вариант A прогноза), счётчик area_share_below(5), точка центра масс,
финальный choropleth "метры дорог на жителя", титры честности (GHS-POP -
производная официальных данных; прогнозные ячейки - модель). Наблюдаемая
и модельная части визуально различаются штриховкой (те же кадры, что уже
несут бейдж "МОДЕЛЬ" - см. etl/grid_frames.py).

Запуск (требует numpy, Pillow, ffmpeg в PATH; rasterio - только для
финального choropleth дорог):
  python tools/render_reel_grid.py --lang ru
  python tools/render_reel_grid.py --lang be --dump-frames build/reels/grid_be_preview --dump-every 30
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from etl.common import ROOT, OUT                      # noqa: E402

SCENE = json.loads((ROOT / "tools" / "reel_grid_scene.json").read_text())
FRAMES = OUT / "grid_frames"
META = json.loads((FRAMES / "meta.json").read_text())
GRID = json.loads((OUT / "grid.json").read_text())
NET_PATH = ROOT / "data" / "raw" / "grid" / "network_metrics.json"
NET = json.loads(NET_PATH.read_text()) if NET_PATH.exists() else None
FONT = ROOT / "data" / "raw" / "nightlights" / "fonts" / "DejaVuSans.ttf"

W, H = SCENE["size"]
FPS = SCENE["fps"]

BG = (8, 8, 24)
INK = (250, 253, 250)
DIM = (160, 175, 185)
ACCENT = (60, 165, 175)
NEG = (224, 122, 104)


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT), size)


def load_frame(key: str) -> Image.Image:
    name = GRID["frames"][key].split("/")[-1]
    img = Image.open(FRAMES / name).convert("RGB")
    return img


def fit_into(img: Image.Image, w: int, h: int) -> Image.Image:
    """Вписывает изображение в прямоугольник w x h с сохранением пропорций,
    дополняя фон BG (letterbox) - как object-fit: contain."""
    src_w, src_h = img.size
    scale = min(w / src_w, h / src_h)
    nw, nh = int(src_w * scale), int(src_h * scale)
    resized = img.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (w, h), BG)
    canvas.paste(resized, ((w - nw) // 2, (h - nh) // 2))
    return canvas, (w - nw) // 2, (h - nh) // 2, scale


def lonlat_to_map_px(lon: float, lat: float, offset_x: int, offset_y: int,
                      scale: float) -> tuple[float, float]:
    w0, s0, e0, n0 = META["bounds_lonlat"]
    fx = (lon - w0) / (e0 - w0)
    fy = (n0 - lat) / (n0 - s0)
    px = fx * META["width"] * scale + offset_x
    py = fy * META["height"] * scale + offset_y
    return px, py


def centroid_at(year: float) -> tuple[float, float]:
    track = sorted(GRID["national"]["centroid_track"], key=lambda p: p["year"])
    if year <= track[0]["year"]:
        p = track[0]
        return p["lon"], p["lat"]
    for a, b in zip(track, track[1:]):
        if a["year"] <= year <= b["year"]:
            t = (year - a["year"]) / (b["year"] - a["year"]) if b["year"] != a["year"] else 0
            return a["lon"] + (b["lon"] - a["lon"]) * t, a["lat"] + (b["lat"] - a["lat"]) * t
    p = track[-1]
    return p["lon"], p["lat"]


def below5_at(key: str) -> float:
    d = GRID["national"]["area_share_below"]["5"]
    return d.get(key, list(d.values())[0])


def draw_text_center(d: ImageDraw.ImageDraw, cx: int, y: int, text: str,
                      size: int, fill=INK, bold_font=None) -> None:
    f = bold_font or font(size)
    bbox = d.textbbox((0, 0), text, font=f)
    w = bbox[2] - bbox[0]
    d.text((cx - w / 2, y), text, font=f, fill=fill)


class Reel:
    def __init__(self, lang: str):
        self.lang = lang
        self.t = SCENE["text"][lang]
        self.keyframes = SCENE["keyframes"]
        self.fps = FPS
        self.sections = self._build_sections()

    def _build_sections(self):
        s = []
        s.append({"kind": "brand", "frames": int(SCENE["brand_s"] * self.fps)})
        for i, kf in enumerate(self.keyframes):
            hold = SCENE["hold_forecast_s"] if kf["dtype"] == "f" else SCENE["hold_observed_s"]
            s.append({"kind": "keyframe", "frames": int(hold * self.fps), "idx": i})
            if i < len(self.keyframes) - 1:
                s.append({"kind": "transition", "frames": int(SCENE["transition_s"] * self.fps), "idx": i})
        s.append({"kind": "network", "frames": int(SCENE["network_s"] * self.fps)})
        s.append({"kind": "disclaimer", "frames": int(SCENE["disclaimer_s"] * self.fps)})
        return s

    def total_frames(self) -> int:
        return sum(s["frames"] for s in self.sections)

    def _cached_frame(self, key: str):
        if not hasattr(self, "_cache"):
            self._cache = {}
        if key not in self._cache:
            img = load_frame(key)
            canvas, ox, oy, scale = fit_into(img, W, int(H * 0.62))
            self._cache[key] = (canvas, ox, oy, scale)
        return self._cache[key]

    def _network_frame(self):
        if hasattr(self, "_net_cache"):
            return self._net_cache
        canvas = Image.new("RGB", (W, int(H * 0.62)), BG)
        if NET is not None:
            try:
                canvas = self._render_network_choropleth()
            except Exception:
                pass
        self._net_cache = canvas
        return canvas

    def _render_network_choropleth(self) -> Image.Image:
        import rasterio
        from etl.grid import zone_labels, RASTERS_CONSTRAINED, _adm_geoms_moll
        ids, feats, raions, minsk = _adm_geoms_moll()
        ref = RASTERS_CONSTRAINED / "pop_2020.tif"
        labels, ids2, transform, crs = zone_labels(ref)
        vals = np.zeros(len(ids) + 1)
        territories = NET["territories"]
        arr = [territories.get(tid, {}).get("road_km_per_1000") or 0 for tid in ids]
        vmax = max(arr) if arr else 1
        for i, tid in enumerate(ids):
            v = territories.get(tid, {}).get("road_km_per_1000") or 0
            vals[i + 1] = v / vmax if vmax else 0
        color_idx = np.clip(vals[labels], 0, 1)
        lut = np.zeros((256, 3), dtype="uint8")
        stops = [(0.0, (10, 30, 20)), (0.5, (90, 130, 60)), (1.0, (230, 90, 60))]
        t = np.linspace(0, 1, 256)
        for c in range(3):
            xs = [s[0] for s in stops]
            ys = [s[1][c] for s in stops]
            lut[:, c] = np.clip(np.interp(t, xs, ys), 0, 255).astype("uint8")
        idx8 = np.clip((color_idx * 255).astype("uint8"), 0, 255)
        rgb = lut[idx8]
        mask = labels > 0
        rgb[~mask] = BG
        img = Image.fromarray(rgb, "RGB")
        canvas, *_ = fit_into(img, W, int(H * 0.62))
        return canvas

    def frame(self, gi: int) -> Image.Image:
        acc = 0
        for sec in self.sections:
            if gi < acc + sec["frames"]:
                local = gi - acc
                return self._render(sec, local)
            acc += sec["frames"]
        return self._render(self.sections[-1], 0)

    def _render(self, sec, local: int) -> Image.Image:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)

        if sec["kind"] == "brand":
            draw_text_center(d, W // 2, int(H * 0.42), self.t["brand_title"], 64, bold_font=font(64))
            draw_text_center(d, W // 2, int(H * 0.42) + 90, self.t["brand_sub"], 26, fill=DIM)
            draw_text_center(d, W // 2, int(H * 0.55), self.t["title"], 88, fill=ACCENT, bold_font=font(88))
            draw_text_center(d, W // 2, int(H * 0.55) + 110, self.t["subtitle"], 30, fill=INK)
            return img

        if sec["kind"] in ("keyframe", "transition"):
            if sec["kind"] == "keyframe":
                kf = self.keyframes[sec["idx"]]
                canvas, ox, oy, scale = self._cached_frame(kf["key"])
                alpha = 1.0
                year_disp = kf["year"]
                below5 = below5_at(kf["key"])
                is_model = kf["dtype"] == "f"
            else:
                kf_a = self.keyframes[sec["idx"]]
                kf_b = self.keyframes[sec["idx"] + 1]
                ca, oxa, oya, sa = self._cached_frame(kf_a["key"])
                cb, oxb, oyb, sb = self._cached_frame(kf_b["key"])
                t = local / max(1, sec["frames"])
                canvas = Image.blend(ca, cb, t)
                ox, oy, scale = oxa, oya, sa
                year_disp = kf_a["year"] + (kf_b["year"] - kf_a["year"]) * t
                below5 = below5_at(kf_a["key"]) + (below5_at(kf_b["key"]) - below5_at(kf_a["key"])) * t
                is_model = kf_b["dtype"] == "f"

            img.paste(canvas, (0, int(H * 0.14)))
            oy_abs = oy + int(H * 0.14)

            lon, lat = centroid_at(year_disp)
            px, py = lonlat_to_map_px(lon, lat, ox, oy_abs, scale)
            r = 7
            d.ellipse([px - r, py - r, px + r, py + r], fill=(224, 102, 63), outline=INK, width=2)

            draw_text_center(d, W // 2, 60, f"{year_disp:.0f}", 84, bold_font=font(84))
            if is_model:
                draw_text_center(d, W // 2, 155, self.t["model_badge"], 24, fill=(180, 150, 230))

            below5_y = int(H * 0.80)
            draw_text_center(d, W // 2, below5_y, f"{below5*100:.1f}%", 56, fill=NEG, bold_font=font(56))
            draw_text_center(d, W // 2, below5_y + 62, self.t["counter_label"], 22, fill=DIM)
            return img

        if sec["kind"] == "network":
            canvas = self._network_frame()
            img.paste(canvas, (0, int(H * 0.14)))
            draw_text_center(d, W // 2, 60, self.t["network_title"], 46, bold_font=font(46), fill=INK)
            draw_text_center(d, W // 2, int(H * 0.80), self.t["network_sub"], 26, fill=INK)
            draw_text_center(d, W // 2, int(H * 0.80) + 40, self.t["network_stat"], 24, fill=ACCENT)
            return img

        if sec["kind"] == "disclaimer":
            y = int(H * 0.38)
            draw_text_center(d, W // 2, y, self.t["disclaimer_1"], 30, fill=INK)
            draw_text_center(d, W // 2, y + 42, self.t["disclaimer_2"], 30, fill=INK)
            draw_text_center(d, W // 2, y + 100, self.t["disclaimer_3"], 26, fill=(230, 190, 150))
            draw_text_center(d, W // 2, y + 170, self.t["open_question"], 24, fill=DIM)
            draw_text_center(d, W // 2, y + 202, self.t["open_question_2"], 24, fill=DIM)
            draw_text_center(d, W // 2, int(H * 0.88), self.t["outro_cta"], 22, fill=ACCENT)
            return img

        return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=["ru", "be"], default="ru")
    ap.add_argument("--out", default="build/reels")
    ap.add_argument("--dump-frames", default=None)
    ap.add_argument("--dump-every", type=int, default=30)
    args = ap.parse_args()

    reel = Reel(args.lang)
    total = reel.total_frames()
    print(f"кадров: {total} ({total / FPS:.1f} c)")

    if args.dump_frames:
        dd = ROOT / args.dump_frames
        dd.mkdir(parents=True, exist_ok=True)
        for gi in range(0, total, args.dump_every):
            reel.frame(gi).save(dd / f"f{gi:05d}.png")
        print(f"OK: превью-кадры в {dd}")
        return

    outdir = ROOT / args.out
    outdir.mkdir(parents=True, exist_ok=True)
    dst = outdir / f"grid_{args.lang}.mp4"
    cmd = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "slow",
           "-b:v", SCENE["bitrate"], "-minrate", SCENE["bitrate"],
           "-maxrate", SCENE["bitrate"], "-bufsize", "28M",
           "-x264-params", "nal-hrd=cbr", "-pix_fmt", "yuv420p",
           str(dst)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for gi in range(total):
        proc.stdin.write(np.asarray(reel.frame(gi), dtype="uint8").tobytes())
        if gi % 150 == 0:
            print(f"  кадр {gi}/{total}")
    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        raise SystemExit("ffmpeg завершился с ошибкой")
    print(f"OK: {dst} ({dst.stat().st_size / 1e6:.1f} МБ, {total / FPS:.1f} c)")


if __name__ == "__main__":
    main()
