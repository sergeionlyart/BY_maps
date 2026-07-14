"""Сцена 8: будущее — демонстрационный слой концентрации (56-62 c).
Слабые огни теряют площадь следа; агломерации — острова. Постоянная
маркировка усиленной визуализации; сценарии различимы численно
(национальные значения 2075 — автоматически из forecast.json)."""
from render import W, MAP_Y, INK, DIM, AMBER, POS, NEG, font, ease


KEYS = [(2030, 0.30), (2050, 0.65), (2075, 1.01)]


def render(ctx, img, d, p, t):
    year = 2030
    prev = None
    for y, edge in KEYS:
        if p <= edge:
            year = y
            break
        prev = y
    v = ctx.norm(ctx.field(f"d{year}_base_official"))
    img.paste(ctx.map_img(v), (0, MAP_Y))
    ctx.demo_marking(d)
    ctx.center(d, str(year), 96, 110, fill=AMBER)
    ctx.center(d, "Во всех сценариях — сокращение", MAP_Y + ctx.map_h + 44,
               48, fill=INK)
    ctx.center(d, "Сильнее на периферии", MAP_Y + ctx.map_h + 104, 48,
               fill=INK)
    if p > 0.6:   # три сценария различимы: население 2075, автоматически
        y0 = MAP_Y + ctx.map_h + 175
        vals = ctx.nat2075
        cols = {"optimistic": POS, "base": AMBER, "negative": NEG}
        names = {"optimistic": "оптимистичный", "base": "базовый",
                 "negative": "негативный"}
        f = font(36)
        for i, s in enumerate(("optimistic", "base", "negative")):
            txt = f"{names[s]}: {vals[s] / 1e6:.1f} млн"
            tw = d.textlength(txt, font=f)
            y = y0 + i * 62
            d.rectangle([88, y - 6, 88 + tw + 26, y + 48],
                        outline=cols[s], width=2)
            d.text((100, y), txt, font=f, fill=cols[s])
        d.text((W / 2 + 40, y0 + 20),
               "население 2075\nпрогноз v2026.4 · модель",
               font=font(30), fill=DIM)
