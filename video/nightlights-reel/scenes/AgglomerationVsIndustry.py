"""Сцена 4: агломерация-сеть против промышленного очага (20-28 c)."""
from render import W, MAP_Y, INK, DIM, AMBER, POS, font


def render(ctx, img, d, p, t):
    v = ctx.norm(ctx.field("y2024"))
    half_h = 560
    agg = ctx.crop_map(v, 26.9, 53.55, 28.25, 54.25, W, half_h)
    ind = ctx.crop_map(v, 28.15, 54.02, 28.65, 54.28, W, half_h)
    img.paste(agg, (0, 250))
    img.paste(ind, (0, 250 + half_h + 24))
    d.text((24, 262), "АГЛОМЕРАЦИЯ = СЕТЬ", font=font(46), fill=AMBER)
    d.text((24, 250 + half_h + 36), "ПРОМЫШЛЕННЫЙ ОБЪЕКТ = ОЧАГ",
           font=font(46), fill=AMBER)
    d.text((24, 306), "Минск и пояс", font=font(30), fill=DIM)
    d.text((24, 250 + half_h + 82), "Жодино · БелАЗ", font=font(30),
           fill=DIM)
    if p > 0.5:
        ctx.center(d, "Крупнее город → непропорционально ярче?",
                   250 + 2 * half_h + 60, 44, fill=INK)
    if p > 0.75:
        ctx.center(d, "Гипотеза, не закон", 250 + 2 * half_h + 118, 40,
                   fill=POS)
