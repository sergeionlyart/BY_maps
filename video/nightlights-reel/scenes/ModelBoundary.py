"""Сцена 7: граница наблюдений и модели (52-56 c)."""
from render import W, MAP_Y, INK, DIM, AMBER, font


def render(ctx, img, d, p, t):
    v = ctx.norm(ctx.field("y2024")) * (1.0 - 0.55 * p)
    img.paste(ctx.map_img(v), (0, MAP_Y))
    ctx.badge(d, "2024 · наблюдения VIIRS")
    ctx.center(d, "2024", 560, 150, fill=INK)
    ctx.center(d, "КОНЕЦ НАБЛЮДЕНИЙ", 740, 64, fill=INK)
    if p > 0.5:
        y = MAP_Y + ctx.map_h - 160
        d.rectangle([0, y - 14, W, y + 78], fill=(16, 11, 7))
        ctx.center(d, "ДАЛЬШЕ — МОДЕЛЬ", y, 66, fill=AMBER)
