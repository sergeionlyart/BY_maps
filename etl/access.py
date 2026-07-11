"""INF-04 `access`: транспортная доступность и «тень Минска».

Вопрос: подтверждается ли градиент - пригород (<45 мин до Минска или
облцентра) растёт, кольцо 1,5-2,5 ч убывает быстрее всего, дальняя
периферия - медленнее; что изменило закрытие границ с ЕС для западных
районов?

Данные: дорожный граф из OSM (Geofabrik belarus-latest.osm.pbf; версия и
md5 - data/raw/osm/registry.csv; извлечение - etl/osm_graph.py, классы
motorway..tertiary со скоростями 105/90/75/60/45 км/ч). Травел-тайм -
Дейкстра по неориентированному графу от узла, ближайшего к райцентру,
до Минска и ближайшего облцентра. Зарплатный контроль - INF-03
(etl.wages). Погранпереходы с ЕС - реестр data/curated/border_crossings.csv
(разведка с источниками): доступность ЕС в 2019 и 2026.

Запуск: python -m etl.access -> web/public/data/access.json
                               data/curated/travel_times.csv
"""
from __future__ import annotations

import csv
import gzip
import heapq
import json
import math
import statistics

from .common import ROOT, OUT
from .wages import (HOSTED, MINSK_SUBURBS, load_wages, ols, raion_pop,
                    WAGE_YEARS, WINDOW)

RAW_OSM = ROOT / "data" / "raw" / "osm"
CURATED = ROOT / "data" / "curated"
VERSION = "1.0.0"

# пояса доступности до Минска, минуты (спека INF-04: <45 пригород;
# 90-150 = «кольцо 1,5-2,5 ч»)
BELTS = [(0, 45, "<45 мин"), (45, 90, "45-90 мин"),
         (90, 150, "1,5-2,5 ч"), (150, 10_000, ">2,5 ч")]

OBL_CENTER_CITY = {"BY-BR": "c-brest", "BY-VI": "c-viciebsk",
                   "BY-HO": "c-homiel", "BY-HR": "c-hrodna",
                   "BY-MA": "c-mahilou", "BY-HM": "c-minsk"}


def _hav(lat1, lon1, lat2, lon2) -> float:
    """Расстояние по сфере, км."""
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p)
         * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


def load_graph() -> tuple[dict, dict]:
    """(adjacency {node: [(node, минуты)]}, coords {node: (lat, lon)})."""
    adj: dict[int, list] = {}
    coords: dict[int, tuple[float, float]] = {}
    with gzip.open(RAW_OSM / "graph_edges.csv.gz", "rt") as f:
        for r in csv.DictReader(f):
            a, b = int(r["node_a"]), int(r["node_b"])
            la, lo = float(r["lat_a"]), float(r["lon_a"])
            lb, lo2 = float(r["lat_b"]), float(r["lon_b"])
            km = _hav(la, lo, lb, lo2)
            minutes = km / float(r["speed_kmh"]) * 60
            adj.setdefault(a, []).append((b, minutes))
            adj.setdefault(b, []).append((a, minutes))
            coords[a] = (la, lo)
            coords[b] = (lb, lo2)
    return adj, coords


def snap(coords: dict, lat: float, lon: float) -> int:
    """Ближайший узел графа (сеточный индекс для скорости)."""
    best, best_d = None, 1e9
    for node, (la, lo) in coords.items():
        # быстрый прямоугольный фильтр
        if abs(la - lat) > 0.3 or abs(lo - lon) > 0.5:
            continue
        d = _hav(lat, lon, la, lo)
        if d < best_d:
            best, best_d = node, d
    assert best is not None and best_d < 15, (lat, lon, best_d)
    return best


def dijkstra(adj: dict, sources: list[int]) -> dict[int, float]:
    dist = {s: 0.0 for s in sources}
    pq = [(0.0, s) for s in sources]
    heapq.heapify(pq)
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, 1e18):
            continue
        for v, w in adj.get(u, ()):
            nd = d + w
            if nd < dist.get(v, 1e18):
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist


def compute_travel_times() -> dict:
    """Травел-таймы райцентров: до Минска, ближайшего облцентра, ЕС-2019/2026.

    Возвращает {terr: {'minsk': мин, 'obl': мин, 'obl_id': ..,
                       'eu2019': мин|None, 'eu2026': мин|None}}."""
    data = json.loads((OUT / "data.json").read_text())["territories"]
    adj, coords = load_graph()

    def city_node(cid: str) -> int:
        c = data[cid]
        return snap(coords, c["lat"], c["lon"])

    # источники: облцентры (и Минск)
    obl_nodes = {o: city_node(c) for o, c in OBL_CENTER_CITY.items()}
    dist_from = {o: dijkstra(adj, [n]) for o, n in obl_nodes.items()}

    # погранпереходы с ЕС (реестр разведки); три состояния:
    # 2019 (13 легковых), надир 03.2024-11.2025 (4), 07.2026 (6)
    borders = list(csv.DictReader(open(CURATED / "border_crossings.csv")))

    def eu_dist(col: str) -> dict[int, float]:
        nodes = [snap(coords, float(b["lat"]), float(b["lon"]))
                 for b in borders if b[col] == "open"]
        return dijkstra(adj, nodes)

    dist_eu19 = eu_dist("status_2019")
    dist_eu_nadir = eu_dist("status_nadir")
    dist_eu26 = eu_dist("status_2026")

    out = {}
    for t, v in data.items():
        if v["level"] != "raion":
            continue
        centers = v.get("center") or []
        if t in HOSTED:
            node = city_node(HOSTED[t])
        elif t == "r-minski":
            node = obl_nodes["BY-HM"]
        elif centers and data[centers[0]].get("lat"):
            node = city_node(centers[0])
        else:
            # район без города-центра с координатами: центроид не считаем,
            # снап по средней точке имеющихся городов района либо пропуск
            raise AssertionError(f"нет координат центра: {t}")
        d_minsk = dist_from["BY-HM"].get(node)
        obl_id, d_obl = min(((o, dist_from[o].get(node, 1e18))
                             for o in obl_nodes), key=lambda kv: kv[1])
        out[t] = {
            "minsk": round(d_minsk, 1) if d_minsk is not None else None,
            "obl": round(d_obl, 1),
            "obl_id": obl_id,
            "eu2019": round(dist_eu19.get(node, 1e18), 1),
            "euNadir": round(dist_eu_nadir.get(node, 1e18), 1),
            "eu2026": round(dist_eu26.get(node, 1e18), 1),
        }
    return out


def belt_of(minutes: float) -> str:
    for lo, hi, name in BELTS:
        if lo <= minutes < hi:
            return name
    return BELTS[-1][2]


def build() -> dict:
    tt = compute_travel_times()
    wages = load_wages()
    data = json.loads((OUT / "data.json").read_text())["territories"]
    minsk_w = wages["BY-HM"]
    y0, y1 = WINDOW

    rows = []
    for t, v in sorted(tt.items()):
        w = wages[t]
        rel = [w[y] / minsk_w[y] for y in WAGE_YEARS if y in w and y in minsk_w]
        p0, p1 = raion_pop(data, t, y0), raion_pop(data, t, y1)
        centers = data[t].get("center") or []
        cpop = sum(float(data[c]["pop"].get(str(y0), [0])[0]) for c in centers
                   if str(y0) in data[c]["pop"])
        # эффективная доступность: минимум (Минск, ближайший облцентр);
        # Минск сам входит в OBL_CENTER_CITY, поэтому eff == v["obl"] -
        # min оставлен для читаемости семантики
        eff = min(v["minsk"], v["obl"])
        rows.append({
            "id": t, **v,
            "eff": round(eff, 1),
            "belt": belt_of(v["minsk"]),
            "belt_eff": belt_of(eff),
            "pop_change": p1 / p0 - 1,
            "wage_rel": sum(rel) / len(rel),
            "center_pop": max(cpop, 1.0),
        })

    # профиль по поясам (до Минска и по эффективной доступности);
    # квартели - statistics.quantiles(method="inclusive")
    def profile(key: str) -> list[dict]:
        prof = []
        for _, _, name in BELTS:
            grp = [r for r in rows if r[key] == name]
            if not grp:
                continue
            vals = sorted(r["pop_change"] * 100 for r in grp)
            if len(vals) >= 2:
                q25, med, q75 = statistics.quantiles(vals, n=4,
                                                     method="inclusive")
            else:
                q25 = med = q75 = vals[0]
            prof.append({
                "belt": name, "n": len(vals),
                "median": round(med, 2),
                "q25": round(q25, 2),
                "q75": round(q75, 2),
            })
        return prof

    # регрессия: динамика ~ пояса (категории) + контроли INF-03
    base_belt = BELTS[-1][2]  # референс: дальняя периферия
    belt_names = [b[2] for b in BELTS if b[2] != base_belt]
    y = [r["pop_change"] * 100 for r in rows]
    xs = [[1.0 if r["belt_eff"] == b else 0.0 for r in rows]
          for b in belt_names]
    xs.append([math.log(r["wage_rel"]) for r in rows])
    xs.append([math.log(r["center_pop"]) for r in rows])
    reg = ols(y, xs)
    reg_nowage = ols(y, xs[:len(belt_names)] + [xs[-1]])

    # западный блок: изменение доступности ЕС 2019 -> надир -> 2026
    for r in rows:
        r["eu_delta"] = round(r["eu2026"] - r["eu2019"], 1)
        r["eu_delta_nadir"] = round(r["euNadir"] - r["eu2019"], 1)
    west = sorted(rows, key=lambda r: r["eu2019"])[:30]

    return {"rows": rows, "profile_minsk": profile("belt"),
            "profile_eff": profile("belt_eff"),
            "reg": reg, "reg_nowage": reg_nowage,
            "belt_names": belt_names, "base_belt": base_belt,
            "west30": [r["id"] for r in west]}


def main() -> None:
    b = build()
    rows = b["rows"]

    terrs = {}
    for r in rows:
        terrs[r["id"]] = {
            "minMinsk": r["minsk"], "minObl": r["obl"], "oblId": r["obl_id"],
            "eff": r["eff"], "belt": r["belt"], "beltEff": r["belt_eff"],
            "eu2019": r["eu2019"], "euNadir": r["euNadir"],
            "eu2026": r["eu2026"],
            "euDelta": r["eu_delta"], "euDeltaNadir": r["eu_delta_nadir"],
            "popChange": round(r["pop_change"] * 100, 2),
            "wageRel": round(r["wage_rel"], 4),
        }

    def reg_out(v: dict) -> dict:
        return {"beta": [round(x, 3) for x in v["beta"]],
                "se": [round(x, 3) for x in v["se"]],
                "seHc1": [round(x, 3) for x in v["se_hc1"]],
                "r2": round(v["r2"], 3), "n": v["n"]}

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "access.json").write_text(json.dumps({
        "version": VERSION,
        "window": list(WINDOW),
        "belts": [b_[2] for b_ in BELTS],
        "baseBelt": b["base_belt"],
        "beltNames": b["belt_names"],
        "territories": terrs,
        "profileMinsk": b["profile_minsk"],
        "profileEff": b["profile_eff"],
        "regression": reg_out(b["reg"]),
        "regressionNoWage": reg_out(b["reg_nowage"]),
        "west30": b["west30"],
    }, ensure_ascii=False))

    with open(CURATED / "travel_times.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["territory_id", "min_minsk",
                                          "min_oblcenter", "oblcenter",
                                          "min_eu_2019", "min_eu_nadir",
                                          "min_eu_2026"],
                           lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({"territory_id": r["id"], "min_minsk": r["minsk"],
                        "min_oblcenter": r["obl"], "oblcenter": r["obl_id"],
                        "min_eu_2019": r["eu2019"],
                        "min_eu_nadir": r["euNadir"],
                        "min_eu_2026": r["eu2026"]})

    print(f"OK: access.json ({len(rows)} районов)")
    for p in b["profile_eff"]:
        print(f"  {p['belt']:>10s}: n={p['n']:3d} медиана {p['median']:+.1f}% "
              f"[{p['q25']:+.1f}; {p['q75']:+.1f}]")
    reg = b["reg"]
    for i, name in enumerate(b["belt_names"]):
        print(f"  пояс {name:>10s}: {reg['beta'][i + 1]:+6.2f} п.п. "
              f"(HC1 SE {reg['se_hc1'][i + 1]:.2f}) к базе «{b['base_belt']}»")
    print(f"  контроль ln(wage_rel): {reg['beta'][len(b['belt_names']) + 1]:.2f}; "
          f"R²={reg['r2']:.3f}")


if __name__ == "__main__":
    main()
