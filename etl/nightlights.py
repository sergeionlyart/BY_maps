"""INF-08 `nightlights`: ночные огни против официальной статистики.

Вопрос: где динамика ночной светимости расходится с официальной
динамикой населения - кандидаты на недоучтённый отток или искажения
учёта?

Данные: зональная светимость 119 зон (118 районов + Минск) по годовым
композитам VIIRS (WorldPop fvf = EOG average_masked VNL 2.1/2.2, 100 м,
2015-2023), извлечённая etl/nightlights_extract.py в
data/raw/nightlights/zonal_light.csv (URL и sha256 источника - registry).
Ряды населения - база проекта (поле `pop`: район включает свой город,
Минск = столица - геометрически совпадает с зоной).

Метод: доля зоны в общенациональной светимости (гасит версионные скачки
продукта VNL 2.1->2.2 и общий калибровочный дрейф) и доля в населении;
лог-линейный тренд долей 2015-2019 («норма» до шоков); индекс расхождения
= ln(доля света_факт/тренд) - ln(доля населения_факт/тренд) на 2022-2023.
Отрицательный - свет просел относительно населения сильнее ожидаемого.

Свет != население: индекс - маркер расхождения для дальнейшего разбора,
а не «истинное население» (LED, промышленность, энергосбережение,
факелы - в методблоке §7).

Запуск: python -m etl.nightlights -> web/public/data/nightlights.json
"""
from __future__ import annotations

import csv
import json
import math

from .common import ROOT, OUT

RAW = ROOT / "data" / "raw" / "nightlights"
VERSION = "1.0.0"

TREND_YEARS = list(range(2015, 2020))   # 2015-2019, докризисное окно
SHOCK_YEARS = [2022, 2023]              # устоявшийся шок (вне спайка VNL 2021)
YEARS = list(range(2015, 2024))

# для консольной диагностики: сколько ярчайших районов считать надёжными
RELIABLE_TOP = 20


def load_zonal() -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = {}
    with open(RAW / "zonal_light.csv") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["zone_id"], {})[int(r["year"])] = float(r["radiance"])
    return out


def _zone_pop(data: dict, zid: str, year: int) -> float | None:
    v = data.get(zid)
    if not v:
        return None
    p = v["pop"].get(str(year))
    return float(p[0]) if p else None


def _loglin_fit(years: list[int], vals: list[float]) -> tuple[float, float]:
    xs = [y - TREND_YEARS[0] for y in years]
    ys = [math.log(max(v, 1e-12)) for v in vals]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return my - b * mx, b


def _ratio(share: dict[int, float]) -> float | None:
    """Факт/тренд доли: среднее SHOCK против экстраполяции тренда."""
    ty = [y for y in TREND_YEARS if share.get(y, 0) > 0]
    sy = [y for y in SHOCK_YEARS if share.get(y, 0) > 0]
    if len(ty) < 4 or not sy:
        return None
    a, b = _loglin_fit(ty, [share[y] for y in ty])
    fact = sum(share[y] for y in sy) / len(sy)
    exp = sum(math.exp(a + b * (y - TREND_YEARS[0])) for y in sy) / len(sy)
    return fact / exp if exp > 0 else None


def build() -> dict:
    data = json.loads((OUT / "data.json").read_text())["territories"]
    light = load_zonal()
    zones = sorted(light)

    # национальные суммы света и населения по годам (по 119 зонам)
    nat_light = {y: sum(light[z].get(y, 0) for z in zones) for y in YEARS}
    nat_pop = {}   # None в годы без публикации населения (2020)
    for y in YEARS:
        ps = [_zone_pop(data, z, y) for z in zones]
        ps = [p for p in ps if p]
        nat_pop[y] = sum(ps) if ps else None

    rows = []
    for z in zones:
        lshare = {y: light[z].get(y, 0) / nat_light[y] for y in YEARS
                  if nat_light[y] > 0}
        pshare = {}
        for y in YEARS:
            p = _zone_pop(data, z, y)
            if p and nat_pop[y]:
                pshare[y] = p / nat_pop[y]
        lr = _ratio(lshare)
        pr = _ratio(pshare)
        div = round(math.log(lr) - math.log(pr), 4) \
            if lr and pr else None
        rows.append({
            "id": z,
            "light": {str(y): round(light[z].get(y, 0), 1) for y in YEARS},
            "pop": {str(y): _zone_pop(data, z, y) for y in YEARS},
            "lightRatio": round(lr, 4) if lr else None,
            "popRatio": round(pr, 4) if pr else None,
            "div": div,
        })

    return {"years": YEARS, "rows": rows,
            "natLight": {str(y): round(v, 1) for y, v in nat_light.items()},
            "natPop": {str(y): (round(v) if v else None)
                       for y, v in nat_pop.items()}}


def main() -> None:
    b = build()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "nightlights.json").write_text(json.dumps(
        {"version": VERSION, "trendYears": [TREND_YEARS[0], TREND_YEARS[-1]],
         "shockYears": SHOCK_YEARS, **b}, ensure_ascii=False))
    # надёжные = RELIABLE_TOP ярчайших районов (малые сельские шумны);
    # ранжируем только их - как на лендинге, не всё подряд
    def lsize(r):
        vals = [r["light"][str(y)] for y in TREND_YEARS]
        return sum(vals) / len(vals)
    withdiv = [r for r in b["rows"] if r["div"] is not None]
    reliable = sorted(withdiv, key=lsize, reverse=True)[:RELIABLE_TOP]
    ranked = sorted(reliable, key=lambda r: r["div"])
    nl = b["natLight"]
    print(f"OK: nightlights.json ({len(b['rows'])} зон, {b['years'][0]}-{b['years'][-1]})")
    print(f"  нац. свет {b['years'][0]}->{b['years'][-1]}: "
          f"{nl[str(b['years'][0])] / 1e6:.1f}М -> {nl[str(b['years'][-1])] / 1e6:.1f}М "
          f"(рост уровня - версия VNL; используются ДОЛИ)")
    print(f"  доля света отстаёт от доли населения (топ-{RELIABLE_TOP} по свету):")
    for r in ranked[:6]:
        print(f"    {r['id']:16s} div {r['div']:+.3f} "
              f"(доля света ×{r['lightRatio']:.2f} / доля насел. ×{r['popRatio']:.2f})")


if __name__ == "__main__":
    main()
