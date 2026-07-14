"""Сцена 5: главный тезис — свет и статистика не сходятся (28-40 c).

Две нормированные линии из АНАЛИТИЧЕСКОГО слоя: доля Смолевичи-Жодино
в населении против доли в национальном свете, 2012-2024; в точке
расхождения территория выделяется контуром.
"""
import json
from render import W, MAP_Y, INK, DIM, AMBER, BLUE, NEG, ROOT, font, ease


def _series(ctx):
    rows = {r["id"]: r for r in ctx.night["rows"]}
    r = rows["r-smalavicki"]
    data = json.loads((ROOT / "web/public/data/data.json").read_text())
    terr = data["territories"]
    years = list(range(2012, 2025))
    ls = [r["lshare"][str(y)] for y in years]
    natp = {y: sum(float(terr[z]["pop"][str(y)][0]) for z in rows
                   if terr[z]["pop"].get(str(y))) for y in years if y != 2020}
    ps = [float(terr["r-smalavicki"]["pop"][str(y)][0]) / natp[y]
          if y != 2020 else None for y in years]
    return years, [v / ls[0] * 100 for v in ls], \
        [v / ps[0] * 100 if v else None for v in ps]


def render(ctx, img, d, p, t):
    v = ctx.norm(ctx.field("y2024")) * 0.35
    img.paste(ctx.map_img(v), (0, MAP_Y))
    ctx.outline(d, "r-smalavicki", AMBER, width=5)
    ctx.center(d, "ГЛАВНЫЙ СИГНАЛ:", 96, 62, fill=INK)
    ctx.center(d, "СВЕТ И СТАТИСТИКА НЕ СХОДЯТСЯ", 170, 62, fill=AMBER)

    # график: нормированные линии (2012=100), рисуются по мере p
    x0 = 90
    y0 = MAP_Y + ctx.map_h + 40
    x1 = W - 90
    y1 = MAP_Y + ctx.map_h + 320
    years, ls, ps = _series(ctx)
    span = years[-1] - years[0]
    def X(y): return x0 + (y - years[0]) / span * (x1 - x0)
    vals = [q for q in ls + [q for q in ps if q] if q]
    lo, hi = min(vals) - 5, max(vals) + 5
    def Y(q): return y1 - (q - lo) / (hi - lo) * (y1 - y0)
    d.line([(x0, Y(100)), (x1, Y(100))], fill=(60, 52, 42), width=2)
    upto = years[0] + ease(min(p * 1.6, 1.0)) * span
    pl = [(X(y), Y(q)) for y, q in zip(years, ls) if y <= upto]
    pp = [(X(y), Y(q)) for y, q in zip(years, ps) if q and y <= upto]
    if len(pp) > 1:
        d.line(pp, fill=BLUE, width=5)
    if len(pl) > 1:
        d.line(pl, fill=AMBER, width=5)
    d.text((x0, y0 - 44), "Смолевичи–Жодино · 2012 = 100",
           font=font(30), fill=DIM)
    d.text((x1, Y(ps[-1] or 100) - 6), "доля в населении", font=font(28),
           fill=BLUE, anchor="rd")
    d.text((x1, Y(ls[-1]) + 10), "доля в нац. свете", font=font(28),
           fill=AMBER, anchor="ra")
    for y in (2012, 2018, 2024):
        d.text((X(y), y1 + 8), str(y), font=font(26), fill=DIM,
               anchor="ma")
    if p > 0.55:
        ctx.center(d, "Не готовый диагноз", y1 + 70, 44, fill=INK)
    if p > 0.7:
        ctx.center(d, "Точка для дополнительного исследования",
                   y1 + 126, 44, fill=INK)
