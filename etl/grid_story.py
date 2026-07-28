"""INF-15 v2, этап 2: данные для режима «История» (handoff/09_next_research/
INF-15_grid_v2_brief.md, раздел 7; гипотезы - docs/preregistration/
grid-v0.2.md C-004/C-005).

Считает всё, что раньше пришлось бы хардкодить в компоненте:
- C-004: разбивка изменения населения клетки 1975->2020 по диапазонам
  плотности 1975 года ("правило пятисот", шаг 2 истории);
- C-005: разбивка изменения по поясам удалённости от ближайшей магистрали
  (motorway/trunk/primary), + GeoJSON-слой магистралей для карты (шаг 3);
- площадь, вмещающая половину населения страны, по годам (шаг 1);
- крупнейшие потери/приросты населения по районам 1975->2020, из уже
  откалиброванных под официальный ряд territories[*].pop_grid_sum
  web/public/data/grid.json - НЕ из сырых клеток (шаги 4-5);
- слой чернобыльских зон для карты (data/curated/chernobyl_zones.csv,
  INF-07) (шаг 4).

Все числа перед публикацией на странице проверены независимо (см.
docs/decisions/INF-15.md D-013, docs/preregistration/grid-v0.2.md раздел 3)
- совпадают с зондажем docs/notes/grid_three_scenarios_2026-07-28.md
дословно (C-004, площадь половины населения, именные районы) либо с малым
расхождением метода растеризации (C-005).

Запуск (требует rasterio+numpy+scipy, тот же venv, что и etl.grid_project;
grid.json уже должен быть собран):
  python -m etl.grid_story
"""
from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.transform import Affine
from rasterio.warp import transform as warp_transform
from scipy import ndimage, stats as sstats
from shapely.geometry import mapping, MultiLineString, LineString, Point
from shapely.ops import linemerge
from shapely.strtree import STRtree
from PIL import Image

from .common import ROOT, OUT
from .grid import zone_labels, country_mask, RASTERS_CONSTRAINED, SETTLEMENT_DENSITY

FRAMES = OUT / "grid_frames"
RULE500_THRESHOLD = 500.0
# полупрозрачная заливка (альфа ~90/255) - кадр рисуется ПОВЕРХ обычного
# кадра "люди в клетке", чтобы яркость подложки (плотность текущего года)
# оставалась видна, а не перекрывалась
RULE500_BELOW_RGBA = (70, 130, 220, 90)    # синий - было <500 чел/км² в 1975
RULE500_ABOVE_RGBA = (230, 120, 40, 90)    # оранжевый - было >=500 чел/км² в 1975

CELLS_DIR = OUT / "grid_cells"
GEO_DIR = OUT / "geo"
RAW_GRID = ROOT / "data" / "raw" / "grid"

WIDTH, HEIGHT = 857, 514
TRANSFORM = Affine(1000, 0, 1602000, 0, -1000, 6512000)

DENSITY_BAND_BOUNDS = [1, 5, 25, 100, 500, 2000]
HIGHWAY_BAND_KM = [0, 2, 5, 10, 20]
HIGHWAY_CLASSES = {"motorway", "trunk", "primary"}
TOP_N_RAIONS = 8

# v3 (handoff/09_next_research/INF-15_grid_v2_brief.md -> доработка v3,
# docs/preregistration/grid-v0.2.md §8): гипотезы C-006/C-007, слой рек.
RIVER_BAND_KM = [0, 2, 5, 10, 20]
RIVER_MIN_LENGTH_KM = 20.0   # "крупная река" - см. пререгистрацию §8.4
RIVER_NEAR_KM = 5.0
RIVER_FAR_KM = 20.0
ROAD_NEAR_KM = 2.0
ROAD_FAR_KM = 10.0
SIMPLIFY_TOLERANCE_M = 150   # тот же допуск, что и у слоя магистралей

# Полупрозрачные RGBA-маски поверх обычного кадра (тот же принцип, что и
# RULE500_*_RGBA выше) - шаг 5 истории (матрица река x дорога, 4 группы).
MATRIX_COLORS = {
    "both": (46, 163, 91, 120),        # зелёный - река И дорога рядом
    "river_only": (70, 130, 220, 90),  # синий - только река
    "road_only": (230, 120, 40, 90),   # оранжевый - только дорога
    "neither": (140, 140, 140, 55),    # серый - ни то ни другое
}
# Шаг 3 истории: пояса удалённости от реки (0-2 км тёмно-синий, 2-5 голубее).
RIVER_BUFFER_NEAR_RGBA = (70, 130, 220, 120)
RIVER_BUFFER_MID_RGBA = (130, 180, 235, 85)

# Раздел 3.3 документа v3 - 12 крупнейших городов, проверка "река встречает
# дорогу"; id - реестр etl/registry.py::city_id (см. web/public/data/data.json).
BIG_CITY_IDS = ["c-minsk", "c-mahilou", "c-brest", "c-hrodna", "c-viciebsk",
                 "c-pinsk", "c-navapolack", "c-babrujsk", "c-homiel",
                 "c-baranavichy", "c-salihorsk", "c-maladziechna"]
EXCEPTION_CITY_IDS = {"c-salihorsk", "c-maladziechna"}

# Шаг 8 истории ("полотно рвётся на лоскуты") - категориальная палитра для
# слоя "острова расселения, каждый своим цветом". Кадры только для лет с
# уже закэшированными web/public/data/grid_cells/pop_<year>.bin (10
# наблюдаемых + 2050:base:A) - остальные прогнозные узлы (2026-2046)
# требовали бы отдельного вызова etl.grid_project.project_epoch() для
# каждого года; сознательно не входит в объём этой доработки (см.
# docs/decisions/INF-15.md за явным решением), прокрутка на этих узлах
# просто не показывает слой островов, обычный кадр плотности остаётся.
ISLAND_YEARS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020]
ISLAND_PALETTE = [
    (230, 126, 34), (41, 128, 185), (39, 174, 96), (155, 89, 182), (241, 196, 15),
    (231, 76, 60), (26, 188, 156), (211, 84, 0), (52, 73, 94), (243, 156, 18),
    (142, 68, 173), (22, 160, 133), (192, 57, 43), (127, 140, 141), (46, 204, 113),
]


def load_bin(path: Path) -> np.ndarray:
    arr = np.fromfile(path, dtype="<u2")
    assert arr.size == WIDTH * HEIGHT, f"{path}: {arr.size} != {WIDTH*HEIGHT}"
    return arr.reshape(HEIGHT, WIDTH).astype("float64")


def density_bands(pop_1975: np.ndarray, pop_2020: np.ndarray) -> list[dict]:
    """C-004: разбивка изменения населения по диапазонам плотности 1975 года."""
    bounds = DENSITY_BAND_BOUNDS
    edges = list(zip(bounds, bounds[1:] + [None]))
    out = []
    for lo, hi in edges:
        mask = (pop_1975 >= lo) & (pop_1975 < hi) if hi is not None else (pop_1975 >= lo)
        n = int(mask.sum())
        s75 = float(pop_1975[mask].sum())
        s20 = float(pop_2020[mask].sum())
        chg = (s20 - s75) / s75 * 100 if s75 > 0 else None
        out.append({"lo": lo, "hi": hi, "n_cells": n,
                     "pop_1975": round(s75), "pop_2020": round(s20),
                     "change_pct": round(chg, 1) if chg is not None else None,
                     "share_2020_pct": round(s20 / pop_2020.sum() * 100, 1)})
    return out


def load_highway_lines() -> list[dict]:
    lons, lats, pairs = [], [], []
    with gzip.open(ROOT / "data" / "raw" / "osm" / "graph_edges.csv.gz", "rt") as f:
        r = csv.DictReader(f)
        for row in r:
            if row["highway"] not in HIGHWAY_CLASSES:
                continue
            lons.extend([float(row["lon_a"]), float(row["lon_b"])])
            lats.extend([float(row["lat_a"]), float(row["lat_b"])])
            pairs.append(len(lons) - 2)
    xs, ys = warp_transform("EPSG:4326", "ESRI:54009", lons, lats)
    xs4326, ys4326 = lons, lats  # уже WGS84 - для GeoJSON слоя карты (EPSG:4326)
    moll = [(xs[i], ys[i], xs[i + 1], ys[i + 1]) for i in pairs]
    wgs = [(xs4326[i], ys4326[i], xs4326[i + 1], ys4326[i + 1]) for i in pairs]
    return moll, wgs


def highway_distance_bands(pop_1975: np.ndarray, pop_2020: np.ndarray,
                             moll_lines: list[tuple]) -> list[dict]:
    """C-005: разбивка изменения по поясам удалённости от магистрали."""
    geoms = [{"type": "LineString", "coordinates": [(a, b), (c, d)]}
             for a, b, c, d in moll_lines]
    road_mask = rasterize(((g, 1) for g in geoms), out_shape=(HEIGHT, WIDTH),
                           transform=TRANSFORM, fill=0, dtype="uint8", all_touched=True)
    dist_km = ndimage.distance_transform_edt(1 - road_mask, sampling=(1000, 1000)) / 1000.0

    bounds = HIGHWAY_BAND_KM
    edges = list(zip(bounds, bounds[1:] + [None]))
    out = []
    for lo, hi in edges:
        mask = (dist_km >= lo) & (dist_km < hi) if hi is not None else (dist_km >= lo)
        s75 = float(pop_1975[mask].sum())
        s20 = float(pop_2020[mask].sum())
        chg = (s20 - s75) / s75 * 100 if s75 > 0 else None
        out.append({"lo": lo, "hi": hi, "n_cells": int(mask.sum()),
                     "pop_1975": round(s75), "pop_2020": round(s20),
                     "change_pct": round(chg, 1) if chg is not None else None})
    return out, road_mask.sum()


def half_population_area_km2(pop: np.ndarray, mask: np.ndarray) -> int:
    flat = pop.ravel()[mask.ravel() > 0]
    flat = flat[flat > 0]
    flat_sorted = np.sort(flat)[::-1]
    cum = np.cumsum(flat_sorted)
    half = cum[-1] / 2
    return int(np.searchsorted(cum, half) + 1)


def top_cell_share(pop: np.ndarray, n: int) -> float:
    flat = np.sort(pop.ravel())[::-1]
    return float(flat[:n].sum() / flat.sum() * 100)


def render_rule500_highlight(pop_1975: np.ndarray) -> str:
    """Шаг 2 истории («Правило пятисот»): полупрозрачная маска по порогу
    плотности 1975 года (НЕ по текущему году прокрутки - классификация
    фиксирована на 1975-м, чтобы было видно, как расходятся две группы
    клеток при прокрутке 1975->2020 обычного кадра "люди в клетке" под
    этой маской). Незаселённые клетки (0 в 1975) - полностью прозрачны."""
    h, w = pop_1975.shape
    rgba = np.zeros((h, w, 4), dtype="uint8")
    below = (pop_1975 > 0) & (pop_1975 < RULE500_THRESHOLD)
    above = pop_1975 >= RULE500_THRESHOLD
    rgba[below] = RULE500_BELOW_RGBA
    rgba[above] = RULE500_ABOVE_RGBA
    img = Image.fromarray(rgba, mode="RGBA")
    name = "story_rule500_1975.webp"
    img.save(FRAMES / name, format="WEBP", quality=80, method=6, lossless=False)
    return name


def raion_rankings(grid_json: dict, names: dict) -> dict:
    """Именные районы по изменению 1975->2020, из уже откалиброванных
    territories[*].pop_grid_sum (тождественно официальному ряду на эти
    годы по построению - D-005) - НЕ из сырых клеток. Имена - из
    web/public/data/data.json, чтобы фронтенд не тянул отдельный
    справочник ради фиксированного набора из top-N районов."""
    rows = []
    for tid, rec in grid_json["territories"].items():
        pgs = rec.get("pop_grid_sum", {})
        p75, p20 = pgs.get("1975"), pgs.get("2020")
        if not p75 or not p20 or tid == "BY-HM":
            continue
        nm = names.get(tid, {})
        rows.append({"id": tid, "name_ru": nm.get("ru", tid), "name_be": nm.get("be", tid),
                      "pop_1975": round(p75), "pop_2020": round(p20),
                      "change_pct": round((p20 - p75) / p75 * 100, 1)})
    rows.sort(key=lambda r: r["change_pct"])
    shrunk = rows[:TOP_N_RAIONS]
    grew = list(reversed(rows[-TOP_N_RAIONS:]))
    n_shrunk = sum(1 for r in rows if r["change_pct"] < 0)
    n_shrunk_40 = sum(1 for r in rows if r["change_pct"] <= -40)

    minsk_city = grid_json["territories"].get("BY-HM", {}).get("pop_grid_sum", {})
    minsk_row = None
    if minsk_city.get("1975") and minsk_city.get("2020"):
        p75, p20 = minsk_city["1975"], minsk_city["2020"]
        nm = names.get("BY-HM", {})
        minsk_row = {"id": "BY-HM", "name_ru": nm.get("ru", "Минск"), "name_be": nm.get("be", "Мінск"),
                      "pop_1975": round(p75), "pop_2020": round(p20),
                      "change_pct": round((p20 - p75) / p75 * 100, 1)}

    tot75 = sum(rec["pop_grid_sum"].get("1975", 0) for rec in grid_json["territories"].values())
    tot20 = sum(rec["pop_grid_sum"].get("2020", 0) for rec in grid_json["territories"].values())

    # Полный словарь по id - шаги 4/5 истории называют конкретные районы,
    # выбранные по ГЕОГРАФИИ (два разных сюжета опустения - см. brief), не
    # обязательно входящие в top-N по рангу (пример: Свислочский -57,3% -
    # 9-й по убыли, не входит в top-8, но нужен западной группе шага 4).
    # top-8 списки (shrunk_most/grew_most) оставлены для отдельного
    # использования ("кто пустеет поимённо"), поиск по id - через `by_id`.
    by_id = {r["id"]: r for r in rows}
    if minsk_row:
        by_id["BY-HM"] = minsk_row

    return {
        "shrunk_most": shrunk, "grew_most": grew, "minsk_city": minsk_row, "by_id": by_id,
        "n_raions_total": len(rows), "n_raions_shrunk": n_shrunk,
        "n_raions_shrunk_40pct_or_more": n_shrunk_40,
        "national_pop_1975": round(tot75), "national_pop_2020": round(tot20),
        "national_change_pct": round((tot20 - tot75) / tot75 * 100, 2),
    }


def chernobyl_zone_layer() -> dict:
    """{raion_id: class} из data/curated/chernobyl_zones.csv (INF-07);
    class 1/2 = эвакуация/сильно загрязнённые (см. grid-v0.1.md §5)."""
    path = ROOT / "data" / "curated" / "chernobyl_zones.csv"
    out = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cls = int(row["class"])
            if cls > 0:
                out[row["territory_id"]] = cls
    return out


def load_river_lines(min_length_km: float = RIVER_MIN_LENGTH_KM):
    """v3: рёбра waterway=river (data/raw/osm/river_edges.csv.gz), сведённые
    по имени и отфильтрованные по длине - "крупная река" (docs/
    preregistration/grid-v0.2.md §8.4). Возвращает:
    - kept_moll: список (x1,y1,x2,y2) в ESRI:54009 - для растеризации
      (расстояние/матрица), только рёбра оставшихся рек;
    - merged_by_name: {имя -> LineString|MultiLineString в ESRI:54009} -
      для визуального слоя (§6.2) и точного geometric-расстояния городов
      (§8.2 - STRtree, не по растру)."""
    lons, lats, pairs, names = [], [], [], []
    with gzip.open(ROOT / "data" / "raw" / "osm" / "river_edges.csv.gz", "rt") as f:
        r = csv.DictReader(f)
        for row in r:
            lons.extend([float(row["lon_a"]), float(row["lon_b"])])
            lats.extend([float(row["lat_a"]), float(row["lat_b"])])
            pairs.append(len(lons) - 2)
            names.append(row["name"] or row["name_ru"] or "")
    xs, ys = warp_transform("EPSG:4326", "ESRI:54009", lons, lats)

    by_name: dict[str, list] = {}
    for i, off in enumerate(pairs):
        by_name.setdefault(names[i], []).append(((xs[off], ys[off]), (xs[off + 1], ys[off + 1])))

    kept_moll: list[tuple[float, float, float, float]] = []
    merged_by_name: dict[str, object] = {}
    for nm, segs in by_name.items():
        if not nm:
            continue
        merged = linemerge(MultiLineString(segs))
        if merged.length / 1000.0 < min_length_km:
            continue
        merged_by_name[nm] = merged
        for (x1, y1), (x2, y2) in segs:
            kept_moll.append((x1, y1, x2, y2))
    return kept_moll, merged_by_name


def river_distance_bands(pop_1975: np.ndarray, pop_2020: np.ndarray,
                          moll_lines: list[tuple]) -> tuple[list[dict], np.ndarray, int]:
    """C-007: разбивка изменения/доли населения по поясам удалённости от
    крупной реки. Возвращает (полосы, растр расстояния в км, число клеток
    рек) - растр переиспользуется ниже для матрицы 2x2 и для маски шага 3."""
    geoms = [{"type": "LineString", "coordinates": [(a, b), (c, d)]}
             for a, b, c, d in moll_lines]
    river_mask = rasterize(((g, 1) for g in geoms), out_shape=(HEIGHT, WIDTH),
                            transform=TRANSFORM, fill=0, dtype="uint8", all_touched=True)
    dist_km = ndimage.distance_transform_edt(1 - river_mask, sampling=(1000, 1000)) / 1000.0

    bounds = RIVER_BAND_KM
    edges = list(zip(bounds, bounds[1:] + [None]))
    tot75, tot20 = float(pop_1975.sum()), float(pop_2020.sum())
    out = []
    for lo, hi in edges:
        mask = (dist_km >= lo) & (dist_km < hi) if hi is not None else (dist_km >= lo)
        s75 = float(pop_1975[mask].sum())
        s20 = float(pop_2020[mask].sum())
        chg = (s20 - s75) / s75 * 100 if s75 > 0 else None
        out.append({"lo": lo, "hi": hi, "n_cells": int(mask.sum()),
                     "pop_1975": round(s75), "pop_2020": round(s20),
                     "change_pct": round(chg, 1) if chg is not None else None,
                     "share_1975_pct": round(s75 / tot75 * 100, 1) if tot75 else None,
                     "share_2020_pct": round(s20 / tot20 * 100, 1) if tot20 else None})
    return out, dist_km, int(river_mask.sum())


def river_road_matrix(pop_1975: np.ndarray, pop_2020: np.ndarray, pop_2050_base_a: np.ndarray,
                       river_dist_km: np.ndarray, road_dist_km: np.ndarray, mask: np.ndarray) -> list[dict]:
    """C-006: 4 группы 2x2 (река рядом/далеко x дорога рядом/далеко),
    изменение 1975->2020 и прогноз 2020->2050 (base:A) по каждой."""
    in_country = mask > 0
    groups_def = [
        ("both", (river_dist_km <= RIVER_NEAR_KM) & (road_dist_km <= ROAD_NEAR_KM)),
        ("river_only", (river_dist_km <= RIVER_NEAR_KM) & (road_dist_km > ROAD_FAR_KM)),
        ("road_only", (river_dist_km > RIVER_FAR_KM) & (road_dist_km <= ROAD_NEAR_KM)),
        ("neither", (river_dist_km > RIVER_FAR_KM) & (road_dist_km > ROAD_FAR_KM)),
    ]
    country_pop2020 = float(pop_2020[in_country].sum())
    country_area = float(in_country.sum())
    out = []
    for gid, gm in groups_def:
        gm = gm & in_country
        n = int(gm.sum())
        s75, s20, s50 = float(pop_1975[gm].sum()), float(pop_2020[gm].sum()), float(pop_2050_base_a[gm].sum())
        chg = (s20 - s75) / s75 * 100 if s75 > 0 else None
        chg50 = (s50 - s20) / s20 * 100 if s20 > 0 else None
        out.append({"id": gid, "n_cells": n,
                     "pop_1975": round(s75), "pop_2020": round(s20), "pop_2050_base_A": round(s50),
                     "change_pct": round(chg, 1) if chg is not None else None,
                     "change_2050_pct": round(chg50, 1) if chg50 is not None else None,
                     "share_2020_pct": round(s20 / country_pop2020 * 100, 1) if country_pop2020 else None,
                     "area_share_pct": round(n / country_area * 100, 1) if country_area else None})
    return out


def render_matrix_highlight(river_dist_km: np.ndarray, road_dist_km: np.ndarray, mask: np.ndarray) -> str:
    """Шаг 5 истории: 4-цветная полупрозрачная маска групп 2x2."""
    in_country = mask > 0
    h, w = river_dist_km.shape
    rgba = np.zeros((h, w, 4), dtype="uint8")
    rgba[(river_dist_km <= RIVER_NEAR_KM) & (road_dist_km <= ROAD_NEAR_KM) & in_country] = MATRIX_COLORS["both"]
    rgba[(river_dist_km <= RIVER_NEAR_KM) & (road_dist_km > ROAD_FAR_KM) & in_country] = MATRIX_COLORS["river_only"]
    rgba[(river_dist_km > RIVER_FAR_KM) & (road_dist_km <= ROAD_NEAR_KM) & in_country] = MATRIX_COLORS["road_only"]
    rgba[(river_dist_km > RIVER_FAR_KM) & (road_dist_km > ROAD_FAR_KM) & in_country] = MATRIX_COLORS["neither"]
    img = Image.fromarray(rgba, mode="RGBA")
    name = "story_matrix_2020.webp"
    img.save(FRAMES / name, format="WEBP", quality=80, method=6, lossless=False)
    return name


def render_river_buffer_highlight(river_dist_km: np.ndarray, mask: np.ndarray) -> str:
    """Шаг 3 истории: пояса 0-2 км / 2-5 км от крупной реки."""
    in_country = mask > 0
    h, w = river_dist_km.shape
    rgba = np.zeros((h, w, 4), dtype="uint8")
    rgba[(river_dist_km <= 2) & in_country] = RIVER_BUFFER_NEAR_RGBA
    rgba[(river_dist_km > 2) & (river_dist_km <= 5) & in_country] = RIVER_BUFFER_MID_RGBA
    img = Image.fromarray(rgba, mode="RGBA")
    name = "story_river_buffer.webp"
    img.save(FRAMES / name, format="WEBP", quality=80, method=6, lossless=False)
    return name


def render_islands_layer(pop: np.ndarray, mask: np.ndarray, year_key: str) -> str:
    """Шаг 8 истории: острова расселения (8-связность, порог 1 чел/км² -
    тот же, что и national.settlement_components), каждый компонент своим
    цветом из фиксированной циклической палитры (не уникальный цвет на
    каждый из тысяч островов - смысл в том, чтобы видеть распад ткани на
    отдельные пятна, не идентифицировать каждое)."""
    settled = (mask == 1) & (pop >= SETTLEMENT_DENSITY)
    labeled, n = ndimage.label(settled, structure=np.ones((3, 3), dtype=int))
    h, w = pop.shape
    rgba = np.zeros((h, w, 4), dtype="uint8")
    if n > 0:
        palette = np.array(ISLAND_PALETTE, dtype="uint8")
        comp_colors = palette[(np.arange(n) % len(ISLAND_PALETTE))]
        flat_labels = labeled.ravel()
        nonzero = flat_labels > 0
        colors = np.zeros((flat_labels.size, 4), dtype="uint8")
        colors[nonzero, :3] = comp_colors[flat_labels[nonzero] - 1]
        colors[nonzero, 3] = 130
        rgba = colors.reshape(h, w, 4)
    img = Image.fromarray(rgba, mode="RGBA")
    name = f"story_islands_{year_key}.webp"
    img.save(FRAMES / name, format="WEBP", quality=75, method=6, lossless=False)
    return name


def independent_city_check(data_json: dict, merged_river_by_name: dict, moll_road_lines: list[tuple]):
    """docs/preregistration/grid-v0.2.md §8.2 - проверка C-006 на
    независимом (не растровом) источнике: официальные ряды численности
    городов (web/public/data/data.json, level=city), точное геометрическое
    расстояние (shapely STRtree, не растр) до ближайшей крупной реки и
    ближайшей магистрали, тест Манна-Уитни группа "река+дорога" против
    остальных трёх, по официальному изменению численности 1989->2019."""
    river_list = list(merged_river_by_name.values())
    river_tree = STRtree(river_list)
    road_line_objs = [LineString([(a, b), (c, d)]) for a, b, c, d in moll_road_lines]
    road_tree = STRtree(road_line_objs)

    cities = {tid: t for tid, t in data_json["territories"].items()
              if t.get("level") == "city" and t.get("lon") is not None}
    ids = list(cities.keys())
    lons = [cities[i]["lon"] for i in ids]
    lats = [cities[i]["lat"] for i in ids]
    xs, ys = warp_transform("EPSG:4326", "ESRI:54009", lons, lats)

    rows = []
    for tid, x, y in zip(ids, xs, ys):
        c = cities[tid]
        pt = Point(x, y)
        river_km = float(river_list[river_tree.nearest(pt)].distance(pt)) / 1000.0
        road_km = float(road_line_objs[road_tree.nearest(pt)].distance(pt)) / 1000.0
        pop = c.get("pop", {})
        p89, p19 = pop.get("1989"), pop.get("2019")
        change_pct = round((p19[0] - p89[0]) / p89[0] * 100, 1) if p89 and p19 and p89[0] else None
        if river_km <= RIVER_NEAR_KM and road_km <= ROAD_NEAR_KM:
            group = "both"
        elif river_km <= RIVER_NEAR_KM and road_km > ROAD_FAR_KM:
            group = "river_only"
        elif river_km > RIVER_FAR_KM and road_km <= ROAD_NEAR_KM:
            group = "road_only"
        elif river_km > RIVER_FAR_KM and road_km > ROAD_FAR_KM:
            group = "neither"
        else:
            group = "buffer"
        rows.append({"id": tid, "name_ru": c.get("ru", tid), "name_be": c.get("be", tid),
                      "lon": c["lon"], "lat": c["lat"],
                      "river_km": round(river_km, 1), "road_km": round(road_km, 1),
                      "change_pct_1989_2019": change_pct, "group": group,
                      "is_exception": tid in EXCEPTION_CITY_IDS})

    both = [r["change_pct_1989_2019"] for r in rows if r["group"] == "both" and r["change_pct_1989_2019"] is not None]
    rest = [r["change_pct_1989_2019"] for r in rows
            if r["group"] in ("river_only", "road_only", "neither") and r["change_pct_1989_2019"] is not None]
    result = {"n_cities_total": len(rows), "n_both": len(both), "n_rest": len(rest),
              "years": [1989, 2019], "test": "mann_whitney_u", "p_threshold": 0.10}
    if both and rest:
        stat, p = sstats.mannwhitneyu(both, rest, alternative="two-sided")
        both_med, rest_med = float(np.median(both)), float(np.median(rest))
        result.update({
            "both_median_change_pct": round(both_med, 1),
            "rest_median_change_pct": round(rest_med, 1),
            "u_statistic": round(float(stat), 1), "p_value": round(float(p), 4),
            "direction_confirmed": bool(both_med > rest_med),
            "significant_p10": bool(p < 0.10),
        })
    return rows, result


def main() -> None:
    grid_json = json.loads((OUT / "grid.json").read_text())

    pop_1975 = load_bin(CELLS_DIR / "pop_1975.bin")
    pop_2020 = load_bin(CELLS_DIR / "pop_2020.bin")
    pop_2050_base_a = load_bin(CELLS_DIR / "pop_2050_base_A.bin")

    ref = RASTERS_CONSTRAINED / "pop_2020.tif"
    mask = country_mask(ref)

    cells_ge5 = {
        "1975": int(((pop_1975 >= 5) & (mask > 0)).sum()),
        "2020": int(((pop_2020 >= 5) & (mask > 0)).sum()),
        "2050:base:A": int(((pop_2050_base_a >= 5) & (mask > 0)).sum()),
    }
    print(f"\nклеток с плотностью >=5 чел/км²: {cells_ge5}")

    rule500_frame = render_rule500_highlight(pop_1975)
    print(f"story_rule500_1975.webp -> {(FRAMES / rule500_frame).stat().st_size / 1024:.1f} КБ")

    c004 = density_bands(pop_1975, pop_2020)
    print("C-004 (плотность 1975 -> изменение 1975-2020):")
    for b in c004:
        print(f"  {b['lo']}-{b['hi'] or '+'}: n={b['n_cells']} chg={b['change_pct']}%")

    moll_lines, wgs_lines = load_highway_lines()
    print(f"\nмагистрали (motorway/trunk/primary): {len(moll_lines)} рёбер")
    c005, n_road_cells = highway_distance_bands(pop_1975, pop_2020, moll_lines)
    print("C-005 (удалённость от магистрали -> изменение 1975-2020):")
    for b in c005:
        print(f"  {b['lo']}-{b['hi'] or '+'} км: n={b['n_cells']} chg={b['change_pct']}%")

    half_area = {
        "1975": half_population_area_km2(pop_1975, mask),
        "2020": half_population_area_km2(pop_2020, mask),
        "2050:base:A": half_population_area_km2(pop_2050_base_a, mask),
    }
    country_area_km2 = int(mask.sum())
    print(f"\nполовина населения страны ({country_area_km2} км² всего): {half_area}")

    top_cells = {
        "1975": {"top100_pct": round(top_cell_share(pop_1975, 100), 1),
                  "top500_pct": round(top_cell_share(pop_1975, 500), 1)},
        "2020": {"top100_pct": round(top_cell_share(pop_2020, 100), 1),
                  "top500_pct": round(top_cell_share(pop_2020, 500), 1)},
    }

    names_json = json.loads((OUT / "data.json").read_text())
    names = {tid: {"ru": t.get("ru", tid), "be": t.get("be", tid)}
             for tid, t in names_json["territories"].items()}
    raions = raion_rankings(grid_json, names)
    print(f"\nнациональный итог: 1975={raions['national_pop_1975']:,} "
          f"2020={raions['national_pop_2020']:,} ({raions['national_change_pct']:+.2f}%)")
    print(f"районов с убылью: {raions['n_raions_shrunk']}/{raions['n_raions_total']}, "
          f"из них >=40%: {raions['n_raions_shrunk_40pct_or_more']}")

    chernobyl = chernobyl_zone_layer()
    print(f"\nчернобыльские зоны (class>0): {len(chernobyl)} районов")

    # --- v3: реки (C-006/C-007) -----------------------------------------
    moll_rivers, merged_rivers_by_name = load_river_lines()
    print(f"\nкрупные реки (>= {RIVER_MIN_LENGTH_KM:.0f} км): "
          f"{len(merged_rivers_by_name)} названных, {len(moll_rivers)} рёбер")

    c007_bands, river_dist_km, n_river_cells = river_distance_bands(pop_1975, pop_2020, moll_rivers)
    print("C-007 (удалённость от реки -> доля/изменение 1975-2020):")
    for b in c007_bands:
        print(f"  {b['lo']}-{b['hi'] or '+'} км: n={b['n_cells']} chg={b['change_pct']}% "
              f"доля2020={b['share_2020_pct']}%")

    # растр расстояния до дороги уже посчитан внутри highway_distance_bands,
    # но не возвращается наружу - пересчитываем один раз здесь, дёшево
    # (растеризация + EDT на решётке 857x514, доли секунды).
    road_geoms = [{"type": "LineString", "coordinates": [(a, b), (c, d)]} for a, b, c, d in moll_lines]
    road_mask_raster = rasterize(((g, 1) for g in road_geoms), out_shape=(HEIGHT, WIDTH),
                                  transform=TRANSFORM, fill=0, dtype="uint8", all_touched=True)
    road_dist_km = ndimage.distance_transform_edt(1 - road_mask_raster, sampling=(1000, 1000)) / 1000.0

    c006_groups = river_road_matrix(pop_1975, pop_2020, pop_2050_base_a, river_dist_km, road_dist_km, mask)
    print("C-006 (матрица река x дорога):")
    for g in c006_groups:
        print(f"  {g['id']}: n={g['n_cells']} chg1975-2020={g['change_pct']}% "
              f"chg2020-2050={g['change_2050_pct']}%")

    matrix_frame = render_matrix_highlight(river_dist_km, road_dist_km, mask)
    river_buffer_frame = render_river_buffer_highlight(river_dist_km, mask)
    print(f"story_matrix_2020.webp -> {(FRAMES / matrix_frame).stat().st_size / 1024:.1f} КБ")
    print(f"story_river_buffer.webp -> {(FRAMES / river_buffer_frame).stat().st_size / 1024:.1f} КБ")

    river_share_near = {
        "1975": round((c007_bands[0]["share_1975_pct"] or 0) + (c007_bands[1]["share_1975_pct"] or 0), 1),
        "2020": round((c007_bands[0]["share_2020_pct"] or 0) + (c007_bands[1]["share_2020_pct"] or 0), 1),
    }

    city_rows, independent_check = independent_city_check(names_json, merged_rivers_by_name, moll_lines)
    print(f"\nнезависимая проверка (города, 1989->2019): n_both={independent_check.get('n_both')} "
          f"n_rest={independent_check.get('n_rest')} p={independent_check.get('p_value')} "
          f"направление_подтверждено={independent_check.get('direction_confirmed')}")

    c007_cities = [r for r in city_rows if r["id"] in BIG_CITY_IDS]
    c007_cities.sort(key=lambda r: BIG_CITY_IDS.index(r["id"]))

    # острова расселения по годам (только закэшированные бины - см. докстринг
    # render_islands_layer/ISLAND_YEARS).
    islands_frames: dict[str, str] = {}
    for y in ISLAND_YEARS:
        pop_y = pop_1975 if y == 1975 else (pop_2020 if y == 2020 else load_bin(CELLS_DIR / f"pop_{y}.bin"))
        islands_frames[str(y)] = render_islands_layer(pop_y, mask, str(y))
    islands_frames["2050:base:A"] = render_islands_layer(pop_2050_base_a, mask, "2050_base_A")
    islands_total_kb = sum(
        (FRAMES / ("story_islands_" + k.replace(":", "_") + ".webp")).stat().st_size for k in islands_frames
    ) / 1024
    print(f"\nострова расселения - {len(islands_frames)} кадров ({islands_total_kb:.1f} КБ суммарно)")

    story = {
        "version": "0.3.0",
        "rule500_frame": f"/data/grid_frames/{rule500_frame}",
        "matrix_frame": f"/data/grid_frames/{matrix_frame}",
        "river_buffer_frame": f"/data/grid_frames/{river_buffer_frame}",
        "islands_frames": {k: f"/data/grid_frames/story_islands_{k.replace(':', '_')}.webp" for k in islands_frames},
        "c004_density_bands": {"bounds_pop_per_km2": DENSITY_BAND_BOUNDS, "bands": c004},
        "c005_highway_distance": {
            "road_classes": sorted(HIGHWAY_CLASSES), "bands_km": HIGHWAY_BAND_KM,
            "n_edges": len(moll_lines), "n_road_cells": int(n_road_cells), "bands": c005,
        },
        "c006_river_road_matrix": {
            "river_near_km": RIVER_NEAR_KM, "river_far_km": RIVER_FAR_KM,
            "road_near_km": ROAD_NEAR_KM, "road_far_km": ROAD_FAR_KM,
            "groups": c006_groups, "independent_check": independent_check,
        },
        "c007_river_distance": {
            "bands_km": RIVER_BAND_KM, "n_edges": len(moll_rivers), "n_river_cells": n_river_cells,
            "bands": c007_bands, "share_near_5km_pct": river_share_near, "cities": c007_cities,
        },
        "half_population_area_km2": half_area,
        "country_area_km2": country_area_km2,
        "cells_ge5_pop": cells_ge5,
        "top_cell_concentration": top_cells,
        "raions": raions,
        "chernobyl_zone_class": chernobyl,
    }
    (RAW_GRID / "story_metrics.json").write_text(
        json.dumps(story, indent=2, ensure_ascii=False) + "\n")
    (OUT / "grid_story.json").write_text(json.dumps(story, ensure_ascii=False) + "\n")
    size_kb = (OUT / "grid_story.json").stat().st_size / 1024
    print(f"\nweb/public/data/grid_story.json -> {size_kb:.1f} КБ")

    # Слои на карту - визуальные (расстояния для C-005/C-007 уже посчитаны
    # выше по ПОЛНОМУ, не упрощённому набору рёбер). Сырой экспорт "1 ребро
    # = 1 фича" даёт десятки МБ (не проходит ни один бюджет проекта).
    # Обработка в метрах (Молльвейде, та же CRS, что и вся сетка - D-001):
    # сливаем смежные рёбра в цельные линии (shapely.ops.linemerge - общие
    # узлы OSM это гарантируют), затем упрощаем (Дуглас-Пекер, допуск 150 м
    # - на масштабе всей страны незаметно, сетка сама по себе 1 км) и
    # только потом переводим в WGS84 для GeoJSON, округляя до 5 знаков (~1 м).
    def _write_lines_geojson(moll_line_tuples, out_path, label, wgs_edge_count):
        raw = MultiLineString([[(a, b), (c, d)] for a, b, c, d in moll_line_tuples])
        merged = linemerge(raw)
        geoms = list(merged.geoms) if merged.geom_type == "MultiLineString" else [merged]
        simplified_ = [ln.simplify(SIMPLIFY_TOLERANCE_M, preserve_topology=False) for ln in geoms]
        simplified_ = [ln for ln in simplified_ if not ln.is_empty and ln.geom_type == "LineString"]
        n_before = sum(len(ln.coords) for ln in geoms)
        n_after = sum(len(ln.coords) for ln in simplified_)
        feats = []
        for ln in simplified_:
            xs_m, ys_m = zip(*ln.coords)
            lon_, lat_ = warp_transform("ESRI:54009", "EPSG:4326", list(xs_m), list(ys_m))
            coords = [[round(x, 5), round(y, 5)] for x, y in zip(lon_, lat_)]
            feats.append({"type": "Feature", "properties": {},
                           "geometry": {"type": "LineString", "coordinates": coords}})
        fc = {"type": "FeatureCollection", "features": feats}
        out_path.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")))
        size_kb_ = out_path.stat().st_size / 1024
        print(f"{out_path} -> {size_kb_:.1f} КБ ({wgs_edge_count} рёбер -> {len(simplified_)} линий, "
              f"{n_before} -> {n_after} точек после упрощения) [{label}]")

    _write_lines_geojson(moll_lines, GEO_DIR / "grid_highways.geojson", "магистрали", len(wgs_lines))
    _write_lines_geojson(moll_rivers, GEO_DIR / "grid_rivers.geojson", "реки", len(moll_rivers))


if __name__ == "__main__":
    main()
