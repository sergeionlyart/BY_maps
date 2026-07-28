"""INF-15, шаг 3: проекция сетки на 2026-2050, варианты A/Б, сборка grid.json.

Читает откалиброванные наблюдаемые растры (data/raw/grid/rasters_
constrained/, см. etl/grid.py) и прогноз районов (web/public/data/
forecast.json, все 3 сценария). Строит ДВА варианта распределения
прогнозной численности внутри района:

  A - "инерция": показывает, куда шёл бы рисунок расселения, если бы
      внутрирайонный тренд 1975-2020 продолжился без изменений (лог-
      линейная экстраполяция доли каждой клетки в населении района).
  Б - "пригороды/периферия": та же экстраполяция, дополнительно смещённая
      в пользу пригородов крупных городов (см. docs/decisions/INF-15.md
      D-006 за точными параметрами - это ЯВНОЕ модельное допущение,
      не измерение).

Оба варианта НОРМИРУЮТСЯ так, чтобы сумма клеток района ТОЧНО (0.1%)
совпадала с прогнозом района из forecast.json (проверка G-2, тест
обязателен - etl/tests/test_grid_project.py).

Год 2050 - не нативный узел forecast.json (шаг 5 лет от 2026 не попадает в
2050) - линейно интерполируется между узлами 2046 и 2051, dtype "f"
(раздел 6 пререгистрации).

Собирает финальный web/public/data/grid.json (наблюдаемая часть - из
data/raw/grid/metrics_observed.json, модельная - из этого модуля).

Запуск (требует rasterio+numpy+scipy; etl/grid.py должен быть выполнен):
  python -m etl.grid_project
"""
from __future__ import annotations

import json

import numpy as np
import rasterio
from scipy import ndimage

from .common import ROOT, OUT
from .grid import (EPOCHS, RASTERS_CONSTRAINED, RAW, THRESH_PRIMARY,
                    THRESH_SECONDARY, THRESH_AUX, area_share_below, densities,
                    settlement_components, centroid_grid, country_mask,
                    zone_labels, load_raion_series)

# WP-1/B-5 (docs/notes/grid_ux_audit_2026-07-27.md, "два замечания к
# содержанию"): методблок §2 обещает трек центра масс 1897-2050, но
# наблюдаемые данные заканчиваются 2020 годом. Решение - достроить трек
# РЕАЛЬНЫМИ прогнозными точками (не текстовой оговоркой): считаем центр
# масс на растрах прогноза канонической комбинации base:A (тот же дефолт,
# что показан на карте при первом заходе на прогнозные годы) - одна
# согласованная линия, не по одной на каждый сценарий/вариант. dtype "f".
CENTROID_FORECAST_SCENARIO = "base"
CENTROID_FORECAST_VARIANT = "A"

FORECAST_YEARS_NATIVE = [2026, 2031, 2036, 2041, 2046]
FORECAST_YEAR_2050_FROM = (2046, 2051)   # интерполяция
FORECAST_YEARS = FORECAST_YEARS_NATIVE + [2050]
SCENARIOS = ["base", "optimistic", "negative"]
VARIANTS = ["A", "B"]
EPS = 1e-9

# Вариант Б (docs/decisions/INF-15.md D-006) - замороженные параметры
SUBURB_INNER_KM = 8.0     # ближе - это уже само городское ядро, не "пригород"
SUBURB_PEAK_KM = 20.0     # пик "пригородного" буста
SUBURB_OUTER_KM = 45.0    # дальше буста нет
SUBURB_BOOST_MAX = 0.35   # доп. рост доли к 2050 году на пике (относительно варианта A)
PERIPHERY_FAR_KM = 60.0   # дальше этого - "периферия", ускоренное опустение
PERIPHERY_PENALTY_MAX = 0.25
N_ANCHORS = 7             # число "крупных городов"-якорей (авто-обнаружение)
ANCHOR_DENSITY_THRESHOLD = 1500.0   # чел/км² - порог "городское ядро"


def interp_forecast_year(years: list[int], pops: list[float], year: int) -> float:
    if year in years:
        return pops[years.index(year)]
    for i in range(len(years) - 1):
        if years[i] <= year <= years[i + 1]:
            frac = (year - years[i]) / (years[i + 1] - years[i])
            return pops[i] + (pops[i + 1] - pops[i]) * frac
    raise ValueError(f"год {year} вне диапазона прогноза {years}")


def load_forecast() -> dict:
    fc = json.loads((OUT / "forecast.json").read_text())
    out = {}
    for tid, rec in fc["territories"].items():
        out[tid] = {}
        for scn in SCENARIOS:
            years = rec[scn]["years"]
            pops = rec[scn]["pop"]
            out[tid][scn] = {y: interp_forecast_year(years, pops, y)
                              if y not in years else pops[years.index(y)]
                              for y in FORECAST_YEARS}
    return out, fc["version"]


def load_observed_stack():
    stack = []
    for epoch in EPOCHS:
        with rasterio.open(RASTERS_CONSTRAINED / f"pop_{epoch}.tif") as s:
            stack.append(s.read(1).astype("float64"))
            transform, crs, shape = s.transform, s.crs, s.shape
    return np.stack(stack, axis=0), transform, crs, shape


def fit_log_share_trend(stack: np.ndarray, labels: np.ndarray, ids: list[str]):
    """OLS-тренд log(доля клетки в населении района) по годам, векторизовано.

    Возвращает (slope, intercept, ever_populated) - массивы формы (H,W).
    Клетки, никогда не заселённые за 1975-2020, помечаются ever_populated=False
    и не участвуют в проекции (нет роста из ничего - раздел 8 ТЗ п.3).
    """
    n = len(ids)
    t, h, w = stack.shape
    years = np.array(EPOCHS, dtype="float64")
    years_c = years - years.mean()

    raion_totals = np.zeros((t, n + 1))
    for i in range(t):
        raion_totals[i] = np.bincount(labels.ravel(),
                                       weights=stack[i].ravel(), minlength=n + 1)
    # доля клетки = pop_cell / pop_raion(того же года), broadcast по label
    denom = raion_totals[:, labels]              # (t, h, w)
    share = np.where(denom > 0, stack / np.maximum(denom, EPS), 0.0)
    ever_populated = (stack.sum(axis=0) > 0)

    log_share = np.log(share + EPS)
    # векторизованный OLS по оси времени (t) для каждого пикселя
    x_mean = years_c.mean()  # = 0, years_c уже центрирован
    sxx = (years_c ** 2).sum()
    y_mean = log_share.mean(axis=0)
    sxy = (years_c[:, None, None] * (log_share - y_mean)).sum(axis=0)
    slope = sxy / sxx
    intercept = y_mean  # т.к. years_c центрирован, intercept = среднее в точке t=mean(years)

    return slope, intercept, ever_populated, years.mean()


def anchors_from_2020(raster: np.ndarray, transform) -> list[tuple[float, float, float]]:
    """Топ-N городских ядер (плотность >= порога) по 2020: (x_m, y_m, pop)."""
    core = raster >= ANCHOR_DENSITY_THRESHOLD
    labeled, n = ndimage.label(core, structure=np.ones((3, 3)))
    if n == 0:
        return []
    pops = ndimage.sum(raster, labeled, index=range(1, n + 1))
    order = np.argsort(pops)[::-1][:N_ANCHORS]
    anchors = []
    for idx in order:
        comp_id = idx + 1
        ys, xs = np.nonzero(labeled == comp_id)
        w = raster[ys, xs]
        cx = transform.c + transform.a * ((xs + 0.5) * w).sum() / w.sum()
        cy = transform.f + transform.e * ((ys + 0.5) * w).sum() / w.sum()
        anchors.append((cx, cy, float(pops[idx])))
    return anchors


def suburb_periphery_adjustment(shape, transform, anchors) -> tuple[np.ndarray, np.ndarray]:
    """Возвращает (suburb_score, periphery_score) в [0,1] на всю сетку."""
    h, w = shape
    ys, xs = np.mgrid[0:h, 0:w]
    x_m = transform.c + transform.a * (xs + 0.5)
    y_m = transform.f + transform.e * (ys + 0.5)
    if not anchors:
        z = np.zeros(shape)
        return z, z
    min_dist_km = np.full(shape, np.inf)
    for (ax, ay, _) in anchors:
        d = np.sqrt((x_m - ax) ** 2 + (y_m - ay) ** 2) / 1000.0
        min_dist_km = np.minimum(min_dist_km, d)

    # "пригород": треугольная весовая функция между inner и outer, пик на peak
    suburb = np.zeros(shape)
    rising = (min_dist_km > SUBURB_INNER_KM) & (min_dist_km <= SUBURB_PEAK_KM)
    falling = (min_dist_km > SUBURB_PEAK_KM) & (min_dist_km <= SUBURB_OUTER_KM)
    suburb[rising] = (min_dist_km[rising] - SUBURB_INNER_KM) / (SUBURB_PEAK_KM - SUBURB_INNER_KM)
    suburb[falling] = 1.0 - (min_dist_km[falling] - SUBURB_PEAK_KM) / (SUBURB_OUTER_KM - SUBURB_PEAK_KM)

    periphery = np.clip((min_dist_km - PERIPHERY_FAR_KM) / PERIPHERY_FAR_KM, 0.0, 1.0)
    return suburb, periphery


def project_epoch(slope, intercept, t_mean, ever_populated, labels, ids,
                   forecast_by_raion: dict, year: int, scenario: str,
                   variant: str, suburb_score=None, periphery_score=None) -> np.ndarray:
    n = len(ids)
    log_share = intercept + slope * (year - t_mean)
    share_raw = np.where(ever_populated, np.exp(log_share), 0.0)

    if variant == "B":
        years_ahead = max(0, year - 2020) / 24.0   # 2020->2044 но клип на 2050 => 30/24=1.25 ок
        boost = 1.0 + SUBURB_BOOST_MAX * years_ahead * suburb_score
        penalty = 1.0 - PERIPHERY_PENALTY_MAX * years_ahead * periphery_score
        share_raw = share_raw * boost * penalty

    raion_sum = np.bincount(labels.ravel(), weights=share_raw.ravel(), minlength=n + 1)
    scale = np.zeros(n + 1)
    for i, tid in enumerate(ids):
        target = forecast_by_raion.get(tid, {}).get(scenario, {}).get(year)
        if target is not None and raion_sum[i + 1] > 0:
            scale[i + 1] = target / raion_sum[i + 1]
    return share_raw * scale[labels]


TOP_N_CONCENTRATION = 5
G9_RATE_MULTIPLIER = 3.0  # допуск: прогнозный темп не выше Kx худшего наблюдаемого


def top5_share_by_raion(pop: np.ndarray, labels: np.ndarray, ids: list[str]) -> dict:
    """Доля населения района в TOP_N_CONCENTRATION самых плотных его клетках
    (грубая мера внутрирайонной концентрации - см. docs/notes/
    grid_three_scenarios_2026-07-28.md §3.6 и docs/decisions/INF-15.md D-013).
    BY-HM (город, не район) исключён - показатель осмыслен для района."""
    flat_pop = pop.ravel()
    flat_lab = labels.ravel()
    out = {}
    for i, tid in enumerate(ids):
        if tid == "BY-HM":
            continue
        cells = flat_pop[flat_lab == i + 1].astype("float64")
        total = cells.sum()
        if total <= 0:
            continue
        top = np.sort(cells)[-TOP_N_CONCENTRATION:].sum() if cells.size >= TOP_N_CONCENTRATION else total
        out[tid] = top / total
    return out


def compute_g9_concentration_check(stack: np.ndarray, labels: np.ndarray, ids: list[str],
                                     epochs: list[int], forecast_2050_base_a: np.ndarray) -> dict:
    """G-9 (D-013): проверка внутрирайонного распределения, которую G-2 не
    делает - G-2 сверяет только СУММУ клеток района с прогнозом района, а
    не то, как эта сумма разложена между клетками. Находка (docs/notes/
    grid_three_scenarios_2026-07-28.md §3.6, независимо перепроверена
    28.07.2026): национальная средняя доля топ-5 клеток района практически
    не менялась 45 наблюдаемых лет (25.6% в 1975 -> 25.9% в 2020, разброс
    по всем 10 эпохам 25.0-26.5%), а лог-линейная экстраполяция доли клетки
    (project_epoch/fit_log_share_trend) даёт 55.3% уже к 2050 году (тот же
    порядок и у варианта Б - 55.2%, т.к. оба варианта используют одну и ту
    же необязательно ограниченную экспоненциальную базу share_raw до
    вариант-специфичной коррекции). Порог по каждому району: прогнозный
    темп роста доли (2020->2050, канонический base:A) не должен превышать
    G9_RATE_MULTIPLIER раз худший наблюдаемый 5-летний темп 1975-2020."""
    n = len(ids)
    shares_by_epoch = [top5_share_by_raion(stack[i], labels, ids) for i in range(len(epochs))]
    raions = [tid for tid in ids if tid != "BY-HM" and tid in shares_by_epoch[0]]

    hist_max_abs_rate = {}
    for tid in raions:
        series = [shares_by_epoch[i].get(tid) for i in range(len(epochs))]
        rates = [abs(series[i] - series[i - 1]) / (epochs[i] - epochs[i - 1])
                 for i in range(1, len(epochs)) if series[i] is not None and series[i - 1] is not None]
        hist_max_abs_rate[tid] = max(rates) if rates else 0.0

    share_2020 = shares_by_epoch[-1]
    share_2050 = top5_share_by_raion(forecast_2050_base_a, labels, ids)

    per_raion = []
    n_violations = 0
    for tid in raions:
        if tid not in share_2050:
            continue
        rate = float(abs(share_2050[tid] - share_2020[tid]) / 30.0)
        baseline = float(max(hist_max_abs_rate[tid], 1e-6))
        ratio = rate / baseline
        violated = bool(ratio > G9_RATE_MULTIPLIER)
        if violated:
            n_violations += 1
        per_raion.append({"raion": tid, "share_2020": round(float(share_2020[tid]), 4),
                           "share_2050_base_a": round(float(share_2050[tid]), 4),
                           "forecast_rate_per_year": round(rate, 6),
                           "hist_max_rate_per_year": round(baseline, 6),
                           "ratio_to_historical": round(ratio, 2), "violated": violated})

    national_by_epoch = {str(epochs[i]): round(float(np.mean(list(shares_by_epoch[i].values()))), 4)
                          for i in range(len(epochs))}
    national_2050 = round(float(np.mean(list(share_2050.values()))), 4)
    ratios = [r["ratio_to_historical"] for r in per_raion]

    return {
        "description": "Доля населения района в топ-5 самых плотных клетках "
                        "(TOP_N=5) - грубая мера внутрирайонной концентрации. "
                        "G-2 сверяет только сумму клеток района, не форму "
                        "распределения внутри - этот тест проверяет форму.",
        "national_mean_top5_share_by_year": national_by_epoch,
        "national_mean_top5_share_2050_base_a": national_2050,
        "n_raions_checked": len(per_raion),
        "n_raions_violated": n_violations,
        "pct_raions_violated": round(n_violations / len(per_raion) * 100, 1) if per_raion else 0.0,
        "rate_multiplier_threshold": G9_RATE_MULTIPLIER,
        "max_ratio_to_historical": round(max(ratios), 2) if ratios else 0.0,
        "median_ratio_to_historical": round(float(np.median(ratios)), 2) if ratios else 0.0,
        "pass": n_violations == 0,
        "per_raion": per_raion,
    }


def write_grid_json(observed: dict, forecast_out: dict, forecast_version: str,
                     centroid_forecast: list | None = None, g9: dict | None = None) -> None:
    """Собирает финальный web/public/data/grid.json (Приложение А ТЗ, раздел
    «Контракт данных») - объединяет наблюдаемую и модельную часть.

    Поле grid.crs = "ESRI:54009" (НЕ "EPSG:3857" из примера Приложения А) -
    решение D-001 в docs/decisions/INF-15.md: равновеликая Молльвейде
    сохраняет обещанный размер ячейки "1 км"; в Web Mercator на широте
    Беларуси ячейка исказилась бы в 2.5-3.2 раза по площади.
    """
    grid_meta = json.loads((RAW / "grid_meta.json").read_text())
    g3 = json.loads((RAW / "g3_nightlights_crosscheck.json").read_text())
    net_path = RAW / "network_metrics.json"
    net = json.loads(net_path.read_text()) if net_path.exists() else None

    frames_dir = OUT / "grid_frames"
    # WP-1/B-2 (docs/notes/grid_ux_audit_2026-07-27.md): frames теперь
    # разбит по РЕЖИМУ показателя (pop/density) - переключатель "Класс
    # плотности" на странице был декорацией именно потому, что раньше
    # существовал только один плоский словарь frames{key->url} без разбивки
    # по режиму, и metric никуда не передавался. "Метры сети на жителя" -
    # без кадров, живой choropleth из territories[].network_per_capita.
    frames: dict = {"pop": {}, "density": {}}
    for mode in ("pop", "density"):
        for epoch in observed["epochs"]:
            p = frames_dir / f"{mode}_{epoch}.webp"
            if p.exists():
                frames[mode][str(epoch)] = f"/data/grid_frames/{p.name}"
        for year in FORECAST_YEARS:
            for scn in SCENARIOS:
                for variant in VARIANTS:
                    p = frames_dir / f"{mode}_{year}_{scn}_{variant}.webp"
                    if p.exists():
                        frames[mode][f"{year}:{scn}:{variant}"] = f"/data/grid_frames/{p.name}"

    national = dict(observed["national"])
    if centroid_forecast:
        track = list(national.get("centroid_track", [])) + list(centroid_forecast)
        national["centroid_track"] = sorted(track, key=lambda p: p["year"])
    for key in ("area_share_below", "arithmetic_density", "population_weighted_density"):
        merged = {k: dict(v) if isinstance(v, dict) else v
                  for k, v in national.get(key, {}).items()} if key == "area_share_below" else dict(national.get(key, {}))
        if key == "area_share_below":
            for d in ("5", "1", "25"):
                merged.setdefault(d, {})
                merged[d].update(forecast_out["national"]["area_share_below"].get(d, {}))
            national[key] = merged
        else:
            merged.update(forecast_out["national"].get(key, {}))
            national[key] = merged
    national["settlement_components"] = dict(national.get("settlement_components", {}))
    national["settlement_components"].update(forecast_out["national"].get("settlement_components", {}))

    territories = {}
    for tid, rec in observed["territories"].items():
        territories[tid] = {
            "pop_grid_sum": dict(rec["pop_grid_sum"]),
            "area_share_below": {"5": dict(rec.get("area_share_below", {}).get("5", {}))},
        }
        fc = forecast_out["territories"].get(tid, {})
        territories[tid]["pop_grid_sum"].update(fc.get("pop_grid_sum", {}))
        if net and tid in net.get("territories", {}):
            nt = net["territories"][tid]
            territories[tid]["network_per_capita"] = {
                "road_km_per_1000": nt.get("road_km_per_1000"),
                "road_km_per_km2": nt.get("road_km_per_km2"),
                "road_km_total": nt.get("road_km_total"),
            }

    out = {
        "version": "1.2.0",
        "forecast_version": forecast_version,
        "grid": {
            "crs": grid_meta["crs"], "cell_m": grid_meta["cell_m"],
            "width": grid_meta["width"], "height": grid_meta["height"],
            "transform": grid_meta["transform"],
            "note": "единая решётка для всех эпох (1975-2050); проекция "
                    "ESRI:54009 (Молльвейде, равновеликая) - НЕ EPSG:3857, "
                    "см. docs/decisions/INF-15.md D-001",
        },
        "years": {"observed": observed["epochs"], "forecast": FORECAST_YEARS},
        "frames": frames,
        "national": national,
        "territories": territories,
        "validation": {
            "g1_reconciliation_summary": observed["reconciliation_summary"],
            "g2_summary": forecast_out["g2_report_summary"],
            "g3_nightlights_crosscheck": g3,
            "g4_g5": observed["validation"],
            "g6_network": net["g6"] if net else None,
            "c3_correlation": net["correlation_c3"] if net else None,
            "g9_concentration_check": ({k: v for k, v in g9.items() if k != "per_raion"}
                                        if g9 else None),
        },
        "meta": {
            "claims": ["C-001", "C-002", "C-003", "C-004", "C-005"],
            "claims_status": {"C-001": "open_question", "C-002": "open_question",
                              "C-003": "verified", "C-004": "verified",
                              "C-005": "open_question"},
            "artifact": "by-maps-grid-v1.2.0.zip",
            "honesty": "GHS-POP — дазиметрическая производная официальной "
                       "статистики (не независимая перепись); районные/"
                       "национальные суммы клеток откалиброваны под "
                       "официальные ряды (constrained dasymetric "
                       "redistribution, D-005) - GHS-POP определяет только "
                       "внутрирайонное распределение, не итог.",
        },
    }
    (OUT / "grid.json").write_text(json.dumps(out, ensure_ascii=False) + "\n")
    size_kb = (OUT / "grid.json").stat().st_size / 1024
    print(f"\nweb/public/data/grid.json -> {size_kb:.1f} КБ (бюджет 1536 КБ)")


def main() -> None:
    observed = json.loads((RAW / "metrics_observed.json").read_text())
    forecast_by_raion, forecast_version = load_forecast()
    ids, feats, raions, minsk = None, None, None, None
    from .grid import _adm_geoms_moll
    ids, feats, raions, minsk = _adm_geoms_moll()

    ref = RASTERS_CONSTRAINED / "pop_2020.tif"
    labels, ids2, transform, crs = zone_labels(ref)
    assert ids2 == ids
    mask = country_mask(ref)

    stack, transform, crs, shape = load_observed_stack()
    slope, intercept, ever_populated, t_mean = fit_log_share_trend(stack, labels, ids)

    with rasterio.open(RASTERS_CONSTRAINED / "pop_2020.tif") as s:
        raster_2020 = s.read(1)
    anchors = anchors_from_2020(raster_2020, transform)
    suburb_score, periphery_score = suburb_periphery_adjustment(shape, transform, anchors)

    national_forecast = {"area_share_below": {"5": {}, "1": {}, "25": {}},
                          "arithmetic_density": {}, "population_weighted_density": {},
                          "settlement_components": {}}
    territories_forecast = {tid: {"pop_grid_sum": {}} for tid in ids}
    g2_report = []
    centroid_forecast = []
    proj_2050_base_a = None

    for scenario in SCENARIOS:
        for variant in VARIANTS:
            for year in FORECAST_YEARS:
                key = f"{year}:{scenario}:{variant}"
                proj = project_epoch(slope, intercept, t_mean, ever_populated,
                                      labels, ids, forecast_by_raion, year,
                                      scenario, variant, suburb_score, periphery_score)

                if scenario == CENTROID_FORECAST_SCENARIO and variant == CENTROID_FORECAST_VARIANT:
                    c = centroid_grid(proj, transform, crs)
                    c["year"] = year
                    c["dtype"] = "f"
                    c["err_km"] = 10
                    centroid_forecast.append(c)
                if scenario == "base" and variant == "A" and year == 2050:
                    proj_2050_base_a = proj

                for d, dkey in [(THRESH_PRIMARY, "5"), (THRESH_SECONDARY, "1"),
                                 (THRESH_AUX, "25")]:
                    national_forecast["area_share_below"][dkey][key] = round(
                        area_share_below(proj, mask, d), 4)
                dens = densities(proj, mask)
                national_forecast["arithmetic_density"][key] = dens["arithmetic_density"]
                national_forecast["population_weighted_density"][key] = dens["population_weighted_density"]
                national_forecast["settlement_components"][key] = settlement_components(proj, mask)

                n = np.bincount(labels.ravel(), weights=proj.ravel(), minlength=len(ids) + 1)
                for i, tid in enumerate(ids):
                    territories_forecast[tid]["pop_grid_sum"][key] = round(float(n[i + 1]), 1)
                    target = forecast_by_raion.get(tid, {}).get(scenario, {}).get(year)
                    if target and target > 0:
                        pct = (float(n[i + 1]) - target) / target * 100.0
                        g2_report.append({"raion": tid, "year": year, "scenario": scenario,
                                           "variant": variant, "pct_diff": round(pct, 4)})
                print(f"{key}: total={n[1:].sum():,.0f} "
                      f"below5={national_forecast['area_share_below']['5'][key]:.3f}")

    max_g2_dev = max(abs(r["pct_diff"]) for r in g2_report)
    print(f"\nG-2: макс. отклонение сумма-клеток-района vs прогноз района = "
          f"{max_g2_dev:.4f}% (допуск 0.1%)")
    assert max_g2_dev <= 0.1 + 1e-6, "G-2 не выполнен! Нормировка сломана."

    assert proj_2050_base_a is not None
    g9 = compute_g9_concentration_check(stack, labels, ids, EPOCHS, proj_2050_base_a)
    print(f"\nG-9: внутрирайонная концентрация (топ-5 клеток) - "
          f"нац. средняя {g9['national_mean_top5_share_by_year']['1975']*100:.1f}% (1975) -> "
          f"{g9['national_mean_top5_share_by_year']['2020']*100:.1f}% (2020) -> "
          f"{g9['national_mean_top5_share_2050_base_a']*100:.1f}% (2050 base:A); "
          f"{g9['n_raions_violated']}/{g9['n_raions_checked']} районов темпом > "
          f"{G9_RATE_MULTIPLIER}x худшего наблюдаемого - {'ПРОЙДЕНА' if g9['pass'] else 'НЕ ПРОЙДЕНА'} "
          f"(это ожидаемо - см. docs/decisions/INF-15.md D-013)")

    anchors_out = [{"lon": None, "lat": None, "x_m": a[0], "y_m": a[1], "pop": a[2]}
                   for a in anchors]

    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "metrics_forecast.json").write_text(json.dumps({
        "forecast_years": FORECAST_YEARS,
        "scenarios": SCENARIOS, "variants": VARIANTS,
        "forecast_version": forecast_version,
        "national": national_forecast,
        "territories": territories_forecast,
        "g2_report_summary": {"max_pct_diff": max_g2_dev, "n_checks": len(g2_report)},
        "variant_b_anchors": anchors_out,
    }, indent=2, ensure_ascii=False) + "\n")
    with open(RAW / "g2_reconciliation.csv", "w", newline="") as f:
        import csv
        w = csv.DictWriter(f, fieldnames=["raion", "year", "scenario", "variant", "pct_diff"])
        w.writeheader()
        w.writerows(g2_report)

    print(f"\nnational_forecast + territories_forecast -> "
          f"data/raw/grid/metrics_forecast.json ({len(g2_report)} проверок G-2)")

    forecast_out = json.loads((RAW / "metrics_forecast.json").read_text())
    (RAW / "g9_concentration_check.json").write_text(
        json.dumps(g9, indent=2, ensure_ascii=False) + "\n")
    write_grid_json(observed, forecast_out, forecast_version, centroid_forecast, g9)


if __name__ == "__main__":
    main()
