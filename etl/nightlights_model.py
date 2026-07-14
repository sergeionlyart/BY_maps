"""INF-08 v2, шаг 4: модель светимости 2030-2075 (stdlib).

НЕ прогноз света, а модельная иллюстрация демографического прогноза:
«как выглядела бы карта света, если бы светимость следовала за
населением при прочих равных». Санкции, энергетика, технологии
освещения моделью не учитываются (LIMITATIONS).

Форма (ТЗ T-4):
  light_i(t) = bright_i(2024) * (pop_i(t)/pop_i(2024))^beta_class(i)
               + floor_i,
где floor_i - неисчезающая инфраструктурная подсветка (дороги, объекты):
суммарная радиансность пикселей 1..floor_max_nw нВт в 2024 г.
(data/raw/nightlights/floor_2024.csv, из растра VNL-2024);
bright_i - остальной (яркий) свет 2024 г.

Эластичность beta - МЕЖРАЙОННАЯ (долгосрочная): ln(bright_2024) ~
ln(pop_2024) по зонам класса (Минск+агломерация / облцентры /
промышленные (моногорода высокой зависимости, INF-06) / сельские).
На горизонте 50 лет уместна равновесная связь «сколько света имеет
район данного размера», а не краткосрочная реакция. ВНУТРИрайонная
панель 2012-2024 (FE зоны+года; диагностика estimate_beta) связи
почти не видит - свет инерционен, у сельских даже отрицателен
(модернизация освещения при убыли населения); это публикуемое
ограничение модели. Для урбан-классов (7 зон, межрайонная оценка не
идентифицируется) принята пропорциональность beta=1. Все параметры -
params/assumptions.json (+ YAML-зеркало).

Анкер adjusted-ветки: измеренный свет 2024 г. произведён фактическим
населением, которое в конвенции adjusted ниже официального - поэтому
знаменатель (pop 2024) для jumpoff=adjusted умножается на отношение
adjusted/official населения области на старте прогноза (2026); иначе
adjusted-ветка систематически занижалась бы на (отношение)^beta при
идентичной динамике.

Входы прогноза: forecast.json v2026.4 - 3 сценария x 2 стартовых ряда;
у районов есть только официальный старт, adjusted-ряд района =
официальный * (область_adjusted/область_official) - незарегистрированный
отток по районам не раскладывается (WP-F3), принято равномерное
масштабирование внутри области.

Запуск: python -m etl.nightlights_model (диагностика панели);
библиотечно - etl/nightlights_v2.py.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from .common import ROOT, OUT

RAW = ROOT / "data" / "raw" / "nightlights"

SCENARIOS = ["base", "negative", "optimistic"]
JUMPOFFS = ["official", "adjusted"]


def load_assumptions() -> dict:
    for p in [ROOT / "params" / "assumptions.json",
              ROOT / "artifacts" / "nightlights" / "params"
              / "assumptions.json"]:
        if p.exists():
            return json.loads(p.read_text())
    raise SystemExit("нет params/assumptions.json")


def zone_class(assump: dict) -> dict[str, str]:
    """Класс каждой зоны; приоритет agglo > oblast_center > industrial."""
    cls = {}
    c = assump["model"]["classes"]
    for name in ["minsk_agglo", "oblast_center", "industrial"]:
        for z in c[name]:
            cls.setdefault(z, name)
    return cls


def _pop(data: dict, zid: str, year: int) -> float | None:
    v = data.get(zid)
    if not v:
        return None
    p = v["pop"].get(str(year))
    return float(p[0]) if p else None


def load_panel(assump: dict) -> tuple[list[str], list[int], dict, dict]:
    """(зоны, годы панели, свет L[z][y], население P[z][y])."""
    y0, y1 = assump["model"]["panel_years"]
    skip = set(assump["model"]["panel_skip_years"])
    years = [y for y in range(y0, y1 + 1) if y not in skip]
    light: dict[str, dict[int, float]] = {}
    with open(RAW / "zonal_vnl.csv") as f:
        for r in csv.DictReader(f):
            if r["zone_id"] != "BY":
                light.setdefault(r["zone_id"], {})[int(r["year"])] = \
                    float(r["radiance"])
    data = json.loads((OUT / "data.json").read_text())["territories"]
    zones = sorted(light)
    pop = {z: {y: _pop(data, z, y) for y in years} for z in zones}
    return zones, years, light, pop


def estimate_beta(assump: dict) -> dict:
    """Панельные beta по классам: two-way FE + long-difference."""
    zones, years, light, pop = load_panel(assump)
    cls = zone_class(assump)
    out = {}
    for cname in ["minsk_agglo", "oblast_center", "industrial", "rural"]:
        zs = [z for z in zones
              if cls.get(z, "rural") == cname]
        obs = [(z, y, math.log(light[z][y]), math.log(pop[z][y]))
               for z in zs for y in years
               if light[z].get(y, 0) > 0 and pop[z].get(y)]
        # two-way демининг (панель сбалансирована: все зоны x все годы)
        zm = {z: [0.0, 0.0, 0] for z in zs}
        ym = {y: [0.0, 0.0, 0] for y in years}
        gm = [0.0, 0.0, 0]
        for z, y, ll, lp in obs:
            zm[z][0] += ll; zm[z][1] += lp; zm[z][2] += 1
            ym[y][0] += ll; ym[y][1] += lp; ym[y][2] += 1
            gm[0] += ll; gm[1] += lp; gm[2] += 1
        sxx = sxy = 0.0
        resid = []
        for z, y, ll, lp in obs:
            yt = ll - zm[z][0] / zm[z][2] - ym[y][0] / ym[y][2] \
                + gm[0] / gm[2]
            xt = lp - zm[z][1] / zm[z][2] - ym[y][1] / ym[y][2] \
                + gm[1] / gm[2]
            sxx += xt * xt
            sxy += xt * yt
            resid.append((z, xt, yt))
        beta = sxy / sxx if sxx > 0 else None
        # кластер-робастная SE по зонам (CR1)
        se = None
        if beta is not None and sxx > 0:
            gsum: dict[str, float] = {}
            for z, xt, yt in resid:
                gsum[z] = gsum.get(z, 0.0) + xt * (yt - beta * xt)
            g = len(gsum)
            if g > 1:
                meat = sum(v * v for v in gsum.values())
                se = math.sqrt(meat * g / (g - 1)) / sxx
        # long-difference 2012->2024 (робастность)
        y0, y1 = years[0], years[-1]
        xs, ys = [], []
        for z in zs:
            if (light[z].get(y0, 0) > 0 and light[z].get(y1, 0) > 0
                    and pop[z].get(y0) and pop[z].get(y1)):
                xs.append(math.log(pop[z][y1] / pop[z][y0]))
                ys.append(math.log(light[z][y1] / light[z][y0]))
        ld = None
        if len(xs) >= 3:
            n = len(xs)
            mx, my = sum(xs) / n, sum(ys) / n
            sxx2 = sum((x - mx) ** 2 for x in xs)
            if sxx2 > 1e-12:
                ld = sum((x - mx) * (yy - my)
                         for x, yy in zip(xs, ys)) / sxx2
        out[cname] = {"beta_fe": beta, "se_cluster": se,
                      "beta_longdiff": ld, "n_zones": len(zs),
                      "n_obs": len(obs)}
    return out


def estimate_beta_cross(assump: dict) -> dict:
    """Межрайонные эластичности: ln(bright_2024) ~ ln(pop_2024) по
    классам (источник принятых beta для industrial/rural) + пул."""
    zones, years, light, pop = load_panel(assump)
    cls = zone_class(assump)
    floor = load_floor()
    base_year = assump["model"]["base_year"]
    out = {}
    groups = {"urban": ["minsk_agglo", "oblast_center"],
              "industrial": ["industrial"], "rural": ["rural"],
              "all": ["minsk_agglo", "oblast_center", "industrial",
                      "rural"]}
    for g, members in groups.items():
        xs, ys = [], []
        for z in zones:
            if cls.get(z, "rural") in members \
                    and floor[z]["bright"] > 0 and pop[z].get(base_year):
                xs.append(math.log(pop[z][base_year]))
                ys.append(math.log(floor[z]["bright"]))
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
        ssr = sum((y - (my + b * (x - mx))) ** 2 for x, y in zip(xs, ys))
        sst = sum((y - my) ** 2 for y in ys)
        se = math.sqrt(ssr / (n - 2) / sxx) if n > 2 else None
        out[g] = {"beta": b, "se": se, "r2": 1 - ssr / sst, "n": n}
    return out


def load_floor() -> dict[str, dict[str, float]]:
    out = {}
    with open(RAW / "floor_2024.csv") as f:
        for r in csv.DictReader(f):
            out[r["zone_id"]] = {"floor": float(r["floor_radiance"]),
                                 "bright": float(r["bright_radiance"])}
    return out


def _interp_nodes(years: list[int], vals: list[float],
                  nodes: list[int]) -> dict[int, float]:
    """Лог-линейная интерполяция ряда прогноза на узлы модели."""
    out = {}
    for t in nodes:
        if t <= years[0]:
            out[t] = vals[0]
            continue
        if t >= years[-1]:
            out[t] = vals[-1]
            continue
        for a, b in zip(range(len(years) - 1), range(1, len(years))):
            if years[a] <= t <= years[b]:
                w = (t - years[a]) / (years[b] - years[a])
                out[t] = math.exp((1 - w) * math.log(vals[a])
                                  + w * math.log(vals[b]))
                break
    return out


def future_pop(assump: dict) -> dict:
    """P[jumpoff][scenario][zone][node] на узлы модели из forecast.json."""
    fc = json.loads((OUT / "forecast.json").read_text())
    terr, adj = fc["territories"], fc["adjusted"]
    data = json.loads((OUT / "data.json").read_text())["territories"]
    nodes = assump["model"]["nodes"]
    zones = [z for z in terr if z.startswith("r-")] + ["BY-HM"]
    out: dict = {j: {s: {} for s in SCENARIOS} for j in JUMPOFFS}
    for s in SCENARIOS:
        # масштаб области: adjusted/official по годам прогноза
        obl_ratio: dict[str, dict[int, float]] = {}
        for ob, entry in adj.items():
            e_adj, e_off = entry[s], terr[ob][s]
            obl_ratio[ob] = {y: pa / po for y, pa, po in
                             zip(e_adj["years"], e_adj["pop"], e_off["pop"])}
        for z in zones:
            e = terr[z][s]
            off = _interp_nodes(e["years"], e["pop"], nodes)
            out["official"][s][z] = off
            parent = "BY-HM" if z == "BY-HM" else data[z]["parent"]
            ratio = _interp_nodes(sorted(obl_ratio[parent]),
                                  [obl_ratio[parent][y]
                                   for y in sorted(obl_ratio[parent])],
                                  nodes)
            out["adjusted"][s][z] = {t: off[t] * ratio[t] for t in nodes}
    return out


def _jumpoff_ratio0(data: dict) -> dict[str, float]:
    """Отношение adjusted/official населения области на старте прогноза
    (2026) по зонам - анкер-поправка знаменателя adjusted-ветки
    (на старте прогноза отношение одинаково во всех сценариях)."""
    fc = json.loads((OUT / "forecast.json").read_text())
    terr, adj = fc["territories"], fc["adjusted"]
    out = {}
    for z in [q for q in terr if q.startswith("r-")] + ["BY-HM"]:
        parent = "BY-HM" if z == "BY-HM" else data[z]["parent"]
        out[z] = (adj[parent]["base"]["pop"][0]
                  / terr[parent]["base"]["pop"][0])
    return out


def future_light(assump: dict) -> dict:
    """Модельная светимость: L[jumpoff][scenario][zone][node] и
    факторы яркой компоненты F[...] (для растровых полей)."""
    data = json.loads((OUT / "data.json").read_text())["territories"]
    floor = load_floor()
    betas = assump["model"]["beta"]
    cls = zone_class(assump)
    base_year = assump["model"]["base_year"]
    pops = future_pop(assump)
    ratio0 = _jumpoff_ratio0(data)
    light: dict = {}
    factor: dict = {}
    for j in JUMPOFFS:
        light[j], factor[j] = {}, {}
        for s in SCENARIOS:
            light[j][s], factor[j][s] = {}, {}
            for z, nodes in pops[j][s].items():
                p0 = _pop(data, z, base_year)
                if j == "adjusted":
                    p0 *= ratio0[z]
                b = betas[cls.get(z, "rural")]
                fz, lz = {}, {}
                for t, p in nodes.items():
                    f = (p / p0) ** b
                    fz[t] = f
                    lz[t] = floor[z]["bright"] * f + floor[z]["floor"]
                light[j][s][z] = lz
                factor[j][s][z] = fz
    return {"light": light, "factor": factor,
            "nodes": assump["model"]["nodes"]}


def main() -> None:
    assump = load_assumptions()
    cross = estimate_beta_cross(assump)
    print("Межрайонные эластичности (ln bright_2024 ~ ln pop_2024) - "
          "источник beta:")
    for g, e in cross.items():
        se = f"{e['se']:.3f}" if e["se"] else "-"
        print(f"  {g:12s} b={e['beta']:+.3f} (SE {se}) R²={e['r2']:.2f} "
              f"n={e['n']}")
    est = estimate_beta(assump)
    print("Внутрирайонная панель (FE зоны+года; диагностика - связь "
          "слабая, в модели НЕ используется):")
    for c, e in est.items():
        fe = f"{e['beta_fe']:+.3f}" if e["beta_fe"] is not None else "-"
        se = f"{e['se_cluster']:.3f}" if e["se_cluster"] else "-"
        ld = f"{e['beta_longdiff']:+.3f}" if e["beta_longdiff"] is not None \
            else "-"
        used = assump["model"]["beta"][c]
        print(f"  {c:14s} FE {fe} (SE {se}) | long-diff {ld} | "
              f"n={e['n_zones']} зон | принято {used}")
    fl = future_light(assump)
    nodes = fl["nodes"]
    for j in JUMPOFFS:
        for s in SCENARIOS:
            tot0 = sum(v[nodes[0]] for v in fl["light"][j][s].values())
            tot1 = sum(v[nodes[-1]] for v in fl["light"][j][s].values())
            print(f"  {j}/{s}: нац. модельный свет {nodes[0]} "
                  f"{tot0 / 1e3:.0f}К -> {nodes[-1]} {tot1 / 1e3:.0f}К "
                  f"({(tot1 / tot0 - 1) * 100:+.0f}%)")


if __name__ == "__main__":
    main()
