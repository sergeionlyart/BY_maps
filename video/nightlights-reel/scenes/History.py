"""Сцена 3: историческое изменение ключевыми кадрами (12-20 c)."""
from PIL import Image
from render import W, MAP_Y, INK, DIM, AMBER, NL, font


KEYS = [(1992, "1992 · реконструкция VIIRS-like", None),
        (2000, "2000 · реконструкция VIIRS-like",
         "delta/base_1992/ab_2000.png"),
        (2012, "2012 · переход к наблюдениям VIIRS", None),
        (2024, "2024 · наблюдения VIIRS",
         "delta/base_2012/ab_2024.png")]


def render(ctx, img, d, p, t):
    idx = min(int(p * 4), 3)
    year, marking, delta = KEYS[idx]
    v = ctx.norm(ctx.field(f"y{year}"))
    img.paste(ctx.map_img(v), (0, MAP_Y))
    if delta:
        dl = Image.open(NL / delta).convert("RGBA")
        dl = dl.resize((W, ctx.map_h), Image.Resampling.BILINEAR)
        img.paste(dl, (0, MAP_Y), dl)
    ctx.badge(d, marking)
    ctx.center(d, str(year), 96, 96)
    ctx.center(d, "1990-е: световой след сокращается", 205, 52,
               fill=AMBER if idx < 2 else DIM)
    if idx >= 2:
        ctx.center(d, "Но одна карта не объясняет причину",
                   MAP_Y + ctx.map_h + 50, 46, fill=INK)
