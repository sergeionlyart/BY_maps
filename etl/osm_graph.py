"""INF-04: извлечение дорожного графа Беларуси из OSM PBF.

Вход: belarus-latest.osm.pbf (Geofabrik; версия и md5 фиксируются в
data/raw/osm/registry.csv — сам PBF в репозиторий не вендорится, ~0,3 ГБ).
Выход: data/raw/osm/graph_edges.csv.gz - рёбра дорожного графа
(node_a, node_b, lat/lon концов, класс дороги, скорость км/ч);
длина и минуты НЕ хранятся - потребитель (etl/access.py) считает их
гаверсинусом из координат.

Классы и скорости (км/ч) - консервативные средние для Беларуси:
motorway 105, trunk 90, primary 75, secondary 60, tertiary 45.
Меньшие классы не включаются: для межрайонного травел-тайма достаточно
(каждый райцентр в пределах пары км от дороги secondary+).

Запуск (требует pyosmium; однократно): python -m etl.osm_graph <path.pbf>
"""
from __future__ import annotations

import csv
import gzip
import sys

import osmium

from .common import ROOT

OUT_DIR = ROOT / "data" / "raw" / "osm"

SPEEDS = {"motorway": 105, "trunk": 90, "primary": 75,
          "secondary": 60, "tertiary": 45}
LINK_OF = {f"{k}_link": v for k, v in SPEEDS.items()}
ALL_SPEEDS = {**SPEEDS, **LINK_OF}


class RoadHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.edges = []

    def way(self, w):
        hw = w.tags.get("highway")
        if hw not in ALL_SPEEDS:
            return
        speed = ALL_SPEEDS[hw]
        nodes = [(n.ref, n.location.lat, n.location.lon)
                 for n in w.nodes if n.location.valid()]
        for (a, la, lo), (b, lb, lo2) in zip(nodes, nodes[1:]):
            self.edges.append((a, b, la, lo, lb, lo2, hw, speed))


def main() -> None:
    pbf = sys.argv[1]
    h = RoadHandler()
    h.apply_file(pbf, locations=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "graph_edges.csv.gz"
    with gzip.open(out, "wt", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["node_a", "node_b", "lat_a", "lon_a", "lat_b", "lon_b",
                    "highway", "speed_kmh"])
        for e in h.edges:
            w.writerow([e[0], e[1], f"{e[2]:.6f}", f"{e[3]:.6f}",
                        f"{e[4]:.6f}", f"{e[5]:.6f}", e[6], e[7]])
    print(f"OK: {out} ({len(h.edges):,} рёбер)")


if __name__ == "__main__":
    main()
