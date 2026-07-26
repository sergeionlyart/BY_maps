# Происхождение данных (PROVENANCE)

Каждое итоговое число пакета выводится по цепочке «первичный источник →
зафиксированное преобразование → вендоренный агрегат → итоговая таблица».
Реестр внешних источников — `sources/registry.csv`; точные шаги
преобразования — докстринги пяти модулей `etl/grid_*.py` основного
репозитория (скопированы в `code/extract/` этого пакета). Пути ниже —
относительно корня пакета `artifacts/grid/`, если не указано иное.

## Слой 1. Население по клеткам (GHS-POP)

```text
GHS-POP R2023A, 40 глобальных тайлов (URL+sha256:
sources/raw/registry_ghsl_pop.csv; 4 тайла на эпоху R3_C20/R3_C21/R4_C20/
R4_C21 — та же тайловая сетка JRC, что у GHS-BUILT-S в INF-12)
  → etl/grid_fetch.py     (докачка тайлов в общий кэш data/raw/ghsl/tiles/,
    не вендорится; идемпотентно; пишет sources/raw/registry_ghsl_pop.csv)
  → etl/grid_extract.py   (мозаика 4 тайлов на эпоху → клип по замороженной
    рамке clip_bbox_moll [1602000, 5998000, 2459000, 6512000] → маска по
    union полигонов adm1, репроецированных EPSG:4326 → ESRI:54009,
    all_touched=True → nodata −200 обнуляется → float32, округление до
    3 знаков; единая сетка 857×514 ячеек по 1000 м для ВСЕХ 10 эпох —
    обязательное условие сравнимости кадров и проверки G-2)
  → sources/raw/rasters/pop_<epoch>.tif (10 растров, сырые/неоткалиброванные)
  → etl/grid.py            (G-1: сверка сырых растров с официальным рядом
    района → 119/119 районов вне допуска ±3% хотя бы раз, D-005 →
    constrain_raster(): клетки района домножаются на коэффициент
    official(epoch)/raw_grid_sum(epoch, raion) → CONSTRAINED растры)
  → sources/raw/rasters_constrained/pop_<epoch>.tif (10 откалиброванных
    растров — источник ВСЕХ публикуемых метрик наблюдаемого периода)
  → etl/grid.py            (area_share_below, arithmetic/population-weighted
    density, settlement_components, centroid_grid) → sources/raw/
    metrics_observed.json + sources/raw/reconciliation.csv (G-1, весь ряд)
  → etl/grid_project.py    (fit_log_share_trend по 10 эпохам → проекция
    2026-2050, варианты A/Б → нормировка к прогнозу района, G-2) →
    sources/raw/metrics_forecast.json + sources/raw/g2_reconciliation.csv
  → etl/grid_frames.py     (webp-кадры карты + G-3 перекрёстная проверка)
  → code/build.py          → data/final/computed_results.json (20 метрик)
```

Растровые шаги (grid_fetch/grid_extract/grid.py/grid_project.py/grid_frames.py)
требуют `rasterio`/`numpy`/`scipy`/`Pillow` и выполняются из корня
основного репозитория BY Maps (см. `README.md`); их выходы завендорены в
`sources/raw/*.json`, поэтому `code/run.sh` воспроизводит все контрольные
числа без растров.

## Слой 2. Официальные ряды населения районов

```text
Переписи и оценки Белстата, компиляция pop-stat.mashke.org
(основной датасет проекта web/public/data/data.json)
  → etl/grid.py::load_raion_series()   (только записи 'r-*' и 'BY-HM',
    119 территорий; {tid: {год: население}})
  → etl/grid.py::interp_official()     (линейная интерполяция к узлам эпох
    GHSL, не совпадающим с годом ряда напрямую — только 2005 и 2015
    совпадают; экстраполяция за диапазон ряда НЕ выполняется)
  → используется в двух ролях:
    (а) знаменатель сверки G-1 (reconcile()) — сравнение с сырым grid_sum;
    (б) коэффициент калибровки в constrain_raster() — official(epoch)/
        raw_grid_sum(epoch) домножает клетки района (Слой 1)
```

## Слой 3. Прогноз населения районов до 2050

```text
Прогноз проекта web/public/data/forecast.json (версия v2026.4,
3 сценария base/optimistic/negative, узлы 2026,2031,2036,2041,2046)
  → etl/grid_project.py::load_forecast()      (2050 — линейная
    интерполяция между узлами 2046 и 2051, dtype "f")
  → etl/grid_project.py::fit_log_share_trend() (OLS лог-линейного тренда
    доли КАЖДОЙ клетки в населении её района по 10 наблюдаемым эпохам
    Слоя 1 — векторизованно по всей сетке)
  → etl/grid_project.py::project_epoch()      (вариант A — экстраполяция
    тренда без изменений; вариант Б — домножение на пригородно-
    периферийный фактор от 7 автообнаруженных городских ядер, D-006)
  → нормировка: клетки района масштабируются так, чтобы сумма ТОЧНО (0,1%)
    совпала с прогнозом района на этот год/сценарий/вариант (G-2, 4284
    проверки, максимальное отклонение по факту 0,0%)
  → sources/raw/metrics_forecast.json (national + territories + вариант-Б
    якоря) + sources/raw/g2_reconciliation.csv (построчная сверка)
```

## Слой 4. Ночная светимость (только для перекрёстной проверки G-3)

```text
Вырезки INF-08 v2 (сегмент VIIRS VNL, 2012-2024; пакет
by-maps-nightlights-v2.2.0, web/public/data/nightlights_v2.json)
  → etl/grid_frames.py::g3_nightlights_crosscheck()  (interp_official()
    к 2012/2020 из официального ряда района → знак Δ население 2012→2020
    против знака Δ светимость 2012→2020 → agree = совпадение знаков;
    разбивка отдельно по группе "районы-хозяева городов"
    (etl/registry.py::OBLAST_CITIES_HOST) и остальным)
  → sources/raw/g3_nightlights_crosscheck.json (сводка: 32,8% согласия,
    ПРОВАЛЕНА) + sources/raw/g3_nightlights_rows.csv (район-level)
```

Светимость используется ТОЛЬКО для этой перекрёстной проверки — она не
входит в саму карту клеток населения и не смешивается со слоем 1.

## Слой 5. Дорожная сеть (network_per_capita, G-6, C-3)

```text
Geofabrik belarus-latest.osm.pbf (снимок для INF-04, обращение
2026-07-11) → data/raw/osm/graph_edges.csv.gz (уже готовый, 833 438 рёбер,
классы motorway/trunk/primary/secondary/tertiary + _link — INF-04 не
извлекал residential/unclassified/track)
  → etl/grid_network.py::_read_edges()      (длина ребра — гаверсинус по
    координатам узлов, в снимке не хранится)
  → etl/grid_network.py::_assign_raions()   (середина ребра →
    point-in-polygon (shapely STRtree, covered_by) по 118 полигонам adm2
    r-* + полигону BY-HM adm1, наложенному ПОСЛЕДНИМ поверх Минского
    района; ~0,82% рёбер вне полигонов через covered_by → снэпнуты к
    ближайшему (STRtree.nearest), не потеряны)
  → sources/raw/network_by_raion.csv        (длина по (район, класс OSM))
  → etl/grid_network.py::main()             (G-6: сумма против официальной
    статистики Белдорцентра registry_road_stats.csv, допуск ±15%;
    network_per_capita = road_km_total / население на последней
    фактической точке ряда data.json (обычно 2026, иначе fallback);
    C-3: Spearman network_per_capita_2026 vs Δ% население 1989→2026 по
    118 районам (без BY-HM))
  → sources/raw/network_metrics.json (g6 + correlation_c3 + territories)
    + sources/raw/registry_road_stats.csv (источники офиц. статистики)
```

## Итоговые файлы

| Файл | Производится | Ключевые входы |
|---|---|---|
| data/final/computed_results.json | code/build.py | metrics_observed.json, metrics_forecast.json, g3_nightlights_crosscheck.json, reconciliation.csv, network_metrics.json |
| data/final/grid.json (материализуется сборкой манифеста) | etl/grid_project.py::write_grid_json() | metrics_observed.json, metrics_forecast.json, grid_meta.json, g3_nightlights_crosscheck.json, network_metrics.json, webp-кадры |

## Лицензии по слоям

- GHS-POP R2023A — CC BY 4.0, атрибуция: Schiavina M., Freire S.,
  MacManus K. (2023), European Commission, JRC. Клетки в пакете —
  производная (calibrated), а не сырой продукт.
- Официальные ряды и прогноз населения районов — использование с
  указанием источника (Белстат / pop-stat.mashke.org), прогноз — CC BY 4.0
  (BY Maps).
- Ночная светимость — вырезки INF-08 v2, CC BY 4.0 (Li et al.) / EOG VNL.
- Дорожная сеть — производная OSM, ODbL 1.0, © OpenStreetMap contributors;
  официальная статистика протяжённости — открытая публикация РУП
  «Белдорцентр» без отдельно указанной лицензии.
- Результаты пакета — CC BY 4.0 (BY Maps).
