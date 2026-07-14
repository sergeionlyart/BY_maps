"""Сцена 2: что измеряет спутник (5-12 c)."""
from render import W, MAP_Y, INK, DIM, AMBER, font


def render(ctx, img, d, p, t):
    v = ctx.norm(ctx.field("y2024")) * 0.75
    img.paste(ctx.map_img(v), (0, MAP_Y))
    ctx.badge(d, "2024 · наблюдения VIIRS")
    ctx.center(d, "Свет ≠ население", 110, 92, fill=INK)
    cats = ["жильё", "дороги", "услуги", "производство"]
    shown = min(1 + int(p * 5), 4)
    xs = [W * (i + 1) / 5 for i in range(4)]
    for i in range(shown):
        f = font(40)
        tw = d.textlength(cats[i], font=f)
        y = MAP_Y + ctx.map_h + 40
        d.rectangle([xs[i] - tw / 2 - 14, y, xs[i] + tw / 2 + 14, y + 58],
                    outline=AMBER, width=2)
        d.text((xs[i], y + 9), cats[i], font=f, fill=INK, anchor="ma")
    ctx.center(d, "Косвенный след человеческой активности",
               MAP_Y + ctx.map_h + 130, 40, fill=DIM)
