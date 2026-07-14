"""INF-08 v2, шаг 3: гармонизация ряда светимости 1992-2024 (stdlib).

Задача: единая шкала яркости (радианс-эквивалент VNL) на весь ряд.
Сегменты: 1992-2011 Li et al. calDMSP (DN 0-63); 2012-2024 EOG VNL v2.1.

Прямой стык DMSP-VNL по перекрытию 2012-2013 НЕВОЗМОЖЕН в допусках ТЗ:
оба года - худшие в своих рядах (VNL-2012 - неполный первый год VIIRS,
+55% к 2013; calDMSP 2010-2013 - спутник F18 с остаточным ~2x
завышением уровня после калибровки Li). Поэтому схема «мост», в которой
НИ ОДНА константа не подгоняется на самом стыке:

  1. Коррекция F18-эры: годы 2010-2013 calDMSP умножаются на
     f18 = mean(DN 2006-2009) / mean(DN 2010-2013) - оценка внутри
     DMSP, допущение «нет реального скачка нац. света между эрами».
  2. Отображение DN -> радианс: ln V = a_y + b*ln S на перекрытии
     продуктов simVIIRS (шкала DN Li, та же, что calDMSP) и VNL,
     2014-2024, 119 зон x 11 лет (n=1296), FE года; b и средний
     интерсепт a_bar фиксируются. Гейт ТЗ: R² >= 0,9.
  3. Ретро-сегмент 1992-2011: L_i(y) = exp(a_bar + b*ln(f*DN_i(y))).
  4. Стык (out-of-sample!): |mean(отобр. 2008-2011) /
     mean(VNL 2012-2015) - 1| <= 5% - симметричные 4-летние окна,
     накрывающие мусорные годы обеих сторон; чувствительность к окнам
     раскрывается в отчёте.

Кросс-сенсорная точность зонального уровня на прямом перекрытии
(R² ln-долей 2012/2013 ~0,78) - это потолок ЛЮБОГО метода: собственный
стык рецензированного продукта Li (calDMSP-2013 против simVIIRS-2013)
даёт те же 0,777. Отсюда правило ТЗ §7: районная детализация надёжна
с 2012 года, ретро-сегмент - для страны/областей/классов и помечен
«ретро, грубее».

Спайк-сравнение с «готовым» продуктом (simVIIRS как современный
сегмент) - отклонено: волатильность долей год-к-году в 1,9 раза выше
фактического VNL, 13 нулевых зоно-лет у малых районов (урок v1:
доступность != пригодность).

Запуск: python -m etl.nightlights_harmonize (отчёт в
docs/notes/nightlights_v2_validation.md); библиотечно - nightlights_v2.
"""
from __future__ import annotations

import csv
import json
import math

from .common import ROOT

RAW = ROOT / "data" / "raw" / "nightlights"

DMSP_LAST = 2011          # последний год, берущийся из ретро-сегмента
OVERLAP = [2012, 2013]    # прямое перекрытие сенсоров (для диагностики)
BRIDGE_YEARS = list(range(2014, 2025))
F18_YEARS = list(range(2010, 2014))
F18_PRE = list(range(2006, 2010))
SEAM_RETRO = [2008, 2009, 2010, 2011]
SEAM_VNL = [2012, 2013, 2014, 2015]

R2_GATE = 0.90
SEAM_GATE = 0.05


def _load(fname: str, col: str) -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = {}
    with open(RAW / fname) as f:
        for r in csv.DictReader(f):
            out.setdefault(r["zone_id"], {})[int(r["year"])] = float(r[col])
    return out


def load_dmsp():
    return _load("zonal_dmsp.csv", "dn_sum")


def load_vnl():
    return _load("zonal_vnl.csv", "radiance")


def load_sim():
    return _load("zonal_simviirs.csv", "dn_sum")


def zones(d: dict) -> list[str]:
    return sorted(z for z in d if z != "BY")


def _pearson_r2(xs, ys) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy * sxy / (sxx * syy) if sxx > 0 and syy > 0 else 0.0


def f18_factor(dmsp=None) -> float:
    """Коррекция уровня F18-эры, оценка внутри DMSP."""
    dmsp = dmsp or load_dmsp()
    zs = zones(dmsp)
    nat = {y: sum(dmsp[z][y] for z in zs)
           for y in set(F18_PRE) | set(F18_YEARS)}
    return (sum(nat[y] for y in F18_PRE) / len(F18_PRE)) \
        / (sum(nat[y] for y in F18_YEARS) / len(F18_YEARS))


def fit_bridge(sim=None, vnl=None) -> dict:
    """ln V = a_y + b*ln S на перекрытии simVIIRS/VNL 2014-2024 (FE
    года). Возвращает b, средний интерсепт a_bar, R² (внутригодовой)."""
    sim = sim or load_sim()
    vnl = vnl or load_vnl()
    zs = zones(sim)
    X, Y, inter = [], [], []
    for y in BRIDGE_YEARS:
        sub = [(math.log(sim[z][y]), math.log(vnl[z][y])) for z in zs
               if sim[z].get(y, 0) > 0 and vnl[z].get(y, 0) > 0]
        mx = sum(a for a, _ in sub) / len(sub)
        my = sum(c for _, c in sub) / len(sub)
        inter.append((mx, my))
        X += [a - mx for a, _ in sub]
        Y += [c - my for _, c in sub]
    b = sum(a * c for a, c in zip(X, Y)) / sum(a * a for a in X)
    ss_res = sum((c - b * a) ** 2 for a, c in zip(X, Y))
    ss_tot = sum(c * c for c in Y)
    a_bar = sum(my - b * mx for mx, my in inter) / len(inter)
    return {"b": b, "a_bar": a_bar, "r2": 1 - ss_res / ss_tot,
            "n": len(X), "years": BRIDGE_YEARS}


def harmonized(dmsp=None, vnl=None, bridge=None, f18=None) -> dict:
    """Единый ряд 1992-2024 в радианс-эквиваленте по зонам.

    {"series": {zone: {year: val}}, "source": {year: сегмент},
    "bridge": ..., "f18": ...}. Ни одна константа не оценена на стыке.
    """
    dmsp = dmsp or load_dmsp()
    vnl = vnl or load_vnl()
    bridge = bridge or fit_bridge(vnl=vnl)
    f18 = f18 or f18_factor(dmsp)
    zs = zones(dmsp)
    series: dict[str, dict[int, float]] = {z: {} for z in zs}
    source: dict[int, str] = {}
    for y in sorted({q for z in zs for q in dmsp[z]}):
        if y > DMSP_LAST:
            continue
        source[y] = "dmsp-cal"
        f = f18 if y in F18_YEARS else 1.0
        for z in zs:
            dn = dmsp[z].get(y, 0.0)
            series[z][y] = (math.exp(bridge["a_bar"]
                                     + bridge["b"] * math.log(f * dn))
                            if dn > 0 else 0.0)
    for y in sorted({q for z in zs for q in vnl[z]}):
        source[y] = "vnl"
        for z in zs:
            series[z][y] = vnl[z].get(y, 0.0)
    return {"series": series, "source": source, "bridge": bridge,
            "f18": f18}


def seam_gap(h=None, retro_win=None, vnl_win=None) -> float:
    """Разрыв нац. суммы на стыке: симметричные окна против склейки."""
    h = h or harmonized()
    zs = sorted(h["series"])
    retro_win = retro_win or SEAM_RETRO
    vnl_win = vnl_win or SEAM_VNL
    m = sum(sum(h["series"][z][y] for z in zs) for y in retro_win) \
        / len(retro_win)
    v = sum(sum(h["series"][z][y] for z in zs) for y in vnl_win) \
        / len(vnl_win)
    return m / v - 1.0


def _share_volatility(series, years) -> float:
    zs = zones(series)
    nat = {y: sum(series[z].get(y, 0.0) for z in zs) for y in years}
    diffs = []
    for z in zs:
        for y0, y1 in zip(years, years[1:]):
            s0 = series[z].get(y0, 0.0) / nat[y0]
            s1 = series[z].get(y1, 0.0) / nat[y1]
            if s0 > 0 and s1 > 0:
                diffs.append(abs(math.log(s1 / s0)))
    diffs.sort()
    return diffs[len(diffs) // 2]


def _share_r2(sa, sb, year) -> float:
    zs = [z for z in zones(sa) if sa[z].get(year, 0) > 0
          and sb[z].get(year, 0) > 0]
    na = sum(sa[z][year] for z in zs)
    nb = sum(sb[z][year] for z in zs)
    return _pearson_r2([math.log(sa[z][year] / na) for z in zs],
                       [math.log(sb[z][year] / nb) for z in zs])


def spike_report(dmsp=None, vnl=None, sim=None) -> dict:
    dmsp = dmsp or load_dmsp()
    vnl = vnl or load_vnl()
    sim = sim or load_sim()
    years = list(range(2014, 2025))
    zs = zones(dmsp)
    sim_zero = sum(1 for z in zs for y in years if sim[z].get(y, 0) == 0)
    vnl_zero = sum(1 for z in zs for y in years if vnl[z].get(y, 0) == 0)
    return {
        "volatility_sim": _share_volatility(sim, years),
        "volatility_vnl": _share_volatility(vnl, years),
        "vol_ratio": _share_volatility(sim, years)
        / _share_volatility(vnl, years),
        "zero_zone_years_sim": sim_zero,
        "zero_zone_years_vnl": vnl_zero,
        "li_seam_2013_share_r2": _share_r2(dmsp, sim, 2013),
        "li_seam_2013_nat_gap": (sum(sim[z].get(2013, 0) for z in zs)
                                 / sum(dmsp[z].get(2013, 0)
                                       for z in zs) - 1.0),
    }


def worldpop_crosscheck(vnl=None) -> dict[int, float]:
    """Независимая проверка ряда VNL: R² ln-долей против зональных сумм
    WorldPop fvf (источник v1, 100 м, average_masked) по годам 2015-2023."""
    vnl = vnl or load_vnl()
    wp = _load("zonal_light.csv", "radiance")
    return {y: _share_r2(wp, vnl, y) for y in range(2015, 2024)}


def validation() -> dict:
    dmsp, vnl, sim = load_dmsp(), load_vnl(), load_sim()
    bridge = fit_bridge(sim, vnl)
    f18 = f18_factor(dmsp)
    h = harmonized(dmsp, vnl, bridge, f18)
    gap = seam_gap(h)
    windows = {
        "2|2 (2010-11 | 2012-13)": seam_gap(h, [2010, 2011], [2012, 2013]),
        "3|3 (2009-11 | 2012-14)": seam_gap(h, [2009, 2010, 2011],
                                            [2012, 2013, 2014]),
        "4|4 (2008-11 | 2012-15)": gap,
        "3|4 (2009-11 | 2012-15)": seam_gap(h, [2009, 2010, 2011],
                                            SEAM_VNL),
    }
    overlap_diag = {}
    zs = zones(dmsp)
    for y in OVERLAP:
        overlap_diag[y] = {
            "level_r2": _pearson_r2([dmsp[z][y] for z in zs],
                                    [vnl[z][y] for z in zs]),
            "loglog_r2": _pearson_r2(
                [math.log(dmsp[z][y]) for z in zs if dmsp[z][y] > 0
                 and vnl[z][y] > 0],
                [math.log(vnl[z][y]) for z in zs if dmsp[z][y] > 0
                 and vnl[z][y] > 0]),
            "share_r2": _share_r2(dmsp, vnl, y),
        }
    nat = {y: sum(h["series"][z].get(y, 0.0) for z in zs)
           for y in sorted(h["source"])}
    return {"bridge": bridge, "f18": f18, "seam_gap": gap,
            "seam_windows": windows, "overlap_diag": overlap_diag,
            "spike": spike_report(dmsp, vnl, sim),
            "worldpop_r2": worldpop_crosscheck(vnl),
            "nat_harmonized": nat,
            "gates": {"r2": bridge["r2"] >= R2_GATE,
                      "seam": abs(gap) <= SEAM_GATE}}


def main() -> None:
    v = validation()
    br, sp = v["bridge"], v["spike"]
    lines = [
        "# INF-08 v2: валидация гармонизации DMSP/VIIRS (1992-2024)", "",
        "Схема «мост» (ни одна константа не оценивается на стыке):",
        f"- коррекция F18-эры 2010-2013: x{v['f18']:.4f} "
        f"(mean DN 2006-2009 / mean DN 2010-2013, внутри DMSP)",
        f"- отображение DN->радианс: ln V = a_y + b ln S на перекрытии "
        f"simVIIRS/VNL {br['years'][0]}-{br['years'][-1]}, FE года: "
        f"b={br['b']:.4f}, a_bar={br['a_bar']:.4f}",
        f"- **R² моста = {br['r2']:.4f}** (гейт >= {R2_GATE}, "
        f"n={br['n']}) - {'OK' if v['gates']['r2'] else 'FAIL'}",
        "",
        f"Стык (out-of-sample, симметричные 4-летние окна "
        f"{SEAM_RETRO[0]}-{SEAM_RETRO[-1]} | {SEAM_VNL[0]}-{SEAM_VNL[-1]}):"
        f" **{v['seam_gap'] * 100:+.2f}%** (гейт +-{SEAM_GATE * 100:.0f}%)"
        f" - {'OK' if v['gates']['seam'] else 'FAIL'}",
        "Чувствительность к окнам (мусорные годы: VNL-2012 - неполный "
        "первый год VIIRS; calDMSP-2013 - худший год F18):",
        *[f"- {k}: {g * 100:+.2f}%" for k, g in v["seam_windows"].items()],
        "",
        "Диагностика прямого перекрытия сенсоров 2012-2013 "
        "(почему прямой стык невозможен и почему ретро - «грубее»):",
        *[f"- {y}: R² уровней {d['level_r2']:.3f}, лог-лог "
          f"{d['loglog_r2']:.3f}, ln-долей {d['share_r2']:.3f}"
          for y, d in v["overlap_diag"].items()],
        f"- бенчмарк: собственный стык продукта Li (calDMSP-2013 против "
        f"simVIIRS-2013) даёт R² ln-долей {sp['li_seam_2013_share_r2']:.3f}"
        f" и разрыв {sp['li_seam_2013_nat_gap'] * 100:+.1f}% - "
        "кросс-сенсорный потолок, а не дефект нашей схемы",
        "- вывод ТЗ §7: районная детализация надёжна с 2012; ретро - "
        "страна/области/классы, помечен «ретро, грубее»",
        "",
        "## Спайк: «готовый» продукт (simVIIRS) как современный сегмент "
        "- отклонён",
        f"- медиана |dln доли| год-к-году 2014-2024: simVIIRS "
        f"{sp['volatility_sim']:.4f} против VNL {sp['volatility_vnl']:.4f}"
        f" (x{sp['vol_ratio']:.2f})",
        f"- нулевые зоно-годы малых районов: simVIIRS "
        f"{sp['zero_zone_years_sim']}, VNL {sp['zero_zone_years_vnl']} "
        "(урок v1: нестабильность малых зон)",
        "",
        "Кросс-проверка ряда VNL против независимой обработки WorldPop "
        "fvf (источник v1), R² ln-долей по годам:",
        "- " + ", ".join(f"{y}: {r:.3f}"
                         for y, r in v["worldpop_r2"].items()),
        "",
        f"Гейты: R² {'OK' if v['gates']['r2'] else 'FAIL'}, "
        f"стык {'OK' if v['gates']['seam'] else 'FAIL'}",
    ]
    dst = ROOT / "docs" / "notes" / "nightlights_v2_validation.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nOK: {dst}")


if __name__ == "__main__":
    main()
