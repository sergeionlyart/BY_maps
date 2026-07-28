"""INF-15 v3: извлечение слоя крупных рек Беларуси из OSM PBF.

Тот же источник и тот же паттерн извлечения, что и у дорожного графа
(`etl/osm_graph.py`, INF-04) - тот же PBF (Geofabrik belarus-latest),
версия/md5 фиксируются в data/raw/osm/registry.csv. Сам PBF в репозиторий
не вендорится (~0,3 ГБ) - фиксируется контрольной суммой.

Вход: `waterway=river` (главные реки, не ручьи/каналы - `stream`/`canal`
явно исключены). Многие крупные реки представлены в OSM как relation
type=waterway (route), но КАЖДЫЙ сегмент-way внутри такого отношения уже
несёт свой собственный тег `waterway=river` - поэтому простого обхода
`way()`-хендлера достаточно, без обработки relations.

Выход: data/raw/osm/river_edges.csv.gz - рёбра (node_a, node_b,
lat/lon концов, name, name:ru) - тот же формат, что и graph_edges.csv.gz,
плюс имя реки для последующей визуальной сверки (шаг 3.3 ТЗ v3 - "10 из
12 крупнейших городов стоят там, где река встречается с дорогой").

Запуск (требует pyosmium; однократно):
  python -m etl.osm_rivers <path.pbf>
"""
from __future__ import annotations

import csv
import gzip
import sys

import osmium

from .common import ROOT

OUT_DIR = ROOT / "data" / "raw" / "osm"

RIVER_CLASSES = {"river"}


class RiverHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.edges = []

    def way(self, w):
        wt = w.tags.get("waterway")
        if wt not in RIVER_CLASSES:
            return
        name = w.tags.get("name") or ""
        name_ru = w.tags.get("name:ru") or ""
        nodes = [(n.ref, n.location.lat, n.location.lon)
                 for n in w.nodes if n.location.valid()]
        for (a, la, lo), (b, lb, lo2) in zip(nodes, nodes[1:]):
            self.edges.append((a, b, la, lo, lb, lo2, name, name_ru))


def main() -> None:
    pbf = sys.argv[1]
    h = RiverHandler()
    h.apply_file(pbf, locations=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "river_edges.csv.gz"
    with gzip.open(out, "wt", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["node_a", "node_b", "lat_a", "lon_a", "lat_b", "lon_b",
                    "name", "name_ru"])
        for e in h.edges:
            w.writerow([e[0], e[1], f"{e[2]:.6f}", f"{e[3]:.6f}",
                        f"{e[4]:.6f}", f"{e[5]:.6f}", e[6], e[7]])
    names = sorted({e[7] or e[6] for e in h.edges if (e[6] or e[7])})
    print(f"OK: {out} ({len(h.edges):,} рёбер, {len(names)} именованных рек)")
    print("реки:", ", ".join(names[:60]), "…" if len(names) > 60 else "")


if __name__ == "__main__":
    main()
