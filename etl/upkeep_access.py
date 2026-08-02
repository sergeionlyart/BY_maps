"""INF-16 `upkeep`: доступность до расширенного набора целей (школа/ФАП/почта/
банк/станция) поверх дорожного графа INF-04.

Тонкая обёртка над `etl.access` — гейт G-9 ТЗ INF-16 требует тождественности
констант/графа с INF-04, а не параллельной реализации. Этот модуль НЕ форкает
`BELTS`, граф или Дейкстру: он их импортирует и переиспользует на новом наборе
целевых точек.

`SPEEDS` (скорости по классам дорог) как рантайм-константа фактически не
существует в `etl.access` — он используется только один раз, на этапе
извлечения графа (`etl.osm_graph.SPEEDS`), и уже "запечён" в
`graph_edges.csv.gz` как поле `speed_kmh` на каждом ребре; `etl.access.
load_graph()` читает это поле напрямую. Формулировка Приложения А ТЗ
(«импортирует BELTS/SPEEDS/граф») в этой части неточна буквально — по смыслу
(тождественность методики) она выполняется тем, что этот модуль читает ТОТ ЖЕ
`graph_edges.csv.gz` через ТУ ЖЕ `load_graph()`, а не пересчитывает скорости
заново. Зафиксировано как уточнение, не как отклонение от гейта G-9.

Статус на майлстоуне 2: координаты целей (`etl/upkeep_network.py`,
`data/raw/osm/upkeep_poi.csv`) готовы — `build()` ниже считает `access_now`
(минуты до ближайшей точки категории) для всех 118 районов на реальных
данных. Разрешение «район -> узел графа» (`raion_center_node`) — минимальное,
неизбежное дублирование: сама методология доступности (граф/`BELTS`/
Дейкстра) по-прежнему импортируется, не форкается (гейт G-9); повторяется
только маленький, нейтральный шаг «какой узел графа представляет район»
(тот же алгоритм, что `etl.access.compute_travel_times`: житель района
райцентра, кроме особого случая Минского района — снап на узел Минска, как
и в access.py). Не вынесено в переиспользуемую функцию `etl.access`, т.к.
это правка чужого файла требует отдельного согласования (раздел 10 ТЗ) —
не сделано в этом майлстоуне.

Запуск: python -m etl.upkeep_access -> data/curated/upkeep_access_now.csv
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict

from .access import BELTS, dijkstra, load_graph, snap, belt_of
from .common import ROOT, OUT
from .wages import HOSTED

# etl.osm_graph.SPEEDS (motorway 105 / trunk 90 / primary 75 / secondary 60 /
# tertiary 45 км/ч) НЕ импортируется здесь намеренно: этот модуль требует
# `osmium`, который нужен только для (пере)извлечения PBF -> graph_edges.csv.gz
# и не установлен в рантайм-окружении доступности. Скорости уже "запечены" в
# graph_edges.csv.gz (поле speed_kmh) и попадают в этот модуль через
# load_graph() - см. docstring модуля.

# Новые целевые категории (сверх Минска/облцентра/границы ЕС INF-04) -
# состав зафиксирован ТЗ §1/§6 позиция 9. Названия категорий - как в
# etl.upkeep_network (источник координат), "post"/"station" из
# первоначального наброска ТЗ переименованы в "post_office"/"station" для
# согласованности с upkeep_poi.csv.
TARGET_CATEGORIES = ("school", "fap", "post_office", "bank", "station")

POI_CSV = ROOT / "data" / "raw" / "osm" / "upkeep_poi.csv"
DATA_JSON = OUT / "data.json"
ACCESS_NOW_OUT = ROOT / "data" / "curated" / "upkeep_access_now.csv"


def compute_target_travel_times(adj: dict, coords: dict,
                                target_points: list[tuple[float, float]],
                                ) -> dict[int, float]:
    """Многоисточниковая Дейкстра до ближайшей точки набора `target_points`.

    `adj`/`coords` - результат `etl.access.load_graph()` (тот же граф, что
    и INF-04, без повторного извлечения). `target_points` - [(lat, lon), ...]
    точек одной категории (например, все школы страны). Возвращает
    {node: минуты до ближайшей точки категории} - формат идентичен тому,
    что `etl.access.compute_travel_times()` уже делает для облцентров/ЕС,
    просто с иным источником узлов-целей.
    """
    if not target_points:
        raise ValueError("target_points пуст - нечего снапать на граф")
    nodes = []
    n_skipped = 0
    for lat, lon in target_points:
        try:
            nodes.append(snap(coords, lat, lon))
        except AssertionError:
            # точка дальше 15 км от любого узла графа motorway..tertiary
            # (см. etl.access.snap) - типично край страны/приграничная
            # неточность геометрии; пропускается, не прерывает расчёт
            n_skipped += 1
    if n_skipped:
        print(f"  compute_target_travel_times: пропущено {n_skipped}/"
              f"{len(target_points)} точек дальше 15 км от графа")
    if not nodes:
        raise ValueError("все target_points дальше 15 км от графа")
    return dijkstra(adj, nodes)


def belt_report(dist_by_node: dict[int, float],
                raion_nodes: dict[str, int]) -> dict[str, dict]:
    """{raion_id: {'minutes': ..., 'belt': ...}} для отчёта доступности."""
    out = {}
    for raion_id, node in raion_nodes.items():
        minutes = dist_by_node.get(node)
        out[raion_id] = {
            "minutes": round(minutes, 1) if minutes is not None else None,
            "belt": belt_of(minutes) if minutes is not None else None,
        }
    return out


def load_target_points(category: str) -> list[tuple[float, float]]:
    """Координаты категории из data/raw/osm/upkeep_poi.csv (etl.upkeep_network)."""
    pts = []
    with POI_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["category"] == category:
                pts.append((float(row["lat"]), float(row["lon"])))
    return pts


def raion_center_nodes(coords: dict) -> dict[str, int]:
    """{raion_id: узел графа, представляющий район} - тот же алгоритм
    разрешения источника, что etl.access.compute_travel_times (райцентр,
    Минский район - особый случай снапа на Минск)."""
    data = json.loads(DATA_JSON.read_text())["territories"]

    def city_node(cid: str) -> int:
        c = data[cid]
        return snap(coords, c["lat"], c["lon"])

    minsk_node = city_node("c-minsk")
    out = {}
    for t, v in data.items():
        if v.get("level") != "raion":
            continue
        centers = v.get("center") or []
        if t in HOSTED:
            out[t] = city_node(HOSTED[t])
        elif t == "r-minski":
            out[t] = minsk_node
        elif centers and data[centers[0]].get("lat"):
            out[t] = city_node(centers[0])
        else:
            raise AssertionError(f"нет координат центра: {t}")
    return out


def build() -> dict[str, dict[str, dict]]:
    """{raion_id: {category: {'minutes':.., 'belt':..}}} для всех 118 районов
    x 5 базовых целей доступности (школа/ФАП/почта/банк/станция)."""
    adj, coords = load_graph()
    raion_nodes = raion_center_nodes(coords)
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    for cat in TARGET_CATEGORIES:
        pts = load_target_points(cat)
        dist = compute_target_travel_times(adj, coords, pts)
        rep = belt_report(dist, raion_nodes)
        for rid, v in rep.items():
            out[rid][cat] = v
    return dict(out)


def main() -> None:
    result = build()
    ACCESS_NOW_OUT.parent.mkdir(parents=True, exist_ok=True)
    with ACCESS_NOW_OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        header = ["raion_id"] + [f"{c}_min" for c in TARGET_CATEGORIES] + \
            [f"{c}_belt" for c in TARGET_CATEGORIES]
        w.writerow(header)
        for rid in sorted(result):
            row = [rid]
            row += [result[rid][c]["minutes"] for c in TARGET_CATEGORIES]
            row += [result[rid][c]["belt"] for c in TARGET_CATEGORIES]
            w.writerow(row)
    n_missing = sum(1 for rid in result for c in TARGET_CATEGORIES
                    if result[rid][c]["minutes"] is None)
    print(f"upkeep_access: 118 районов x {len(TARGET_CATEGORIES)} целей -> {ACCESS_NOW_OUT}"
          f" ({n_missing} пропусков)")


if __name__ == "__main__":
    main()
