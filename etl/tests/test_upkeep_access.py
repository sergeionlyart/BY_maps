"""Тесты INF-16 `upkeep_access`. Гейт G-9 ТЗ: константы/граф доступности
тождественны etl.access, не переизобретены (не число близости - тест на
равенство)."""
from etl import access as access_mod
from etl.upkeep_access import (BELTS, TARGET_CATEGORIES, belt_report,
                               compute_target_travel_times, dijkstra,
                               load_graph, snap)


def test_g9_belts_identical_object():
    """BELTS импортирован, не переопределён - тот же объект в памяти."""
    assert BELTS is access_mod.BELTS


def test_g9_graph_loader_identical_function():
    """load_graph/dijkstra/snap - те же функции, не копии."""
    assert load_graph is access_mod.load_graph
    assert dijkstra is access_mod.dijkstra
    assert snap is access_mod.snap


def test_target_categories_defined():
    assert TARGET_CATEGORIES == ("school", "fap", "post", "bank", "station")


def test_compute_target_travel_times_toy():
    """Игрушечный граф (как test_dijkstra_toy INF-04): многоисточниковая
    Дейкстра до ближайшей цели новой категории."""
    adj = {1: [(2, 10.0), (3, 25.0)], 2: [(1, 10.0), (3, 10.0)],
           3: [(1, 25.0), (2, 10.0)]}
    coords = {1: (53.0, 27.0), 2: (53.1, 27.1), 3: (53.2, 27.2)}
    # цель "школа" ровно в узле 3 - snap() должен вернуть узел 3
    dist = compute_target_travel_times(adj, coords, [(53.2, 27.2)])
    assert dist[3] == 0.0
    assert dist[1] == 20.0  # 1->2->3 короче прямого 1->3 (25)
    assert dist[2] == 10.0


def test_compute_target_travel_times_empty_raises():
    import pytest
    with pytest.raises(ValueError):
        compute_target_travel_times({}, {}, [])


def test_belt_report():
    dist = {10: 5.0, 20: 60.0, 30: None}
    raion_nodes = {"r-a": 10, "r-b": 20, "r-c": 30, "r-d": 999}
    rep = belt_report({10: 5.0, 20: 60.0}, raion_nodes)
    assert rep["r-a"]["belt"] == "<45 мин"
    assert rep["r-b"]["belt"] == "45-90 мин"
    assert rep["r-c"]["minutes"] is None and rep["r-c"]["belt"] is None
    assert rep["r-d"]["minutes"] is None  # узла нет в dist
