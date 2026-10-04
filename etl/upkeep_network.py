"""INF-16 `upkeep`: производственный точечный экстрактор OSM (майлстоун 2).

Вход: `belarus-latest.osm.pbf` (Geofabrik; версия/sha256 - `data/raw/osm/
registry.csv`; сам PBF в репозиторий не вендорится, ~0,33 ГБ - тот же файл,
что уже используют `etl/osm_graph.py`/`etl/urban_osm.py`).

Заменяет пилотный Overpass-снимок майлстоуна 1 (`docs/decisions/INF-16.md`
D-005/D-006/D-007) производственным экстрактором на полном PBF - снимает
и сетевую зависимость от Overpass API, и двойной счёт узел/way (находка
D-009: OSM/официальное медиана 1,27x на пилоте), который здесь устраняется
явной дедупликацией (см. `dedup_points`), а не остаётся диагностическим
ограничением.

12 категорий: 5 базовых целей доступности INF-04 (школа/ФАП/почта/банк/
станция, ТЗ §6 позиция 9) + 7 категорий рыночной оси лестницы благоустройства
(кафе/ресторан/магазин + бассейн/аквапарк/ледовый дворец/спорткомплекс,
ТЗ §0.4/§6 позиции 17-18; спортивные объекты дублируются реестром Минспорта
как основным источником для gid-11 - см. `etl/upkeep_amenities.py`, здесь
OSM - вторичная сверка по этой конкретной подкатегории). Институциональная
сеть (РУВД/МЧС/газ/РЭС, фискальная ось) НЕ извлекается отсюда - это не
точки OSM, а ведомственная структура, собранная веб-разведкой (см.
`data/raw/upkeep_amenities_pilot_2026-08-01/institutional_ruvd_mchs_gas_res.json`).

Запуск (требует pyosmium+shapely, PBF в data/raw/osm/):
    python -m etl.upkeep_network parse   -> data/raw/osm/upkeep_poi.csv (точки, после дедупликации)
    python -m etl.upkeep_network raions  -> data/curated/upkeep_network_by_raion.csv (счётчики по 118 районам)
    python -m etl.upkeep_network all     -> обе фазы
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import osmium

from .common import ROOT
from .geo import build_raion_geoms
from .registry import raion_id

RAW_OSM = ROOT / "data" / "raw" / "osm"
OSM_PBF = RAW_OSM / "belarus-latest.osm.pbf"
CURATED = ROOT / "data" / "curated"
POI_OUT = RAW_OSM / "upkeep_poi.csv"
RAION_OUT = CURATED / "upkeep_network_by_raion.csv"

# --- 12 категорий (фиксированный порядок) -------------------------------
ACCESS_CATEGORIES = ("school", "fap", "post_office", "bank", "station")
LADDER_CATEGORIES = ("cafe", "restaurant", "shop_grocery", "pool",
                     "water_park", "ice_rink", "sports_centre")
ALL_CATEGORIES = ACCESS_CATEGORIES + LADDER_CATEGORIES

_GROCERY_SHOP = {"convenience", "supermarket", "general", "department_store"}
_HEALTH_AMENITY = {"clinic", "hospital"}
_HEALTH_HC = {"centre", "clinic"}

# amenity=school в OSM не различает общее среднее образование от музыкальных/
# художественных/спортивных школ (ДЮСШ) - Белстат считает их отдельно от
# "учреждений общего среднего образования" (см. docs/decisions/INF-16.md,
# уточнение диагноза D-009 -> D-0NN на майлстоуне 2: геометрическая
# дедупликация узел+way объясняла только ~2% превышения OSM над официальным
# счётчиком школ, не медианные ~27-45%; часть объяснения - категориальное
# загрязнение, отфильтровано здесь по названию, где оно есть).
_NON_GENERAL_SCHOOL_NAME_MARKERS = (
    "муз",  # рус. "музыкальная", бел. "музычная" - разные корни, общий префикс
    "мастацтв", "искусств", "харэаграф", "хореограф",
    "спарт", "спортив", "юнацк", "юношеск",  # ДЮСШ/СДЮШОР расшифровка
    "дюсш", "сдюшор",  # те же школы, но аббревиатурой в названии
)


def _is_general_school(tags) -> bool:
    """False только для явно НЕ-общеобразовательных школ по названию (музыка/
    искусство/хореография/спорт) - осторожный фильтр: если названия нет вовсе
    (34% случаев по стране, см. журнал решений), объект НЕ исключается -
    отсутствие имени не считается основанием для исключения."""
    name = (tags.get("name") or tags.get("name:ru") or tags.get("name:be")
            or tags.get("official_name") or "")
    if not name:
        return True
    low = name.lower()
    return not any(marker in low for marker in _NON_GENERAL_SCHOOL_NAME_MARKERS)

# дедупликация узел+way одного физического объекта (D-009): точки одной
# категории ближе этого расстояния схлопываются в одну - см. dedup_points.
# 30 м - меньше типичного расстояния между школами/магазинами (обычно
# сотни метров и больше в пределах одного нас. пункта), но больше типичного
# смещения между узлом-входом и первым узлом контура здания той же школы.
DEDUP_METERS = 30.0
_DEDUP_DEG = DEDUP_METERS / 111_320.0  # приближение: 1 градус широты ~111.32 км


def categorize(tags) -> list[str]:
    """Категории точки по тегам OSM (может быть несколько, фиксированный порядок)."""
    amenity = tags.get("amenity")
    shop = tags.get("shop")
    leisure = tags.get("leisure")
    hc = tags.get("healthcare")
    railway = tags.get("railway")
    cats = []
    if amenity == "school" and _is_general_school(tags):
        cats.append("school")
    if amenity in _HEALTH_AMENITY or hc in _HEALTH_HC:
        cats.append("fap")
    if amenity == "post_office":
        cats.append("post_office")
    if amenity == "bank":
        cats.append("bank")
    if railway in ("station", "halt"):
        cats.append("station")
    if amenity == "cafe":
        cats.append("cafe")
    if amenity == "restaurant":
        cats.append("restaurant")
    if shop in _GROCERY_SHOP:
        cats.append("shop_grocery")
    if leisure == "swimming_pool":
        cats.append("pool")
    if leisure == "water_park":
        cats.append("water_park")
    if leisure == "ice_rink":
        cats.append("ice_rink")
    if leisure == "sports_centre":
        cats.append("sports_centre")
    return cats


class PoiHandler(osmium.SimpleHandler):
    """Один проход по узлам и путям (первый валидный узел - координата way)."""

    def __init__(self):
        super().__init__()
        self.points: list[tuple[str, float, float]] = []
        self.n_nodes_seen = 0
        self.n_ways_seen = 0

    @staticmethod
    def _first_loc(w):
        for nd in w.nodes:
            if nd.location.valid():
                return nd.location.lat, nd.location.lon
        return None

    def node(self, n):
        if not n.tags or not n.location.valid():
            return
        cats = categorize(n.tags)
        if cats:
            self.n_nodes_seen += 1
            for c in cats:
                self.points.append((c, n.location.lat, n.location.lon))

    def way(self, w):
        if not w.tags:
            return
        cats = categorize(w.tags)
        if not cats:
            return
        loc = self._first_loc(w)
        if loc is None:
            return
        self.n_ways_seen += 1
        for c in cats:
            self.points.append((c, loc[0], loc[1]))


def dedup_points(points: list[tuple[str, float, float]]
                 ) -> list[tuple[str, float, float]]:
    """Схлопывает точки одной категории, попавшие в одну ячейку решётки
    ~`DEDUP_METERS`. Устраняет паттерн «узел-точка + way-здание с тем же
    тегом» (находка D-009 пилота: OSM превышал официальный счётчик школ
    медианно в 1,27 раза). Не топологическая проверка членства узла в way
    (не сопоставляет node_id с списком узлов way) - более простой,
    геометрический метод: если это даёт заниженный счёт для двух реально
    разных, но близко расположенных объектов одной категории (редкий
    случай на расстояниях < 30 м для школ/ФАП/банков/etc.), это
    консервативная ошибка в сторону недосчёта, а не иллюзии полноты."""
    seen_cells: dict[tuple[str, int, int], tuple[float, float]] = {}
    out = []
    for cat, lat, lon in points:
        cell = (cat, round(lat / _DEDUP_DEG), round(lon / _DEDUP_DEG))
        if cell in seen_cells:
            continue
        seen_cells[cell] = (lat, lon)
        out.append((cat, lat, lon))
    return out


def cmd_parse() -> None:
    if not OSM_PBF.exists():
        raise SystemExit(
            f"нет {OSM_PBF}; скачайте belarus-latest.osm.pbf с Geofabrik "
            "(см. data/raw/osm/registry.csv) в этот путь")
    print("upkeep_network: разбор PBF (один проход, flex_mem) ...")
    h = PoiHandler()
    h.apply_file(str(OSM_PBF), locations=True, idx="flex_mem")
    print(f"  сырых точек: {len(h.points):,} "
          f"(узлов с тегами {h.n_nodes_seen:,}, way {h.n_ways_seen:,})")

    deduped = dedup_points(h.points)
    n_removed = len(h.points) - len(deduped)
    print(f"  после дедупликации (сетка {DEDUP_METERS:.0f} м): "
          f"{len(deduped):,} (убрано {n_removed:,}, "
          f"{n_removed / max(len(h.points), 1) * 100:.1f}%)")

    RAW_OSM.mkdir(parents=True, exist_ok=True)
    with POI_OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["category", "lat", "lon"])
        for cat, lat, lon in deduped:
            w.writerow([cat, f"{lat:.7f}", f"{lon:.7f}"])
    by_cat = {c: 0 for c in ALL_CATEGORIES}
    for c, _, _ in deduped:
        by_cat[c] = by_cat.get(c, 0) + 1
    print("  по категориям: " + ", ".join(f"{c}={n:,}" for c, n in by_cat.items()))
    print(f"  -> {POI_OUT}")


def cmd_raions() -> None:
    if not POI_OUT.exists():
        raise SystemExit(f"нет {POI_OUT}; сначала `python -m etl.upkeep_network parse`")

    from shapely.geometry import Point

    raion_geoms = build_raion_geoms(ROOT / "data/raw/gb-BLR-ADM2.geojson",
                                    ROOT / "data/raw/drybin_osm.json")
    geoms_by_rid = {raion_id(lat): g["geom"] for lat, g in
                    ((lat, raion_geoms[lat]) for lat in raion_geoms if lat != "MINSK_CITY")}
    assert len(geoms_by_rid) == 118, f"ожидалось 118 районов, нашлось {len(geoms_by_rid)}"

    counts: dict[str, dict[str, int]] = {rid: {c: 0 for c in ALL_CATEGORIES}
                                         for rid in geoms_by_rid}
    unmatched = 0
    with POI_OUT.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pt = Point(float(row["lon"]), float(row["lat"]))
            hit = None
            for rid, geom in geoms_by_rid.items():
                if geom.contains(pt) or geom.intersects(pt):
                    hit = rid
                    break
            if hit:
                counts[hit][row["category"]] += 1
            else:
                unmatched += 1
    print(f"upkeep_network: spatial join завершён, {unmatched} точек вне 118 районов "
          "(за границей страны/Минск-город/приграничная неточность)")

    CURATED.mkdir(parents=True, exist_ok=True)
    with RAION_OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["raion_id", *ALL_CATEGORIES])
        for rid in sorted(counts):
            w.writerow([rid, *(counts[rid][c] for c in ALL_CATEGORIES)])
    print(f"  -> {RAION_OUT}")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("parse", "all"):
        cmd_parse()
    if cmd in ("raions", "all"):
        cmd_raions()
    if cmd not in ("parse", "raions", "all"):
        raise SystemExit(f"неизвестная команда {cmd!r}; ожидалось parse|raions|all")


if __name__ == "__main__":
    main()
