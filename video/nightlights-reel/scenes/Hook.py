"""Сцена 1: исследовательский вопрос (0-5 c)."""
from render import W, MAP_Y, INK, DIM, AMBER, font, ease


HIGHLIGHTS = [   # агломерация → промышленный очаг → дорога → малый НП
    (27.56, 53.90, "агломерация"),
    (28.35, 54.10, "промышленный очаг"),      # Жодино/БелАЗ
    (26.80, 53.15, "дорога"),                 # трасса М1
    (25.32, 53.15, "малый населённый пункт"),  # Дятлово
]


def render(ctx, img, d, p, t):
    v = ctx.norm(ctx.field("y2024")) * min(1.0, 0.35 + p)
    img.paste(ctx.map_img(v), (0, MAP_Y))
    ctx.badge(d, "2024 · наблюдения VIIRS")
    ctx.center(d, "Что видно из космоса ночью?", 96, 74)
    idx = min(int(p * 4), 3)
    lon, lat, label = HIGHLIGHTS[idx]
    x, y = ctx.to_map_xy(lon, lat)
    r = 46 + 8 * ease((p * 4) % 1)
    d.ellipse([x - r, y - r, x + r, y + r], outline=AMBER, width=4)
    d.text((x, y + r + 10), label, font=font(32), fill=AMBER, anchor="ma")
    q = ["Население?", "Экономика?", "Только свет?"][min(int(p * 3), 2)]
    ctx.center(d, q, 190, 58, fill=DIM)
