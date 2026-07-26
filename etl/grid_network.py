"""INF-15 «Полотно»: метры дорожной сети на жителя (ТЗ §4 «Метры сети на
жителя») + проверка G-6 «Полна ли карта дорог» (ТЗ §7, проверка 6) и тест
утверждения C-3 пререгистрации (`docs/preregistration/grid-v0.1.md` §3):
«дорожной сети на одного жителя больше там, где депопуляция сильнее».

Вход:
  - data/raw/osm/graph_edges.csv.gz — единственный уже готовый снимок
    дорожного графа в проекте (INF-04, 833 438 рёбер; классы
    motorway/trunk/primary/secondary/tertiary + их `_link`-варианты; см.
    data/raw/osm/registry.csv). Длина/время в файле не хранятся — считаем
    длину сами по гаверсинусу (та же логика, что у потребителя INF-04,
    etl/access.py, только тут это делается один раз пакетно, а не по
    запросу).
  - web/public/data/geo/adm2.geojson (118 районов `r-*`) +
    web/public/data/geo/adm1.geojson (`BY-HM`, город Минск как отдельная
    единица, накладывается ПОСЛЕДНИМ поверх Минского района). Тот же
    принцип, что в etl/nightlights_extract.py::_zone_labels, но через
    shapely point-in-polygon по СЕРЕДИНЕ ребра, а не растеризацию — исходные
    данные здесь векторные, не растровые.
  - web/public/data/data.json — численность района на 1989 (базовый год
    депопуляции C-3) и наиболее свежая доступная (обычно 2026) численность
    (раздел 8 ТЗ п.4: по дорогам у нас снимок на 2026 год, не история — год
    для network_per_capita не «прогноз», а последняя фактическая/оценочная
    точка ряда data.json).

Выход:
  - data/raw/grid/network_by_raion.csv (raion,highway_class,length_km)
  - data/raw/grid/network_metrics.json (G-6, корреляция C-3, per-territory
    network_per_capita по всем 119 территориям)
  - data/raw/grid/registry_road_stats.csv (источник официальной статистики
    протяжённости дорог для сверки G-6)

Официальная статистика протяжённости дорог РБ зафиксирована константами
ниже — см. docstring у OFFICIAL_TOTAL_KM и registry_road_stats.csv за
полной атрибуцией (URL, дата обращения, точная цифра, разбивка).

Запуск (shapely+numpy обязательны, scipy опционален — если недоступен,
корреляция считается вручную по рангам): python -m etl.grid_network
"""
from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path

import numpy as np
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from .common import ROOT, OUT

RAW = ROOT / "data" / "raw" / "grid"
OSM_EDGES = ROOT / "data" / "raw" / "osm" / "graph_edges.csv.gz"

NETWORK_CSV = RAW / "network_by_raion.csv"
METRICS_JSON = RAW / "network_metrics.json"
REGISTRY_CSV = RAW / "registry_road_stats.csv"

# --- Официальная статистика протяжённости дорог общего пользования РБ ---
# Основной источник: РУП «Белдорцентр» (подведомственная организация
# Министерства транспорта и коммуникаций РБ, ведёт паспорт сети
# автомобильных дорог) — данные на 01.01.2026:
#   https://beldor.centr.by/en/2026/03/stata2026/ (обращение 2026-07-26)
#   Всего 86 446 км: республиканские 15 934 км + местные 70 512 км.
# Сверочный источник: Минтранс РБ, текущая версия страницы структуры сети
# (без явной даты публикации, но структурно и по порядку величины совпадает):
#   https://mintrans.gov.by/ru/dorozhnoe-khozyajstvo/struktura/set-avtomobilnykh-dorog
#   (обращение 2026-07-26) — Всего 86 538 км: респ. 15 944 + местные 70 594 км.
# Два источника расходятся между собой на 0,1% (86 446 vs 86 538) —
# берём более свежую по явной дате цифру Белдорцентра (01.01.2026) как
# основную для G-6; расхождение источников << допуска G-6 (15%), поэтому
# выбор основного источника не влияет на исход проверки.
OFFICIAL_TOTAL_KM = 86_446.0
OFFICIAL_REPUBLICAN_KM = 15_934.0
OFFICIAL_LOCAL_KM = 70_512.0
OFFICIAL_SOURCE_ID = "beldorcenter_2026"
OFFICIAL_ACCESSED = "2026-07-26"
G6_TOLERANCE_PCT = 15.0

# Классы OSM в снимке INF-04 (data/raw/osm/registry.csv): нет
# residential/unclassified/track — граф извлекался под нужды INF-04
# (межрайонный travel-time), поэтому местные/дворовые дороги в снимке
# отсутствуют по построению. Прямое сопоставление с официальной разбивкой
# «республиканские vs местные» невозможно (motorway/trunk не равны
# «республиканские», а primary/secondary/tertiary не равны «местные» один
# в один — административная и функциональная классификации разные шкалы).
# Поэтому сравниваем ТОЛЬКО общий итог против общего итога (раздел 7 ТЗ,
# проверка 6: «складываем всю дорожную сеть... и сравниваем с официальной
# статистикой протяжённости» — без требования по классам; наиболее
# защитимый вариант, тот же принцип обозначен в задании на этот модуль).

CENSUS_YEARS = [1897, 1923, 1926, 1939, 1959, 1970, 1979, 1989, 1999, 2009, 2019]
BASELINE_YEAR = 1989
CURRENT_YEAR = 2026
EARTH_RADIUS_KM = 6371.0088


def _haversine_km(lat1: np.ndarray, lon1: np.ndarray,
                   lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    lat1r, lat2r = np.radians(lat1), np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (np.sin(dlat / 2) ** 2
         + np.cos(lat1r) * np.cos(lat2r) * np.sin(dlon / 2) ** 2)
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def _zone_polygons():
    """r-* (118, adm2.geojson) + BY-HM (adm1.geojson), BY-HM ПОСЛЕДНИМ —
    перекрывает Минский район там, где город лежит внутри района (тот же
    принцип наложения, что в etl/nightlights_extract.py::_zone_labels,
    там — «покраска» растра в порядке фич, тут — приоритет по индексу при
    наложении полигонов в point-in-polygon)."""
    g2 = json.loads((OUT / "geo" / "adm2.geojson").read_text())
    g1 = json.loads((OUT / "geo" / "adm1.geojson").read_text())
    raions = [f for f in g2["features"] if f["properties"]["id"].startswith("r-")]
    ids = [f["properties"]["id"] for f in raions]
    geoms = [shape(f["geometry"]) for f in raions]
    minsk = next(f for f in g1["features"] if f["properties"]["id"] == "BY-HM")
    ids.append("BY-HM")
    geoms.append(shape(minsk["geometry"]))
    assert len(ids) == 119
    return ids, geoms


def _read_edges():
    lat_a, lon_a, lat_b, lon_b, hw = [], [], [], [], []
    with gzip.open(OSM_EDGES, "rt", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            lat_a.append(float(row["lat_a"]))
            lon_a.append(float(row["lon_a"]))
            lat_b.append(float(row["lat_b"]))
            lon_b.append(float(row["lon_b"]))
            hw.append(row["highway"])
    return (np.array(lat_a), np.array(lon_a), np.array(lat_b), np.array(lon_b),
            hw)


def _assign_raions(mid_lat: np.ndarray, mid_lon: np.ndarray,
                    ids: list[str], geoms: list) -> tuple[list, int, int]:
    """Присваивает каждой середине ребра id территории. covered_by
    (включает границу) векторно через STRtree; при наложении полигонов
    (Минск внутри Минского района, либо ребро лежит точно на общей границе
    двух районов) побеждает больший индекс в списке ids (BY-HM добавлен
    последним и потому побеждает над r-minski — тот же принцип «рисуем
    поверх», что при растеризации в nightlights_extract.py).

    Мелкая доля рёбер (~0.8% на практике) не попадает ни в один полигон
    covered_by — расхождение клип-границы Geofabrik-выгрузки OSM и границы
    adm2-полигонов проекта на уровне пары км. Для них — ближайший полигон
    (tree.nearest), не «потеряно», а «снэпнуто» к ближайшему району;
    учитывается отдельно в metrics как snapped_edges."""
    tree = STRtree(geoms)
    pts = [Point(lo, la) for lo, la in zip(mid_lon, mid_lat)]
    pairs = tree.query(pts, predicate="covered_by")
    best: dict[int, int] = {}
    for in_idx, tree_idx in zip(pairs[0].tolist(), pairs[1].tolist()):
        if in_idx not in best or tree_idx > best[in_idx]:
            best[in_idx] = tree_idx
    n = len(pts)
    unassigned_idx = [i for i in range(n) if i not in best]
    n_snapped = 0
    if unassigned_idx:
        nearest = tree.nearest([pts[i] for i in unassigned_idx])
        nearest = np.atleast_1d(nearest)
        for i, tidx in zip(unassigned_idx, nearest.tolist()):
            best[i] = int(tidx)
            n_snapped += 1
    assigned = [ids[best[i]] for i in range(n)]
    match_counts = np.bincount(pairs[0], minlength=n)
    n_multi_match = int((match_counts > 1).sum())
    return assigned, n_snapped, n_multi_match


def _pop_series(rec: dict) -> dict[int, float]:
    return {int(y): v[0] for y, v in rec.get("pop", {}).items()}


def _resolve_baseline(pop: dict[int, float], base_year: int = BASELINE_YEAR):
    """1989, либо (если недоступен) ближайший ПОСЛЕДУЮЩИЙ год из списка
    официальных переписей (раздел 4 пререгистрации: «если 1989 недоступен —
    ближайший последующий перепис. год»)."""
    if base_year in pop:
        return base_year, pop[base_year], False
    for y in CENSUS_YEARS:
        if y > base_year and y in pop:
            return y, pop[y], True
    later = sorted(y for y in pop if y > base_year)
    if not later:
        raise ValueError("нет ни одного года после базового в pop-ряду")
    y = later[0]
    return y, pop[y], True


def _resolve_current(pop: dict[int, float], target_year: int = CURRENT_YEAR):
    """2026, либо (если недоступен для конкретного района) ближайший
    ПРЕДЫДУЩИЙ доступный год — «снимок» network_per_capita строится на
    последней фактической точке ряда, не на прогнозе (ТЗ §8 п.4)."""
    if target_year in pop:
        return target_year, pop[target_year], False
    earlier = sorted((y for y in pop if y < target_year), reverse=True)
    if not earlier:
        raise ValueError("нет ни одного года до целевого в pop-ряду")
    y = earlier[0]
    return y, pop[y], True


def _spearman(x: list[float], y: list[float]):
    """Ранговая корреляция Спирмена + двусторонний p-value. Используем
    scipy, если доступен в окружении (он есть в .venv этого репозитория,
    установлен как опциональная зависимость для пересборки растров) —
    иначе считаем вручную по формуле Пирсона на рангах со средними рангами
    при связках и t-распределением для p-value (без scipy)."""
    try:
        from scipy.stats import spearmanr
        rho, p = spearmanr(x, y)
        return float(rho), float(p), "scipy.stats.spearmanr"
    except ImportError:
        pass

    import math

    def _ranks(vals):
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        ranks = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg_rank
            i = j + 1
        return ranks

    rx, ry = _ranks(x), _ranks(y)
    n = len(x)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    varx = sum((a - mx) ** 2 for a in rx)
    vary = sum((b - my) ** 2 for b in ry)
    rho = cov / math.sqrt(varx * vary) if varx > 0 and vary > 0 else 0.0
    if abs(rho) >= 1.0:
        p = 0.0
    else:
        t = rho * math.sqrt((n - 2) / (1 - rho ** 2))
        # приближение p-value t-распределения через дополнительную
        # функцию ошибок (нормальное приближение для df=n-2 достаточно
        # большого n; n=118 здесь, приближение обосновано)
        df = n - 2
        x_t = df / (df + t * t)
        p = _betai(df / 2.0, 0.5, x_t)
    return float(rho), float(p), "manual_rank_formula"


def _betai(a: float, b: float, x: float) -> float:
    """Регуляризованная неполная бета-функция (для p-value t-распределения
    без scipy) — реализация continued fraction (Numerical Recipes)."""
    import math
    if x <= 0.0:
        return 1.0
    if x >= 1.0:
        return 0.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                   + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return 1.0 - bt * _betacf(a, b, x) / a
    return bt * _betacf(b, a, 1.0 - x) / b


def _betacf(a: float, b: float, x: float) -> float:
    import math
    MAXIT, EPS, FPMIN = 200, 3e-16, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            break
    return h


def main() -> None:
    ids, geoms = _zone_polygons()

    lat_a, lon_a, lat_b, lon_b, hw = _read_edges()
    lengths_km = _haversine_km(lat_a, lon_a, lat_b, lon_b)
    mid_lat = (lat_a + lat_b) / 2.0
    mid_lon = (lon_a + lon_b) / 2.0

    assigned, n_snapped, n_multi_match = _assign_raions(mid_lat, mid_lon,
                                                          ids, geoms)

    osm_total_km = float(lengths_km.sum())

    # --- Агрегация по (raion, highway_class) ---
    agg: dict[tuple[str, str], float] = {}
    for tid, cls, ln in zip(assigned, hw, lengths_km):
        key = (tid, cls)
        agg[key] = agg.get(key, 0.0) + float(ln)

    RAW.mkdir(parents=True, exist_ok=True)
    with open(NETWORK_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["raion", "highway_class", "length_km"])
        for (tid, cls), ln in sorted(agg.items()):
            w.writerow([tid, cls, round(ln, 3)])

    road_km_total_by_raion: dict[str, float] = {tid: 0.0 for tid in ids}
    road_km_by_class_by_raion: dict[str, dict[str, float]] = {tid: {} for tid in ids}
    for (tid, cls), ln in agg.items():
        road_km_total_by_raion[tid] += ln
        road_km_by_class_by_raion[tid][cls] = round(ln, 3)

    # --- G-6: полнота карты дорог против официальной статистики ---
    delta_pct = (osm_total_km - OFFICIAL_TOTAL_KM) / OFFICIAL_TOTAL_KM * 100.0
    g6_passed = abs(delta_pct) <= G6_TOLERANCE_PCT
    mode = "absolute" if g6_passed else "relative_index"

    g6 = {
        "osm_total_km": round(osm_total_km, 1),
        "osm_total_km_by_class": {
            cls: round(sum(ln for (t, c), ln in agg.items() if c == cls), 1)
            for cls in sorted(set(hw))
        },
        "official_total_km": OFFICIAL_TOTAL_KM,
        "official_republican_km": OFFICIAL_REPUBLICAN_KM,
        "official_local_km": OFFICIAL_LOCAL_KM,
        "official_source": OFFICIAL_SOURCE_ID,
        "official_accessed": OFFICIAL_ACCESSED,
        "delta_pct": round(delta_pct, 2),
        "tolerance_pct": G6_TOLERANCE_PCT,
        "passed": g6_passed,
        "mode": mode,
        "note": ("Снимок INF-04 содержит только классы "
                 "motorway/trunk/primary/secondary/tertiary (+_link) — "
                 "без residential/unclassified/track; официальная "
                 "статистика включает ВСЕ дороги общего пользования "
                 "(включая местные проездные/дворовые). Сравнение — общий "
                 "итог против общего итога (раздел 7 ТЗ, проверка 6), "
                 "классового сопоставления республиканские<->motorway/trunk "
                 "не делаем (не 1:1 совместимые классификации)."),
        "geometry_note": (f"{n_snapped} рёбер ({n_snapped / len(hw) * 100:.2f}%) "
                           "не попали ни в один полигон covered_by "
                           "(расхождение клип-границы Geofabrik-выгрузки и "
                           "adm2-полигонов проекта) — присвоены ближайшему "
                           "району (STRtree.nearest); "
                           f"{n_multi_match} рёбер лежат на общей границе "
                           "двух районов (совпадающая грань полигонов) — "
                           "присвоены по приоритету последнего в списке "
                           "(BY-HM тут не участвует, кроме случаев "
                           "Минск/Минский район)."),
    }

    # --- network_per_capita по территориям ---
    data = json.loads((OUT / "data.json").read_text())["territories"]
    territories_out: dict[str, dict] = {}
    per1000_for_index: dict[str, float] = {}
    for tid in ids:
        rec = data.get(tid)
        area_km2 = rec.get("area") if rec else None
        road_km_total = road_km_total_by_raion.get(tid, 0.0)
        pop_series = _pop_series(rec) if rec else {}
        cur_year, cur_pop, cur_fallback = _resolve_current(pop_series)
        base_year, base_pop, base_fallback = _resolve_baseline(pop_series)
        pop_change_pct = (cur_pop - base_pop) / base_pop * 100.0

        road_km_per_1000 = (road_km_total / cur_pop * 1000.0) if cur_pop else None
        road_km_per_km2 = (road_km_total / area_km2) if area_km2 else None
        per1000_for_index[tid] = road_km_per_1000 or 0.0

        territories_out[tid] = {
            "road_km_total": round(road_km_total, 2),
            "road_km_by_class": road_km_by_class_by_raion.get(tid, {}),
            "area_km2": area_km2,
            "pop_current": {"year": cur_year, "value": cur_pop,
                             "is_fallback": cur_fallback},
            "pop_baseline_1989": {"year": base_year, "value": base_pop,
                                   "is_fallback": base_fallback},
            "pop_change_1989_2026_pct": round(pop_change_pct, 3),
        }
        if mode == "absolute":
            territories_out[tid]["road_km_per_1000"] = (
                round(road_km_per_1000, 3) if road_km_per_1000 is not None else None)
            territories_out[tid]["road_km_per_km2"] = (
                round(road_km_per_km2, 4) if road_km_per_km2 is not None else None)
        else:
            territories_out[tid]["road_km_per_1000"] = None
            territories_out[tid]["road_km_per_km2"] = None

    national_pop_total = sum(t["pop_current"]["value"] for t in territories_out.values())
    national_per_1000 = osm_total_km / national_pop_total * 1000.0
    mean_per1000 = sum(per1000_for_index.values()) / len(per1000_for_index)
    for tid in ids:
        idx = (per1000_for_index[tid] / mean_per1000) if mean_per1000 else None
        territories_out[tid]["relative_index_per_1000_vs_national_mean"] = (
            round(idx, 3) if idx is not None else None)

    national = {
        "road_km_total": round(osm_total_km, 1),
        "pop_current_total": national_pop_total,
        "pop_current_total_note": ("сумма по 119 территориям (118 районов "
            "+ г. Минск, тот же периметр зон, что в "
            "etl/nightlights_extract.py::_zone_labels) - НЕ равна полной "
            "численности страны: население областных/районных городов "
            "(c-baranavichy и т.п.) учтено в data.json отдельными "
            "территориями и в эту сумму не входит, т.к. они не входят в "
            "периметр 119 зон этого модуля."),
        "road_km_per_1000": round(national_per_1000, 4),
        "n_edges": len(hw),
        "n_edges_snapped_to_nearest": n_snapped,
        "n_edges_on_shared_boundary": n_multi_match,
    }

    # --- C-3: корреляция Спирмена, ТОЛЬКО 118 районов (r-*), без BY-HM ---
    # (пререгистрация §3: «по 118 районам»)
    raion_ids = [tid for tid in ids if tid.startswith("r-")]
    x_per1000 = [per1000_for_index[tid] for tid in raion_ids]
    y_change = [territories_out[tid]["pop_change_1989_2026_pct"] for tid in raion_ids]
    rho, p_value, method = _spearman(x_per1000, y_change)
    sign = "negative" if rho < 0 else ("positive" if rho > 0 else "zero")
    significant = p_value < 0.05
    supports_c3 = sign == "negative" and significant

    correlation_c3 = {
        "n_raions": len(raion_ids),
        "variable_x": "network_per_capita_2026 (road_km_per_1000, все классы OSM)",
        "variable_y": "pop_change_1989_2026_pct (официальная численность data.json)",
        "spearman_rho": round(rho, 4),
        "p_value": p_value,  # НЕ округляем - при сильной корреляции p может
                              # быть << 1e-6 (round(1.25e-22, 6) == 0.0),
                              # округление до 6 знаков стёрло бы информацию
        "method": method,
        "sign": sign,
        "significant_at_0.05": significant,
        "supports_c3": supports_c3,
        "hypothesis": ("C-3 (пререгистрация grid-v0.1.md §3): дорожной сети "
                       "на одного жителя больше там, где депопуляция "
                       "сильнее -> ожидаем отрицательную и значимую "
                       "корреляцию Спирмена."),
        "note": ("Проверка на исключение городских районов INF-12 "
                 "(доп. условие контракта опровержения C-3 в §7 "
                 "пререгистрации) в этом модуле не выполнялась — вне "
                 "рамок текущего WP (только базовая корреляция §3); "
                 "если базовая корреляция не подтверждает C-3, доп. "
                 "проверка не требуется по контракту опровержения."),
    }

    out = {
        "generated_by": "etl.grid_network",
        "g6": g6,
        "correlation_c3": correlation_c3,
        "national": national,
        "territories": territories_out,
    }
    METRICS_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")

    # --- Реестр источника официальной статистики ---
    with open(REGISTRY_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["id", "title", "url", "license", "accessed", "value", "notes"])
        w.writerow([
            "beldorcenter_2026",
            "РУП «Белдорцентр»: протяжённость сети автомобильных дорог "
            "общего пользования РБ на 01.01.2026",
            "https://beldor.centr.by/en/2026/03/stata2026/",
            "официальная государственная статистика (открытая публикация, "
            "без указанной отдельной лицензии)",
            OFFICIAL_ACCESSED,
            f"{OFFICIAL_TOTAL_KM:.0f} км всего "
            f"({OFFICIAL_REPUBLICAN_KM:.0f} км республиканские + "
            f"{OFFICIAL_LOCAL_KM:.0f} км местные)",
            "основной источник для G-6 (раздел 7 ТЗ, проверка 6; допуск "
            "|Δ|<=15%, Приложение А); РУП «Белдорцентр» — подведомственная "
            "организация Минтранса РБ, ведёт паспорт сети автодорог",
        ])
        w.writerow([
            "mintrans_gov_by_set_avtomobilnykh_dorog",
            "Минтранс РБ: страница «Сеть автомобильных дорог» (сверочный "
            "источник)",
            "https://mintrans.gov.by/ru/dorozhnoe-khozyajstvo/struktura/"
            "set-avtomobilnykh-dorog",
            "официальная государственная статистика (открытая публикация)",
            OFFICIAL_ACCESSED,
            "86538 км всего (15944 км республиканские + 70594 км местные)",
            "сверочный источник, не основной для G-6; расхождение с "
            "Белдорцентром 0.1% (86538 vs 86446) — в пределах шума "
            "обновления реестра между двумя ведомственными публикациями, "
            "не влияет на исход G-6 при допуске 15%",
        ])
        w.writerow([
            "network_by_raion",
            "Длина дорожной сети INF-04 по (район, класс OSM) — итог "
            "extract этого модуля",
            "data/raw/grid/network_by_raion.csv",
            "ODbL 1.0 (производная OSM, тот же снимок, что "
            "data/raw/osm/graph_edges.csv.gz)",
            OFFICIAL_ACCESSED,
            f"{osm_total_km:.0f} км всего (снимок OSM, только "
            "motorway..tertiary)",
            "гаверсинус по координатам узлов ребра; район — по "
            "point-in-polygon середины ребра (adm2 r-* + adm1 BY-HM "
            "поверх Минского района)",
        ])

    print(f"OK: network_metrics.json — {len(hw):,} рёбер, "
          f"OSM итог {osm_total_km:,.0f} км, официально "
          f"{OFFICIAL_TOTAL_KM:,.0f} км, Δ={delta_pct:+.1f}% "
          f"-> G-6 {'ПРОЙДЕНА' if g6_passed else 'НЕ пройдена'} "
          f"(mode={mode})")
    print(f"C-3: Spearman rho={rho:.4f}, p={p_value:.4g}, sign={sign}, "
          f"поддерживает C-3: {supports_c3} ({method})")


if __name__ == "__main__":
    main()
