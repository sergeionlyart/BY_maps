"""Сцена 6: три исследовательских кандидата (40-52 c). Гипотезы, не
выводы; числа не показываются (гейт releaseApproved охраняет числовые
значения, качественные направления подтверждены пересчётом)."""
from render import W, MAP_Y, INK, DIM, AMBER, font


CROPS = {
    "minsk-agglomeration": (26.9, 53.55, 28.25, 54.25),
    "smolevichi-zhodino": (27.9, 53.85, 28.75, 54.35),
    "astravets": (25.6, 54.45, 26.4, 54.95),
}


def render(ctx, img, d, p, t):
    story = ctx.story["scenes"][5]
    cards = story["cards"]
    seg = p * 3.12                     # ~3.8 c на карточку + титр
    idx = min(int(seg), 2)
    if p > 0.96:
        ctx.center(d, "ТРИ ГИПОТЕЗЫ", H2 := 700, 72, fill=AMBER)
        ctx.center(d, "ДЛЯ СЛЕДУЮЩЕГО ИССЛЕДОВАНИЯ", 790, 58, fill=INK)
        return
    card = cards[idx]
    cand = ctx.cands[card["caseId"]]
    v = ctx.norm(ctx.field("y2024"))
    crop = CROPS[card["caseId"]]
    img.paste(ctx.crop_map(v, *crop, W, 760), (0, 330))
    d.rectangle([0, 330, W - 1, 330 + 760], outline=AMBER, width=3)
    ctx.center(d, card["title"], 100, 72, fill=AMBER)
    ctx.center(d, card["line"], 200, 50, fill=INK)
    ctx.center(d, card["sub"], 330 + 760 + 40, 38, fill=DIM)
    ctx.center(d, f"статус: кандидат · период "
               f"{cand['period'][0]}–{cand['period'][1]}",
               330 + 760 + 100, 32, fill=DIM)
