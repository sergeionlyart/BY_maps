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
from scipy import ndimage
from shapely.geometry import mapping, MultiLineString
from shapely.ops import linemerge
from PIL import Image

from .common import ROOT, OUT
from .grid import zone_labels, country_mask, RASTERS_CONSTRAINED

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

    story = {
        "version": "0.2.0",
        "rule500_frame": f"/data/grid_frames/{rule500_frame}",
        "c004_density_bands": {"bounds_pop_per_km2": DENSITY_BAND_BOUNDS, "bands": c004},
        "c005_highway_distance": {
            "road_classes": sorted(HIGHWAY_CLASSES), "bands_km": HIGHWAY_BAND_KM,
            "n_edges": len(moll_lines), "n_road_cells": int(n_road_cells), "bands": c005,
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

    # Слой на карту - визуальный (расстояния для C-005 уже посчитаны выше
    # по ПОЛНОМУ, не упрощённому набору рёбер). Сырой экспорт "1 ребро = 1
    # фича" даёт ~24 МБ (не проходит ни один бюджет проекта). Обработка в
    # метрах (Молльвейде, та же CRS, что и вся сетка - D-001): сливаем
    # смежные рёбра в цельные линии (shapely.ops.linemerge - общие узлы
    # OSM это гарантируют), затем упрощаем (Дуглас-Пекер, допуск 150 м -
    # на масштабе всей страны незаметно, сетка сама по себе 1 км) и только
    # потом переводим в WGS84 для GeoJSON, округляя до 5 знаков (~1 м).
    SIMPLIFY_TOLERANCE_M = 150
    raw_lines_moll = MultiLineString([[(a, b), (c, d)] for a, b, c, d in moll_lines])
    merged_moll = linemerge(raw_lines_moll)
    merged_geoms = list(merged_moll.geoms) if merged_moll.geom_type == "MultiLineString" else [merged_moll]
    simplified = [ln.simplify(SIMPLIFY_TOLERANCE_M, preserve_topology=False) for ln in merged_geoms]
    simplified = [ln for ln in simplified if not ln.is_empty and ln.geom_type == "LineString"]

    n_pts_before = sum(len(ln.coords) for ln in merged_geoms)
    n_pts_after = sum(len(ln.coords) for ln in simplified)

    features = []
    for ln in simplified:
        xs_m, ys_m = zip(*ln.coords)
        lon, lat = warp_transform("ESRI:54009", "EPSG:4326", list(xs_m), list(ys_m))
        coords = [[round(x, 5), round(y, 5)] for x, y in zip(lon, lat)]
        features.append({"type": "Feature", "properties": {},
                          "geometry": {"type": "LineString", "coordinates": coords}})

    highways_geojson = {"type": "FeatureCollection", "features": features}
    (GEO_DIR / "grid_highways.geojson").write_text(
        json.dumps(highways_geojson, ensure_ascii=False, separators=(",", ":")))
    size_kb = (GEO_DIR / "grid_highways.geojson").stat().st_size / 1024
    print(f"web/public/data/geo/grid_highways.geojson -> {size_kb:.1f} КБ "
          f"({len(wgs_lines)} рёбер -> {len(simplified)} линий, "
          f"{n_pts_before} -> {n_pts_after} точек после упрощения)")


if __name__ == "__main__":
    main()
