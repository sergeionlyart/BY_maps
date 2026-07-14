#!/usr/bin/env python3
"""Рилс-конвейер INF-08 v2: «Беларусь из космоса, 1992-2075» (R-3, T-14/15).

Кадры 1080x1920@30fps генерируются ИЗ ДАННЫХ пакета (вырезки растров +
nightlights_v2.json + assumptions.json + сцена reel_space_scene.json) и
собираются ffmpeg в мастер H.264 >= 12 Мбит/с. Рендер детерминирован
(сеяный дизеринг по номеру кадра): кадры регенерируются бит-в-бит.

Честность (T-13): весь модельный сегмент несёт впечатанный бейдж
«МОДЕЛЬ/МАДЭЛЬ», штриховую рамку и подпись сценария; отбивки отделяют
смену природы данных (DMSP -> VIIRS -> модель).

Визуальная стабилизация ретро-сегмента: поля DMSP домножаются на
(median3(нац.DN)/нац.DN) - гасит межспутниковые скачки уровня в КАДРАХ;
зональные данные не сглаживаются (методблок §3).

Запуск (требует rasterio, numpy, Pillow, ffmpeg в PATH):
  python tools/render_reel_space.py --lang ru --hook A
  python tools/render_reel_space.py --lang be --hook A --mode square
  ... --dump-frames build/reels/frames_ru --dump-every 30  (PNG-превью)
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from etl.common import ROOT, OUT                     # noqa: E402
from etl.nightlights_fetch import RASTERS            # noqa: E402
from etl.nightlights_zonal import zone_labels        # noqa: E402
from etl.nightlights_frames import (                 # noqa: E402
    lut, _norm_vnl, _norm_dmsp, SEED)
from etl import nightlights_model as M               # noqa: E402

SCENE = json.loads((ROOT / "tools" / "reel_space_scene.json").read_text())
FONT = ROOT / "data" / "raw" / "nightlights" / "fonts" / "DejaVuSans.ttf"
QR = ROOT / "data" / "raw" / "nightlights" / "qr_nightlights.png"

BG = (5, 4, 3)
INK = (238, 230, 214)
DIM = (150, 138, 118)
AMBER = (240, 205, 150)
BLUE = (86, 152, 185)
NEG = (224, 122, 104)
POS = (77, 189, 110)

LAYOUTS = {
    "portrait": {"size": (1080, 1920), "counter": (60, 30),
                 "map": (0, 210, 1080, None), "chart": (70, 1290, 1010, 1560),
                 "sub": (60, 1620, 1020, 1830)},
    "square": {"size": (1080, 1080), "counter": (40, 18),
               "map": (0, 150, 1080, None), "chart": None,
               "sub": (50, 990, 1030, 1072)},
    "landscape": {"size": (1920, 1080), "counter": (1180, 40),
                  "map": (30, 30, 1160, None), "chart": (1220, 620, 1880, 900),
                  "sub": (1180, 200, 1880, 560)},
}


def font(sz: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT), sz)


class Fields:
    """Ленивая загрузка нормированных полей яркости на сетке VNL-2024."""

    def __init__(self, assump: dict):
        self.assump = assump
        with rasterio.open(RASTERS / "vnl_2024.tif") as ref:
            self.transform, self.crs = ref.transform, ref.crs
            self.shape = (ref.height, ref.width)
            self.bounds = ref.bounds
            self.base2024 = ref.read(1).astype("float64")
            self.labels, self.ids = zone_labels(ref)
        self.zid = {z: i + 1 for i, z in enumerate(self.ids)}
        self.floor_max = assump["model"]["floor_max_nw"]
        self.bright = self.base2024 >= self.floor_max
        self.fut = M.future_light(assump)
        self._cache: dict[str, np.ndarray] = {}
        self._order: list[str] = []
        # визуальная стабилизация ретро: median3 нац. DN / нац. DN
        sums = {}
        for y in range(1992, 2012):
            with rasterio.open(RASTERS / f"dmsp_{y}.tif") as s:
                sums[y] = float(s.read(1).sum())
        self.stab = {}
        for y in sums:
            w = [sums.get(q) for q in (y - 1, y, y + 1) if q in sums]
            self.stab[y] = statistics.median(w) / sums[y]

    def _put(self, k: str, v: np.ndarray) -> np.ndarray:
        self._cache[k] = v
        self._order.append(k)
        if len(self._order) > 8:
            self._cache.pop(self._order.pop(0), None)
        return v

    def obs(self, year: int) -> np.ndarray:
        k = f"y{year}"
        if k in self._cache:
            return self._cache[k]
        if year <= 2011:
            with rasterio.open(RASTERS / f"dmsp_{year}.tif") as s:
                src = s.read(1).astype("float64") * self.stab[year]
                dst = np.zeros(self.shape)
                reproject(src, dst, src_transform=s.transform, src_crs=s.crs,
                          dst_transform=self.transform, dst_crs=self.crs,
                          resampling=Resampling.bilinear)
            v = _norm_dmsp(dst)
        else:
            with rasterio.open(RASTERS / f"vnl_{year}.tif") as s:
                v = _norm_vnl(s.read(1).astype("float64"))
        return self._put(k, v.astype("float32"))

    def model(self, node: int, scn: str, jmp: str) -> np.ndarray:
        k = f"m{node}_{scn}_{jmp}"
        if k in self._cache:
            return self._cache[k]
        f_arr = np.ones(len(self.ids) + 1)
        for z, fz in self.fut["factor"][jmp][scn].items():
            f_arr[self.zid[z]] = fz[node]
        scaled = np.where(self.bright, self.base2024 * f_arr[self.labels],
                          self.base2024)
        return self._put(k, _norm_vnl(scaled).astype("float32"))


class Reel:
    def __init__(self, lang: str, hook: str, mode: str):
        self.lang, self.hook, self.mode = lang, hook, mode
        self.L = LAYOUTS[mode]
        self.W, self.H = self.L["size"]
        self.fps = SCENE["fps"]
        self.assump = M.load_assumptions()
        self.fields = Fields(self.assump)
        self.table = lut()
        self.night = json.loads(
            (OUT / "nightlights_v2.json").read_text())
        self.data = json.loads((OUT / "data.json").read_text())["territories"]
        b = self.fields.bounds
        kx = math.cos(math.radians((b.bottom + b.top) / 2))
        self.map_aspect = ((b.right - b.left) * kx) / (b.top - b.bottom)
        mx0, my0, mw, _ = self.L["map"]
        self.map_rect = (mx0, my0, mw, round(mw / self.map_aspect))
        self.geo = self._load_geo()
        self.nat_curve = self._nat_curve()
        self.sections = self._compile()

    # ---------- подготовка ----------

    def _load_geo(self) -> dict[str, list[list[tuple[float, float]]]]:
        g2 = json.loads((OUT / "geo" / "adm2.geojson").read_text())
        g1 = json.loads((OUT / "geo" / "adm1.geojson").read_text())
        feats = {f["properties"]["id"]: f for f in g2["features"]}
        feats.update({f["properties"]["id"]: f for f in g1["features"]})
        out = {}
        for zid, f in feats.items():
            polys = (f["geometry"]["coordinates"]
                     if f["geometry"]["type"] == "MultiPolygon"
                     else [f["geometry"]["coordinates"]])
            out[zid] = [p[0] for p in polys]
        return out

    def to_map(self, lon: float, lat: float) -> tuple[float, float]:
        b = self.fields.bounds
        x0, y0, w, h = self.map_rect
        return (x0 + (lon - b.left) / (b.right - b.left) * w,
                y0 + (b.top - lat) / (b.top - b.bottom) * h)

    def _nat_curve(self) -> dict:
        """График рилса - НАСЕЛЕНИЕ (наблюдение + 3 сценария): чистая
        кривая без продуктовых артефактов света (VNL-2021 и пр.);
        карта показывает свет, график - население, которое он
        иллюстрирует."""
        obs = sorted((int(y), v) for y, v in self.night["natPop"].items()
                     if int(y) <= 2024)
        fc = json.loads((OUT / "forecast.json").read_text())
        br = {}
        for s in ["optimistic", "base", "negative"]:
            e = fc["territories"]["BY"][s]
            br[s] = list(zip(e["years"], e["pop"]))
        return {"obs": obs, "branches": br}

    def _compile(self) -> list[dict]:
        out, t0 = [], 0.0
        for s in SCENE["sections"]:
            n = round(s["dur"] * self.fps)
            out.append({**s, "start": t0, "frames": n})
            t0 += s["dur"]
        return out

    # ---------- отрисовка элементов ----------

    def map_img(self, v: np.ndarray, rng) -> Image.Image:
        x = np.clip(v * 255 + rng.uniform(-1.0, 1.0, v.shape), 0, 255)
        idx = x.astype("uint8")
        img = Image.fromarray(idx, "P")
        img.putpalette(self.table.flatten().tolist())
        img = img.convert("RGB")
        _, _, w, h = self.map_rect
        return img.resize((w, h), Image.Resampling.BILINEAR)

    def text(self, d: ImageDraw.ImageDraw, xy, s, sz, fill=INK,
             anchor="la") -> None:
        d.text(xy, s, font=font(sz), fill=fill, anchor=anchor)

    def wrap_lines(self, d, lines, rect, sz, fill=INK, gap=1.25,
                   align="center") -> None:
        """Перенос по словам под ширину rect; кегль ужимается, пока
        блок не помещается по высоте (субтитры не должны резаться)."""
        x0, y0, x1, y1 = rect
        maxw = x1 - x0

        def flow(size):
            f = font(size)
            out = []
            for ln in lines:
                cur = ""
                for w in ln.split(" "):
                    trial = (cur + " " + w).strip()
                    if d.textlength(trial, font=f) <= maxw or not cur:
                        cur = trial
                    else:
                        out.append(cur)
                        cur = w
                if cur:
                    out.append(cur)
            return out

        while sz > 30:
            flowed = flow(sz)
            if len(flowed) * sz * gap <= (y1 - y0) + sz * 0.4:
                break
            sz -= 4
        f = font(sz)
        total = len(flowed) * sz * gap
        y = y0 + max(0, ((y1 - y0) - total) / 2)
        for ln in flowed:
            xx = (x0 + x1) / 2 if align == "center" else x0
            d.text((xx, y), ln, font=f, fill=fill,
                   anchor="ma" if align == "center" else "la")
            y += sz * gap

    def draw_badge(self, d, seg: str, extra: str = "") -> None:
        x0, y0, w, h = self.map_rect
        txt = SCENE["badges"][seg][self.lang] + extra
        f = font(34)
        tw = d.textlength(txt, font=f)
        bx, by = x0 + 16, y0 + 14
        d.rectangle([bx - 8, by - 6, bx + tw + 10, by + 44],
                    fill=(18, 12, 7))
        color = AMBER if seg == "model" else DIM
        d.text((bx, by), txt, font=f, fill=color)
        if seg == "model":
            d.rectangle([bx - 8, by - 6, bx + tw + 10, by + 44],
                        outline=(199, 141, 80), width=2)

    def dashed_rect(self, d, rect, color, dash=16, gap=10, width=3) -> None:
        x0, y0, x1, y1 = rect
        for xa in range(int(x0), int(x1), dash + gap):
            d.line([(xa, y0), (min(xa + dash, x1), y0)], fill=color, width=width)
            d.line([(xa, y1), (min(xa + dash, x1), y1)], fill=color, width=width)
        for ya in range(int(y0), int(y1), dash + gap):
            d.line([(x0, ya), (x0, min(ya + dash, y1))], fill=color, width=width)
            d.line([(x1, ya), (x1, min(ya + dash, y1))], fill=color, width=width)

    def draw_model_marker(self, d, scn: str) -> None:
        """T-13: бейдж + штриховая рамка + подпись сценария."""
        x0, y0, w, h = self.map_rect
        scn_txt = {s: SCENE["trio"][self.lang][i] for i, s in
                   enumerate(["optimistic", "base", "negative"])}[scn]
        self.draw_badge(d, "model", f" · {scn_txt}")
        self.dashed_rect(d, (x0 + 4, y0 + 4, x0 + w - 4, y0 + h - 4),
                         (199, 141, 80))

    def draw_year(self, d, label: str) -> None:
        cx, cy = self.L["counter"]
        self.text(d, (cx, cy), label, 150 if self.mode != "square" else 96,
                  fill=INK)

    def draw_cities(self, d, year: float) -> None:
        for c in SCENE["cities"]:
            if year < c["from_year"]:
                continue
            e = self.data.get(c["id"])
            if not e:
                continue
            x, y = self.to_map(float(e["lon"]), float(e["lat"]))
            name = e["be" if self.lang == "be" else "ru"]
            d.ellipse([x - 3, y - 3, x + 3, y + 3], outline=DIM, width=1)
            d.text((x + 7, y - 8), name, font=font(26), fill=DIM)

    def _dashed_line(self, d, pts, col, width) -> None:
        for i in range(len(pts) - 1):
            (xa, ya), (xb, yb) = pts[i], pts[i + 1]
            steps = max(2, int(math.hypot(xb - xa, yb - ya) / 14))
            for q in range(0, steps, 2):
                d.line([(xa + (xb - xa) * q / steps,
                         ya + (yb - ya) * q / steps),
                        (xa + (xb - xa) * (q + 1) / steps,
                         ya + (yb - ya) * (q + 1) / steps)],
                       fill=col, width=width)

    def draw_chart(self, d, year: float, scn: str, jmp: str) -> None:
        rect = self.L["chart"]
        if not rect:
            return
        x0, y0, x1, y1 = rect
        obs = self.nat_curve["obs"]
        branches = self.nat_curve["branches"]
        vmax = 11_000_000
        vmin = 3_000_000
        X = lambda yy: x0 + (yy - 1992) / (2075 - 1992) * (x1 - x0)
        Y = lambda v: y1 - (v - vmin) / (vmax - vmin) * (y1 - y0)
        d.line([(x0, y1), (x1, y1)], fill=(60, 52, 42), width=2)
        for yy in (1992, 2024, 2075):
            d.text((X(yy), y1 + 8), str(yy), font=font(24), fill=DIM,
                   anchor="ma")
        for v in (5_000_000, 10_000_000):
            d.line([(x0, Y(v)), (x1, Y(v))], fill=(38, 33, 27), width=1)
            d.text((x0 - 8, Y(v)), f"{v / 1e6:.0f}М", font=font(22),
                   fill=DIM, anchor="rm")
        seen = [(X(yy), Y(v)) for yy, v in obs if yy <= year]
        if len(seen) > 1:
            d.line(seen, fill=BLUE, width=4)
        if year >= 2024:
            for s, col in [("optimistic", POS), ("base", AMBER),
                           ("negative", NEG)]:
                pts = [seen[-1]] if seen else []
                pts += [(X(yy), Y(v)) for yy, v in branches[s]
                        if yy <= max(year, 2026)]
                if len(pts) > 1:
                    self._dashed_line(d, pts, col,
                                      4 if s == scn else 2)
        if seen:
            cx, cy = seen[-1]
            d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=BLUE)
        cap = ("население, наблюдение и 3 сценария прогноза"
               if self.lang == "ru"
               else "насельніцтва, назіранне і 3 сцэнарыі прагнозу")
        d.text((x0, y0 - 30), cap, font=font(24), fill=DIM)

    def draw_progress(self, d, frac: float) -> None:
        d.line([(0, self.H - 4), (self.W * frac, self.H - 4)],
               fill=AMBER, width=4)

    def zone_outline(self, d, zid: str, color, width=4) -> None:
        for ring in self.geo.get(zid, []):
            pts = [self.to_map(lon, lat) for lon, lat in ring]
            d.line(pts + [pts[0]], fill=color, width=width)

    # ---------- секции ----------

    def frame(self, gi: int) -> Image.Image:
        t = gi / self.fps
        sec, p = None, 0.0
        for s in self.sections:
            if t < s["start"] + s["dur"] or s is self.sections[-1]:
                sec, p = s, min(1.0, (t - s["start"]) / s["dur"])
                break
        rng = np.random.default_rng(SEED + gi)
        img = Image.new("RGB", (self.W, self.H), BG)
        d = ImageDraw.Draw(img)
        getattr(self, f"sec_{sec['id']}")(img, d, p, rng)
        total = self.sections[-1]["start"] + self.sections[-1]["dur"]
        self.draw_progress(d, t / total)
        return img

    def _paste_map(self, img, v, rng) -> None:
        m = self.map_img(v, rng)
        img.paste(m, (self.map_rect[0], self.map_rect[1]))

    def _blend(self, pos: float, kind="obs", scn="base", jmp="official"):
        """Линейный кроссфейд полей: pos - год (obs) либо дробный
        индекс узла модели."""
        frac = pos - math.floor(pos)
        if kind == "obs":
            a = int(math.floor(pos))
            b = min(a + 1, 2024)
            va, vb = self.fields.obs(a), self.fields.obs(b)
        else:
            nodes = self.night["nodes"]
            i = min(int(math.floor(pos)), len(nodes) - 1)
            j = min(i + 1, len(nodes) - 1)
            va = self.fields.model(nodes[i], scn, jmp)
            vb = self.fields.model(nodes[j], scn, jmp)
        return va * (1 - frac) + vb * frac

    @staticmethod
    def ease(p: float) -> float:
        s = p * p * (3 - 2 * p)
        return 0.75 * p + 0.25 * s

    def sec_hook(self, img, d, p, rng) -> None:
        if self.hook == "B":
            v = self.fields.obs(2024)
            z = 1.30 - 0.30 * self.ease(p)
            h, w = v.shape
            ch, cw = int(h / z), int(w / z)
            y0, x0 = (h - ch) // 2, (w - cw) // 2
            vv = np.asarray(Image.fromarray(
                (v[y0:y0 + ch, x0:x0 + cw] * 255).astype("uint8")).resize(
                (w, h), Image.Resampling.BILINEAR), dtype="float32") / 255
            self._paste_map(img, vv * min(1.0, 0.25 + p), rng)
        else:
            self._paste_map(img, self.fields.obs(2024) * min(1.0, 0.35 + p), rng)
        self.draw_badge(d, "vnl")
        lines = SCENE["hook"][self.hook][self.lang]
        self.wrap_lines(d, lines, self.L["sub"], 66, fill=INK)
        self.draw_year(d, "2024")

    def _callout(self, d, year: float) -> None:
        for c in SCENE["callouts"]:
            if c["from"] <= year <= c["to"] + 0.99:
                self.wrap_lines(d, [c[self.lang]], self.L["sub"], 58,
                                fill=AMBER)
                return

    def sec_retro_run(self, img, d, p, rng) -> None:
        # кап 2011.0: без него хвост секции подмешивал кадр VNL-2012
        # под бейджем «DMSP» - смена природы данных только через отбивку
        yf = min(1992 + self.ease(p) * (2011.999 - 1992), 2011.0)
        self._paste_map(img, self._blend(yf), rng)
        self.draw_badge(d, "dmsp")
        self.draw_cities(d, yf)
        self.draw_year(d, str(int(yf)))
        self.draw_chart(d, yf, "base", "official")
        self._callout(d, yf)

    def sec_seam_break(self, img, d, p, rng) -> None:
        flash = max(0.0, 1 - abs(p - 0.5) * 5)
        v = self.fields.obs(2012) * (0.55 + 0.45 * p)
        self._paste_map(img, np.clip(v + flash * 0.35, 0, 1), rng)
        self.draw_badge(d, "vnl")
        self.draw_year(d, "2012")
        self.wrap_lines(d, [SCENE["seam_break"][self.lang]], self.L["sub"],
                        58, fill=INK)
        self.draw_chart(d, 2012, "base", "official")

    def sec_viirs_run(self, img, d, p, rng) -> None:
        yf = 2012 + self.ease(p) * (2024.999 - 2012)
        yf = min(yf, 2024.0)
        self._paste_map(img, self._blend(yf), rng)
        self.draw_badge(d, "vnl")
        self.draw_cities(d, yf)
        self.draw_year(d, str(int(yf)))
        self.draw_chart(d, yf, "base", "official")
        self._callout(d, yf)

    def sec_focus_smal(self, img, d, p, rng) -> None:
        self._paste_map(img, self.fields.obs(2024), rng)
        self.draw_badge(d, "vnl")
        self.draw_year(d, "2024")
        cfg = SCENE["focus_smal"]
        zid = cfg["zone"]
        pulse = 0.5 + 0.5 * math.sin(p * math.pi * 4)
        col = tuple(int(a + (b - a) * pulse) for a, b in zip(AMBER, (255, 255, 255)))
        self.zone_outline(d, zid, col, width=5)
        row = next(r for r in self.night["rows"] if r["id"] == zid)
        lr, pr = row["lightRatio"], row["popRatio"]
        title = cfg[f"{self.lang}_title"]
        line = cfg[f"{self.lang}_line"]
        stat = (f"доля света к тренду ×{lr:.2f} · населения ×{pr:.2f}"
                if self.lang == "ru" else
                f"доля святла да трэнду ×{lr:.2f} · насельніцтва ×{pr:.2f}")
        self.wrap_lines(d, [title, stat, line], self.L["sub"], 54, fill=INK)
        self.draw_chart(d, 2024, "base", "official")

    def sec_model_break(self, img, d, p, rng) -> None:
        v = self.fields.obs(2024) * (1 - 0.35 * p)
        self._paste_map(img, v, rng)
        self.draw_model_marker(d, "base")
        self.wrap_lines(d, [SCENE["model_break"][self.lang]], self.L["sub"],
                        64, fill=AMBER)
        self.draw_year(d, "2024")

    def sec_model_run(self, img, d, p, rng) -> None:
        nodes = self.night["nodes"]
        pos = self.ease(p) * (len(nodes) - 1)
        v = self._blend(pos, kind="model")
        self._paste_map(img, v, rng)
        node = nodes[min(int(round(pos)), len(nodes) - 1)]
        self.draw_model_marker(d, "base")
        self.draw_year(d, str(node))
        self.draw_chart(d, node, "base", "official")
        self.wrap_lines(d, [SCENE["model_sub"][self.lang],
                            SCENE["disclaimer"][self.lang]],
                        self.L["sub"], 50, fill=DIM)

    def sec_trio_2075(self, img, d, p, rng) -> None:
        labels = SCENE["trio"][self.lang]
        scns = ["optimistic", "base", "negative"]
        cols = [POS, AMBER, NEG]
        x0, y0, w, _ = self.map_rect
        mh = int(w / self.map_aspect)
        span = self.L["sub"][1] - y0 if self.mode == "portrait" else self.H - y0
        step = min(mh // 2 + 40, span // 3) if self.mode == "portrait" else self.H // 3
        sh = step - 14
        sw = int(sh * self.map_aspect)
        for i, s in enumerate(scns):
            v = self.fields.model(2075, s, "official")
            x = np.clip(v * 255 + rng.uniform(-1, 1, v.shape), 0, 255)
            m = Image.fromarray(x.astype("uint8"), "P")
            m.putpalette(self.table.flatten().tolist())
            m = m.convert("RGB").resize((sw, sh), Image.Resampling.BILINEAR)
            px = (self.W - sw) // 2 if self.mode != "landscape" else 60
            py = y0 + i * step
            img.paste(m, (px, py))
            dd = ImageDraw.Draw(img)
            self.dashed_rect(dd, (px, py, px + sw, py + sh), (199, 141, 80),
                             dash=12, gap=8, width=2)
            f = font(40)
            tw = dd.textlength(labels[i], font=f)
            dd.rectangle([px + 10, py + 10, px + tw + 26, py + 62],
                         fill=(14, 10, 7))
            dd.text((px + 18, py + 16), labels[i], font=f, fill=cols[i])
        self.wrap_lines(d, [SCENE["trio"][f"{self.lang}_caption"]],
                        (40, y0 - 120, self.W - 40, y0 - 8), 48, fill=INK)
        self.draw_badge(d, "model")
        self.wrap_lines(d, [SCENE["disclaimer"][self.lang]], self.L["sub"],
                        44, fill=DIM)

    def sec_twist(self, img, d, p, rng) -> None:
        v = self.fields.obs(2024) * 0.35
        self._paste_map(img, v, rng)
        lines = SCENE["twist"][self.lang]
        k = 1 + int(p * 3.2)
        rect = (60, self.H * 0.30, self.W - 60, self.H * 0.72) \
            if self.mode == "portrait" else self.L["sub"]
        self.wrap_lines(d, lines[:k], rect, 62, fill=INK)

    def sec_brand(self, img, d, p, rng) -> None:
        cx = self.W // 2
        # контур страны: все области adm1
        for zid, rings in self.geo.items():
            if not zid.startswith("BY-"):
                continue
            for ring in rings:
                pts = [self.to_map(lon, lat) for lon, lat in ring]
                d.line(pts + [pts[0]], fill=(120, 100, 78), width=2)
        lines = SCENE["brand"][self.lang]
        rect = (60, self.map_rect[1] + self.map_rect[3] + 30,
                self.W - 60, self.H - 420) if self.mode == "portrait" \
            else self.L["sub"]
        self.wrap_lines(d, lines, rect, 52, fill=INK)
        if QR.exists():
            qr = Image.open(QR).resize((300, 300))
            img.paste(qr, (cx - 150, self.H - 380))
        d.text((cx, self.H - 66), "bymaps · /research/nightlights",
               font=font(36), fill=DIM, anchor="ma")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=["ru", "be"], default="ru")
    ap.add_argument("--hook", choices=["A", "B"], default="A")
    ap.add_argument("--mode", choices=list(LAYOUTS), default="portrait")
    ap.add_argument("--out", default="build/reels")
    ap.add_argument("--dump-frames", default=None)
    ap.add_argument("--dump-every", type=int, default=30)
    args = ap.parse_args()

    reel = Reel(args.lang, args.hook, args.mode)
    total = sum(s["frames"] for s in reel.sections)
    outdir = ROOT / args.out
    outdir.mkdir(parents=True, exist_ok=True)

    if args.dump_frames:
        dd = ROOT / args.dump_frames
        dd.mkdir(parents=True, exist_ok=True)
        for gi in range(0, total, args.dump_every):
            reel.frame(gi).save(dd / f"f{gi:05d}.png")
        print(f"OK: превью-кадры в {dd} ({len(range(0, total, args.dump_every))})")
        return

    name = f"space_{args.lang}_hook{args.hook}_{args.mode}.mp4"
    dst = outdir / name
    # CBR с филлером: тёмный контент в ABR недобирает битрейт, а ТЗ
    # требует мастер >= 12 Мбит/с (запас под пережатие соцсетями)
    cmd = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{reel.W}x{reel.H}", "-r", str(reel.fps), "-i", "-",
           "-c:v", "libx264", "-preset", "slow",
           "-b:v", SCENE["bitrate"], "-minrate", SCENE["bitrate"],
           "-maxrate", SCENE["bitrate"], "-bufsize", "28M",
           "-x264-params", "nal-hrd=cbr", "-pix_fmt", "yuv420p",
           str(dst)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    for gi in range(total):
        proc.stdin.write(np.asarray(reel.frame(gi), dtype="uint8").tobytes())
        if gi % 150 == 0:
            print(f"  кадр {gi}/{total}")
    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        raise SystemExit("ffmpeg завершился с ошибкой")
    print(f"OK: {dst} ({dst.stat().st_size / 1e6:.1f} МБ, "
          f"{total / reel.fps:.1f} c)")


if __name__ == "__main__":
    main()
