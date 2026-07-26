"""INF-15, шаг 2: метрики по наблюдаемым эпохам сетки (1975-2020).

Читает вырезки data/raw/grid/rasters/pop_<epoch>.tif (etl/grid_extract.py),
считает: сверку с официальными рядами районов (G-1.1/G-1.2), долю площади
ниже порогов депопуляции (area_share_below), плотность арифметическую и
взвешенную по населению, число «островов» расселения (settlement_
components), трек центра масс населения (для лет, где есть сетка - 1975+;
более ранние опорные годы 1897-1970 весятся по офиц. численности районов и
их географическим центроидам - см. docs/preregistration/grid-v0.1.md §6).

Пишет промежуточный файл data/raw/grid/metrics_observed.json - его читает
etl/grid_project.py (шаг 3) и собирает финальный web/public/data/grid.json
вместе с прогнозной частью.

Также пишет data/raw/grid/reconciliation.csv (весь ряд эпоха x район,
G-1.1) - обязательная часть архива (raion_reconciliation, "нет" не прячется
в средней цифре - раздел 7 ТЗ, проверка 1).

Запуск (требует rasterio+numpy+scipy; grid_extract.py должен быть выполнен):
  python -m etl.grid
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.warp import transform_geom
from scipy import ndimage

from .common import ROOT, OUT

RAW = ROOT / "data" / "raw" / "grid"
RASTERS = RAW / "rasters"
RASTERS_CONSTRAINED = RAW / "rasters_constrained"
CURATED = ROOT / "data" / "curated"

EPOCHS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020]
PRE_GRID_YEARS = [1897, 1913, 1940, 1959, 1970]  # до GHS-POP, взвешено по data.json

# Замороженные пороги (docs/preregistration/grid-v0.1.md §6)
THRESH_PRIMARY = 5.0
THRESH_SECONDARY = 1.0
THRESH_AUX = 25.0
SETTLEMENT_DENSITY = 1.0
RAION_TOL_PCT = 3.0
NATIONAL_TOL_PCT = 1.0
MAX_FAILED_RAIONS = 15


def _adm_geoms_moll():
    g2 = json.loads((OUT / "geo" / "adm2.geojson").read_text())
    g1 = json.loads((OUT / "geo" / "adm1.geojson").read_text())
    raions = [f for f in g2["features"] if f["properties"]["id"].startswith("r-")]
    ids = [f["properties"]["id"] for f in raions]
    feats = [(transform_geom("EPSG:4326", "ESRI:54009", f["geometry"]), i + 1)
             for i, f in enumerate(raions)]
    minsk = next(f for f in g1["features"] if f["properties"]["id"] == "BY-HM")
    ids.append("BY-HM")
    feats.append((transform_geom("EPSG:4326", "ESRI:54009", minsk["geometry"]),
                  len(ids)))
    return ids, feats, raions, minsk


def zone_labels(ref_tif: Path):
    ids, feats, _, _ = _adm_geoms_moll()
    with rasterio.open(ref_tif) as s:
        labels = rasterize(feats, out_shape=(s.height, s.width),
                            transform=s.transform, fill=0, dtype="int32")
        transform = s.transform
        crs = s.crs
    return labels, ids, transform, crs


def country_mask(ref_tif: Path) -> np.ndarray:
    g1 = json.loads((OUT / "geo" / "adm1.geojson").read_text())
    geoms = [transform_geom("EPSG:4326", "ESRI:54009", f["geometry"])
             for f in g1["features"]]
    with rasterio.open(ref_tif) as s:
        mask = rasterize(((g, 1) for g in geoms), out_shape=s.shape,
                          transform=s.transform, fill=0, dtype="uint8",
                          all_touched=True)
    return mask


def load_raion_series() -> dict:
    """{raion_id: {year:int -> pop:int}} из data.json, только 'r-*' и 'BY-HM'."""
    data = json.loads((OUT / "data.json").read_text())
    out = {}
    for tid, rec in data["territories"].items():
        if tid.startswith("r-") or tid == "BY-HM":
            out[tid] = {int(y): v[0] for y, v in rec.get("pop", {}).items()}
    return out


def interp_official(series: dict[int, int], year: int) -> float | None:
    """Линейная интерполяция офиц. ряда района к произвольному году.

    Экстраполяция за пределы диапазона не производится (возвращает None) -
    все наблюдаемые эпохи (1975-2020) внутри диапазона рядов data.json
    (1970-2026), так что для них экстраполяция не требуется.
    """
    years = sorted(series.keys())
    if year in series:
        return float(series[year])
    if year < years[0] or year > years[-1]:
        return None
    lo = max(y for y in years if y < year)
    hi = min(y for y in years if y > year)
    v_lo, v_hi = series[lo], series[hi]
    frac = (year - lo) / (hi - lo)
    return v_lo + (v_hi - v_lo) * frac


def reconcile(epoch: int, labels: np.ndarray, ids: list[str],
              raster: np.ndarray, official: dict) -> list[dict]:
    n = len(ids)
    sums = np.bincount(labels.ravel(), weights=raster.ravel(), minlength=n + 1)
    rows = []
    for i, tid in enumerate(ids):
        grid_sum = float(sums[i + 1])
        off = interp_official(official.get(tid, {}), epoch)
        if off is None or off <= 0:
            rows.append({"raion": tid, "epoch": epoch, "grid_sum": round(grid_sum, 1),
                         "official": off, "pct_diff": None, "pass": None})
            continue
        pct = (grid_sum - off) / off * 100.0
        rows.append({
            "raion": tid, "epoch": epoch,
            "grid_sum": round(grid_sum, 1), "official": round(off, 1),
            "pct_diff": round(pct, 2),
            "pass": abs(pct) <= RAION_TOL_PCT,
        })
    return rows


def area_share_below(raster: np.ndarray, mask: np.ndarray, d: float) -> float:
    country_cells = mask == 1
    below = country_cells & (raster < d)
    return float(below.sum()) / float(country_cells.sum())


def densities(raster: np.ndarray, mask: np.ndarray) -> dict:
    country_cells = mask == 1
    pop = raster[country_cells]
    total_pop = float(pop.sum())
    total_area = float(country_cells.sum())  # 1 ячейка = 1 км²
    arithmetic = total_pop / total_area if total_area else 0.0
    pw = float((pop.astype("float64") ** 2).sum() / total_pop) if total_pop else 0.0
    return {"arithmetic_density": round(arithmetic, 3),
            "population_weighted_density": round(pw, 3),
            "total_pop": round(total_pop, 1), "total_area_km2": total_area}


def settlement_components(raster: np.ndarray, mask: np.ndarray) -> dict:
    settled = (mask == 1) & (raster >= SETTLEMENT_DENSITY)
    structure = np.ones((3, 3), dtype=int)  # 8-связность (queen's case)
    labeled, n = ndimage.label(settled, structure=structure)
    if n == 0:
        return {"n_components": 0, "largest_share_of_pop": 0.0,
                "largest_share_of_area": 0.0}
    sizes = ndimage.sum(np.ones_like(raster), labeled, index=range(1, n + 1))
    pops = ndimage.sum(raster, labeled, index=range(1, n + 1))
    total_pop = float(raster[mask == 1].sum())
    largest_i = int(np.argmax(pops))
    return {
        "n_components": int(n),
        "largest_area_km2": float(sizes[largest_i]),
        "largest_pop": float(pops[largest_i]),
        "largest_share_of_pop": float(pops[largest_i] / total_pop) if total_pop else 0.0,
        "largest_share_of_area": float(sizes[largest_i] / float((mask == 1).sum())),
    }


def constrain_raster(raster: np.ndarray, labels: np.ndarray, ids: list[str],
                      epoch: int, official: dict) -> np.ndarray:
    """Приводит клетки к официальному ряду района (constrained dasymetric).

    Обоснование - docs/decisions/INF-15.md D-005 и docs/notes/
    grid_validation.md: сырой GHS-POP не проходит G-1 (раион-уровневое
    расхождение до -80%/+200%, системный геогр. паттерн, не шум).
    Домножаем клетки района на official(epoch)/raw_sum(epoch, raion):
    GHS-POP остаётся источником ТОЛЬКО внутрирайонного пространственного
    рисунка, итог по району становится тождественно официальным рядом
    (само по себе НЕ является измерением/проверкой - см. VALIDATION.md).
    Клетки вне зон учёта (~0.94% площади) масштабируются 1.0 (не трогаются).
    """
    n = len(ids)
    raw_sums = np.bincount(labels.ravel(), weights=raster.ravel(), minlength=n + 1)
    scale = np.ones(n + 1, dtype="float64")
    for i, tid in enumerate(ids):
        off = interp_official(official.get(tid, {}), epoch)
        if off is not None and raw_sums[i + 1] > 0:
            scale[i + 1] = off / raw_sums[i + 1]
    return raster * scale[labels]


def centroid_grid(raster: np.ndarray, transform, crs) -> dict:
    """Центр масс населения по сетке (Молльвейде -> lon/lat)."""
    h, w = raster.shape
    rows, cols = np.nonzero(raster > 0)
    weights = raster[rows, cols].astype("float64")
    xs = transform.c + transform.a * (cols + 0.5)
    ys = transform.f + transform.e * (rows + 0.5)
    cx = float((xs * weights).sum() / weights.sum())
    cy = float((ys * weights).sum() / weights.sum())
    lon, lat = _moll_to_lonlat(cx, cy)
    return {"lon": round(lon, 5), "lat": round(lat, 5)}


def _moll_to_lonlat(x: float, y: float) -> tuple[float, float]:
    from rasterio.warp import transform as warp_transform
    lons, lats = warp_transform("ESRI:54009", "EPSG:4326", [x], [y])
    return lons[0], lats[0]


def centroid_pre_grid(year: int, official: dict, raion_centroids_moll: dict) -> dict | None:
    """Центр масс до 1975 - взвешено офиц. численностью района на его геогр. центроиде."""
    num_x = num_y = den = 0.0
    for tid, series in official.items():
        pop = series.get(year)
        if pop is None:
            continue
        cx, cy = raion_centroids_moll.get(tid, (None, None))
        if cx is None:
            continue
        num_x += cx * pop
        num_y += cy * pop
        den += pop
    if den == 0:
        return None
    lon, lat = _moll_to_lonlat(num_x / den, num_y / den)
    return {"lon": round(lon, 5), "lat": round(lat, 5)}


def _raion_centroids_moll(raions: list, minsk: dict) -> dict:
    from shapely.geometry import shape
    out = {}
    for f in raions:
        geom = transform_geom("EPSG:4326", "ESRI:54009", f["geometry"])
        out[f["properties"]["id"]] = shape(geom).centroid.coords[0]
    geom = transform_geom("EPSG:4326", "ESRI:54009", minsk["geometry"])
    out["BY-HM"] = shape(geom).centroid.coords[0]
    return out


POLESYE_RAIONS = [   # docs/decisions/INF-15.md D-004 - операциональный proxy
    "r-baranavicki", "r-brescki", "r-biarozauski", "r-hancavicki",
    "r-drahichynski", "r-zhabinkauski", "r-ivanauski", "r-ivacevicki",
    "r-kamianiecki", "r-kobrynski", "r-luniniecki", "r-lachavicki",
    "r-malarycki", "r-pinski", "r-pruzhanski", "r-stolinski",
    "r-brahinski", "r-jelski", "r-zhytkavicki", "r-kalinkavicki",
    "r-lelchycki", "r-lojeuski", "r-mazyrski", "r-naraulanski",
    "r-pietrykauski", "r-rechycki", "r-chojnicki",
]


def chernobyl_raions() -> list[str]:
    p = CURATED / "chernobyl_zones.csv"
    with p.open() as f:
        rows = list(csv.DictReader(f))
    return [r["territory_id"] for r in rows if r["class"] in ("1", "2")]


def g4_area_share_excluding(labels, ids, mask, exclude_ids: set[str]) -> dict:
    """G-4: area_share_below(5) национально, исключая район(ы) exclude_ids
    из И числителя, И знаменателя (площадь этих районов убирается целиком,
    не просто их вклад в "below")."""
    excl_zone_ids = {i + 1 for i, tid in enumerate(ids) if tid in exclude_ids}
    excl_mask = np.isin(labels, list(excl_zone_ids))
    out = {}
    for epoch in EPOCHS:
        with rasterio.open(RASTERS_CONSTRAINED / f"pop_{epoch}.tif") as s:
            raster = s.read(1)
        keep = (mask == 1) & (~excl_mask)
        below = keep & (raster < THRESH_PRIMARY)
        out[str(epoch)] = round(float(below.sum()) / float(keep.sum()), 4)
    return out


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    from math import radians, sin, cos, sqrt, atan2
    r = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def g5_centroid_sensitivity(official, raion_centroids) -> dict:
    """G-5: пересчёт трека при "других разумных предположениях" (раздел 7
    ТЗ): (а) для дореволюционных/довоенных лет (1897-1959, нет сетки) -
    случайное возмущение веса каждого района ±10% (seed=42, имитация
    неопределённости исторических оценок - равномерное масштабирование
    ВСЕХ весов на одну константу не меняет взвешенное среднее, поэтому
    возмущение обязано быть дифференцированным по районам, не общим
    множителем); (б) для наблюдаемых по сетке лет (1975-2020) - другой
    порог "заселённости" при взвешивании (только клетки с плотностью >=5
    вместо всех клеток >0)."""
    rng = np.random.default_rng(42)
    shifts = {}

    for year in PRE_GRID_YEARS:
        base = centroid_pre_grid(year, official, raion_centroids)
        if base is None:
            continue
        num_x = num_y = den = 0.0
        for tid, series in sorted(official.items()):
            pop = series.get(year)
            if pop is None:
                continue
            cx, cy = raion_centroids.get(tid, (None, None))
            if cx is None:
                continue
            perturb = 1.0 + rng.uniform(-0.10, 0.10)
            w_pop = pop * perturb
            num_x += cx * w_pop
            num_y += cy * w_pop
            den += w_pop
        if den == 0:
            continue
        lon, lat = _moll_to_lonlat(num_x / den, num_y / den)
        shifts[str(year)] = round(_haversine_km(base["lat"], base["lon"], lat, lon), 2)

    for epoch in EPOCHS:
        with rasterio.open(RASTERS_CONSTRAINED / f"pop_{epoch}.tif") as s:
            raster = s.read(1)
            transform = s.transform
        base = centroid_grid(raster, transform, s.crs)
        thresholded = np.where(raster >= THRESH_PRIMARY, raster, 0.0)
        if thresholded.sum() == 0:
            continue
        alt = centroid_grid(thresholded, transform, s.crs)
        shifts[str(epoch)] = round(_haversine_km(base["lat"], base["lon"],
                                                   alt["lat"], alt["lon"]), 2)
    return shifts


def main() -> None:
    ids, feats, raions, minsk = _adm_geoms_moll()
    ref = RASTERS / f"pop_{EPOCHS[-1]}.tif"
    labels, ids2, transform, crs = zone_labels(ref)
    assert ids2 == ids
    mask = country_mask(ref)
    official = load_raion_series()
    raion_centroids = _raion_centroids_moll(raions, minsk)

    recon_rows = []
    national = {
        "area_share_below": {"5": {}, "1": {}, "25": {}},
        "arithmetic_density": {}, "population_weighted_density": {},
        "settlement_components": {}, "centroid_track": [],
        "raion_reconciliation_national": {},
    }
    # Сырые (не откалиброванные) национальные показатели - для сравнения
    # raw vs constrained (условие ревью skeptic+3rd-reviewer, D-005).
    national_raw = {"area_share_below": {"5": {}, "1": {}, "25": {}},
                     "arithmetic_density": {}, "population_weighted_density": {}}
    territories = {tid: {"pop_grid_sum": {}, "area_share_below": {"5": {}, "1": {}}}
                   for tid in ids}

    for epoch in EPOCHS:
        with rasterio.open(RASTERS / f"pop_{epoch}.tif") as s:
            raw_raster = s.read(1)

        rows = reconcile(epoch, labels, ids, raw_raster, official)
        recon_rows.extend(rows)

        raster = constrain_raster(raw_raster, labels, ids, epoch, official)

        RASTERS_CONSTRAINED.mkdir(parents=True, exist_ok=True)
        with rasterio.open(RASTERS / f"pop_{epoch}.tif") as ref_src:
            profile = ref_src.profile
        with rasterio.open(RASTERS_CONSTRAINED / f"pop_{epoch}.tif", "w",
                            **profile) as dst:
            dst.write(raster.astype("float32"), 1)

        n = np.bincount(labels.ravel(), weights=raster.ravel(), minlength=len(ids) + 1)
        below5_mask = (raster < THRESH_PRIMARY).astype("float64")
        zone_area = np.bincount(labels.ravel(), minlength=len(ids) + 1).astype("float64")
        zone_below5 = np.bincount(labels.ravel(), weights=below5_mask.ravel(),
                                   minlength=len(ids) + 1)
        for i, tid in enumerate(ids):
            territories[tid]["pop_grid_sum"][str(epoch)] = round(float(n[i + 1]), 1)
            if zone_area[i + 1] > 0:
                territories[tid]["area_share_below"]["5"][str(epoch)] = round(
                    float(zone_below5[i + 1] / zone_area[i + 1]), 4)

        for d, key in [(THRESH_PRIMARY, "5"), (THRESH_SECONDARY, "1"), (THRESH_AUX, "25")]:
            national["area_share_below"][key][str(epoch)] = round(
                area_share_below(raster, mask, d), 4)
            national_raw["area_share_below"][key][str(epoch)] = round(
                area_share_below(raw_raster, mask, d), 4)

        dens = densities(raster, mask)
        dens_raw = densities(raw_raster, mask)
        national["arithmetic_density"][str(epoch)] = dens["arithmetic_density"]
        national["population_weighted_density"][str(epoch)] = dens["population_weighted_density"]
        national_raw["arithmetic_density"][str(epoch)] = dens_raw["arithmetic_density"]
        national_raw["population_weighted_density"][str(epoch)] = dens_raw["population_weighted_density"]

        national["settlement_components"][str(epoch)] = settlement_components(raster, mask)

        c = centroid_grid(raster, transform, crs)
        c["year"] = epoch
        c["dtype"] = "c" if epoch <= 2020 else "f"
        c["err_km"] = 10
        national["centroid_track"].append(c)

        print(f"epoch {epoch}: pop={dens['total_pop']:,.0f} "
              f"arith_dens={dens['arithmetic_density']:.2f} "
              f"pw_dens={dens['population_weighted_density']:.2f} "
              f"below5={national['area_share_below']['5'][str(epoch)]:.3f} "
              f"(raw below5={national_raw['area_share_below']['5'][str(epoch)]:.3f}, "
              f"raw pw_dens={dens_raw['population_weighted_density']:.2f})")

    # трек центра масс до 1975 (нет сетки - веса по офиц. численности района)
    for year in PRE_GRID_YEARS:
        c = centroid_pre_grid(year, official, raion_centroids)
        if c:
            c["year"] = year
            c["dtype"] = "c" if year in (1959, 1970) else "e"
            c["err_km"] = 25
            national["centroid_track"].append(c)
    national["centroid_track"].sort(key=lambda r: r["year"])

    # ---- G-1.2: национальная сверка (сумма растра vs офиц. страновой ряд) ----
    nat_data = json.loads((OUT / "data.json").read_text())["territories"]["BY"]["pop"]
    nat_series = {int(y): v[0] for y, v in nat_data.items()}
    national_recon = []
    for epoch in EPOCHS:
        grid_total = sum(r["grid_sum"] for r in recon_rows if r["epoch"] == epoch)
        off = interp_official(nat_series, epoch)
        pct = (grid_total - off) / off * 100.0 if off else None
        national_recon.append({
            "epoch": epoch, "grid_sum": round(grid_total, 1),
            "official": round(off, 1) if off else None,
            "pct_diff": round(pct, 2) if pct is not None else None,
            "pass": (abs(pct) <= NATIONAL_TOL_PCT) if pct is not None else None,
        })
    national["raion_reconciliation_national"] = national_recon

    # ---- сводка G-1.1 (СЫРОЙ продукт, до calibration) ----
    # per-epoch счёт - НЕ "118 из 119 в каждой эпохе" (см. ревью D-005):
    # по эпохам проваливается от 40 до 111 из 118-119, unique-объединение
    # по всем 10 эпохам даёт 118-119 (почти каждый раион хоть раз выходит
    # за допуск на каком-то эпохе - это не то же самое, что "всегда").
    per_epoch_fail = {}
    for epoch in EPOCHS:
        pairs = [r for r in recon_rows if r["epoch"] == epoch and r["pass"] is not None]
        per_epoch_fail[str(epoch)] = {
            "failed": len([r for r in pairs if r["pass"] is False]),
            "total": len(pairs),
        }
    failed_raions_ever = sorted({r["raion"] for r in recon_rows if r["pass"] is False})
    summary = {
        "raw_reconciliation_note": (
            "Сырой (неоткалиброванный) GHS-POP не проходит G-1.1 на "
            "большинстве районов в каждой эпохе (см. per_epoch_fail); "
            "далеко за порогом 'более 15 районов' раздела 13 ТЗ. Причина -"
            " не баг конвейера (площадь маски проверена), а системный "
            "геогр. паттерн (города-хозяева переоценены, пригороды Минска "
            "недооценены) + вероятная калибровочная неточность референса "
            "JRC на 2009 год - см. docs/decisions/INF-15.md D-005 и "
            "docs/notes/grid_validation.md."
        ),
        "n_raions_checked": len(ids),
        "per_epoch_fail": per_epoch_fail,
        "failed_raions_ever": failed_raions_ever,
        "n_failed_raions_ever": len(failed_raions_ever),
        "drop_raw_raion_numbers": True,
        "calibration_applied": (
            "constrained dasymetric redistribution - district/national "
            "totals in territories[]/national are forced equal to the "
            "interpolated official series (data.json); GHS-POP supplies "
            "only the within-raion spatial pattern. G-1.1/G-1.2/G-2 pass "
            "by construction after this step, not as an empirical test - "
            "see docs/notes/grid_validation.md."
        ),
    }

    # ---- G-4: устойчивость C-2 к исключению Полесья/Чернобыля ----
    excl = set(POLESYE_RAIONS) | set(chernobyl_raions())
    below5_excl = g4_area_share_excluding(labels, ids, mask, excl)
    below5_full = national["area_share_below"]["5"]
    g4 = {
        "excluded_raions": sorted(excl), "n_excluded": len(excl),
        "area_share_below_5_excluding": below5_excl,
        "area_share_below_5_full": {str(e): below5_full[str(e)] for e in EPOCHS},
        "still_monotonic_nondecreasing": all(
            below5_excl[str(EPOCHS[i])] >= below5_excl[str(EPOCHS[i - 1])] - 0.005
            for i in range(1, len(EPOCHS))
        ),
        "growth_1975_2020": round(below5_excl[str(EPOCHS[-1])] - below5_excl[str(EPOCHS[0])], 4),
    }

    # ---- G-5: устойчивость центра масс к альтернативным весам ----
    g5_shifts = g5_centroid_sensitivity(official, raion_centroids)
    g5 = {"shift_km_by_year": g5_shifts,
          "max_shift_km": max(g5_shifts.values()) if g5_shifts else 0.0,
          "tolerance_km": 15, "pass": (max(g5_shifts.values()) < 15) if g5_shifts else True}

    validation = {"g4_polesye_chernobyl": g4, "g5_centroid_sensitivity": g5}
    print(f"\nG-4: area_share_below(5) искл. Полесье+Чернобыль ({len(excl)} районов): "
          f"1975={below5_excl['1975']:.3f} -> 2020={below5_excl['2020']:.3f} "
          f"(рост {g4['growth_1975_2020']:+.4f}, монотонно={g4['still_monotonic_nondecreasing']})")
    print(f"G-5: макс. сдвиг центра масс при альт. весах = {g5['max_shift_km']:.2f} км "
          f"(допуск 15 км, pass={g5['pass']})")

    RAW.mkdir(parents=True, exist_ok=True)
    with open(RAW / "reconciliation.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["raion", "epoch", "grid_sum", "official",
                                           "pct_diff", "pass"])
        w.writeheader()
        w.writerows(recon_rows)

    out = {
        "epochs": EPOCHS,
        "national": national,
        "national_raw": national_raw,
        "territories": territories,
        "reconciliation_summary": summary,
        "validation": validation,
    }
    (RAW / "metrics_observed.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n")

    print(f"\nG-1.1 (сырой продукт, до калибровки), провал по эпохам:")
    for epoch in EPOCHS:
        pf = per_epoch_fail[str(epoch)]
        print(f"  {epoch}: {pf['failed']}/{pf['total']}")
    print(f"уникальных районов, хоть раз вышедших за допуск: "
          f"{summary['n_failed_raions_ever']} из {summary['n_raions_checked']}")
    print(f"G-1.2 (национально, по эпохам, СЫРОЙ продукт): "
          + ", ".join(f"{r['epoch']}:{r['pct_diff']}%" for r in national_recon))
    print("-> применена constrained-калибровка (D-005); "
          "district/national totals после калибровки равны официальным "
          "по построению.")


if __name__ == "__main__":
    main()
