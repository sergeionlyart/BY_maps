"""Тесты INF-16 `upkeep_network`. Категоризация тегов и дедупликация узел/way
(находка D-009 пилота) - без PBF, синтетические данные."""
from etl.upkeep_network import (ALL_CATEGORIES, categorize, dedup_points)


def test_categorize_school():
    assert categorize({"amenity": "school"}) == ["school"]


def test_categorize_excludes_music_school_by_name():
    assert categorize({"amenity": "school", "name": "Музычная школа"}) == []
    assert categorize({"amenity": "school", "name": "Детская школа искусств"}) == []
    assert categorize({"amenity": "school", "name": "ДЮСШ по лёгкой атлетике"}) == []


def test_categorize_keeps_unnamed_school():
    # отсутствие имени - НЕ основание для исключения (осторожный фильтр)
    assert categorize({"amenity": "school"}) == ["school"]


def test_categorize_keeps_general_school_with_name():
    assert categorize({"amenity": "school", "name": "Ушацкая средняя школа"}) == ["school"]


def test_categorize_multi_tag_no_overlap():
    # магазин с кафе внутри (частый в OSM паттерн amenity=cafe;shop=convenience
    # смоделирован раздельными тегами) даёт обе категории, не теряет ни одну
    cats = categorize({"amenity": "cafe", "shop": "convenience"})
    assert set(cats) == {"cafe", "shop_grocery"}


def test_categorize_healthcare_variants():
    assert categorize({"amenity": "clinic"}) == ["fap"]
    assert categorize({"healthcare": "centre"}) == ["fap"]
    assert categorize({"amenity": "hospital"}) == ["fap"]


def test_categorize_station():
    assert categorize({"railway": "station"}) == ["station"]
    assert categorize({"railway": "halt"}) == ["station"]
    assert categorize({"railway": "rail"}) == []  # просто рельс, не станция


def test_categorize_ladder_leisure():
    assert categorize({"leisure": "swimming_pool"}) == ["pool"]
    assert categorize({"leisure": "water_park"}) == ["water_park"]
    assert categorize({"leisure": "ice_rink"}) == ["ice_rink"]
    assert categorize({"leisure": "sports_centre"}) == ["sports_centre"]


def test_categorize_no_match():
    assert categorize({"amenity": "parking"}) == []


def test_all_categories_count():
    assert len(ALL_CATEGORIES) == 12


def test_dedup_collapses_near_duplicates():
    # узел-точка школы и первый узел контура того же здания школы, ~5 м друг
    # от друга (паттерн узел+way, находка D-009) -> должны схлопнуться
    points = [
        ("school", 53.900000, 27.560000),
        ("school", 53.900030, 27.560020),  # ~3-4 м - тот же физический объект
    ]
    deduped = dedup_points(points)
    assert len(deduped) == 1


def test_dedup_keeps_distant_points():
    # две реально разные школы в одном районе, километры друг от друга
    points = [
        ("school", 53.900000, 27.560000),
        ("school", 53.950000, 27.600000),
    ]
    deduped = dedup_points(points)
    assert len(deduped) == 2


def test_dedup_is_per_category():
    # школа и ФАП в одной точке (соседние здания/один узел с двумя тегами
    # смоделирован раздельно) - разные категории не схлопываются друг с другом
    points = [
        ("school", 53.900000, 27.560000),
        ("fap", 53.900000, 27.560000),
    ]
    deduped = dedup_points(points)
    assert len(deduped) == 2


def test_dedup_empty():
    assert dedup_points([]) == []
