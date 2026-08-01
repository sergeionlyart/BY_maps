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

Статус на майлстоуне 1: координаты целей (школа/ФАП/почта/банк/станция) ещё
не добыты (см. `docs/decisions/INF-16.md` D-005/D-006 — снимок OSM в
`data/raw/osm/` не содержит точек интереса, Overpass API оказался недоступен
в течение сессии M1). Поэтому `compute_target_travel_times()` ниже реализован
и протестирован на синтетическом наборе целей (toy-граф теста G-9), но ещё не
запускался на реальных координатах школ/ФАП/почты/банков/станций — это
входит в этап 4/5 (майлстоун 2), после того как `etl/upkeep_network.py`
поставит координаты.

Запуск (после появления координат целей, майлстоун 2):
    python -m etl.upkeep_access <категория> -> добавка к travel_times.csv
"""
from __future__ import annotations

from .access import BELTS, dijkstra, load_graph, snap, belt_of

# etl.osm_graph.SPEEDS (motorway 105 / trunk 90 / primary 75 / secondary 60 /
# tertiary 45 км/ч) НЕ импортируется здесь намеренно: этот модуль требует
# `osmium`, который нужен только для (пере)извлечения PBF -> graph_edges.csv.gz
# и не установлен в рантайм-окружении доступности. Скорости уже "запечены" в
# graph_edges.csv.gz (поле speed_kmh) и попадают в этот модуль через
# load_graph() - см. docstring модуля.

# Новые целевые категории (сверх Минска/облцентра/границы ЕС INF-04) -
# состав зафиксирован ТЗ §1/§6 позиция 9. Координаты (lat, lon) для каждой
# категории поставляет etl.upkeep_network (не этот модуль - гейт G-9
# проверяет константы/граф, не источник точек).
TARGET_CATEGORIES = ("school", "fap", "post", "bank", "station")


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
    nodes = [snap(coords, lat, lon) for lat, lon in target_points]
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


def main() -> None:
    raise SystemExit(
        "etl.upkeep_access: координаты целевых точек (школа/ФАП/почта/банк/"
        "станция) ещё не собраны (см. docs/decisions/INF-16.md D-005/D-006) - "
        "запуск как самостоятельного пайплайна отложен до майлстоуна 2, "
        "когда etl.upkeep_network поставит координаты. Функции модуля уже "
        "доступны для импорта и покрыты тестом гейта G-9."
    )


if __name__ == "__main__":
    main()
