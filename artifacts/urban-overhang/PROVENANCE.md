# Происхождение данных (PROVENANCE)

Каждое итоговое число пакета выводится по цепочке «первичный источник →
зафиксированное преобразование → вендоренный агрегат → итоговая таблица».
Контрольные суммы всех файлов пакета — в `manifest.json` и
`checks/checksums.sha256`; реестр внешних источников — `sources/registry.csv`.

## Слой 1. Материальный фонд (GHSL)

```text
GHS-BUILT-S R2023A, 40 глобальных тайлов (URL+sha256: sources/raw/registry_ghsl.csv)
  → code/extract/urban_extract.py  (мозаика 4 тайлов/эпоху, клип Беларуси,
    Молльвейде 100 м; эпохи 1975–2020; 2025/2030 продукта НЕ используются)
  → code/extract/urban_morph.py    (порог 10% + чувствительность 5/20%,
    замыкание 0/100/200 м, 8-связность, ≥5 га, seed-компоненты, деление
    слившихся к ближайшему seed, фикс-рамка = объединение эпох + 1 км,
    ядро = контур 1975)
  → sources/raw/morph_city_epoch.csv | morph_fixed.csv | morph_flows.csv | morph_qa.csv
  → code/build.py → data/final/city_metrics.csv | city_interval_metrics.csv
```

Растровые шаги требуют rasterio/numpy/scipy и выполняются из корня
репозитория BY_maps (см. README.md); их выходы завендорены, поэтому
`code/run.sh` воспроизводит все итоговые числа без растров.

## Слой 2. Население

```text
Переписи 1959–2019 и оценки Белстата (компиляция pop-stat.mashke.org,
основной датасет BY Maps data.json)
  → code/extract/urban_registry.py  (реестр 94 городов ≥10 тыс.;
    исключения с преемниками: Восточный→Минск, Костюковка→Гомель)
  → sources/raw/city_registry.csv | exclusions.csv | city_population.csv
  → code/build.py  (линейная интерполяция к годам эпох, статусы
    census/estimate/interpolated; экстраполяции нет)
```

## Слой 3. Интенсивность использования (ночные огни)

```text
Вырезки INF-08 v2 (calDMSP 1992–2013 Li et al.; VIIRS VNL v2.1 2012–2024 EOG;
факелы двух НПЗ обнулены; sha256 растров — в пакете by-maps-nightlights-v2.1.1)
  → code/extract/urban_light.py  (маски городов фикс-рамки → суперсетка 1/10°
    DMSP-пикселя → зональные суммы total/core/edge/buffer; пороги как в INF-08)
  → sources/raw/city_light.csv
  → code/build.py  (окна 2012–14 / 2022–24; SUG, CEUR, IHS)
```

## Слой 4. Современная инфраструктура (OSM)

```text
Geofabrik belarus-latest.osm.pbf, выгрузка 2026-07-15T20:21:10Z
(sha256/md5: sources/raw/registry_osm.csv)
  → code/extract/urban_osm.py  (классы major/local; сегменты по середине;
    POI 8 категорий; здания; админ-границы, содержащие seed города)
  → sources/raw/city_roads.csv | city_poi.csv | city_buildings.csv |
    admin_areas.csv | admin_built.csv
  → code/build.py  (км на 1000 жителей; админ-рамка как контроль MOR)
```

История правок OSM нигде не используется как дата строительства.

## Итоговые файлы

| Файл | Производится | Ключевые входы |
|---|---|---|
| data/final/city_metrics.csv | code/build.py | morph_*, city_population |
| data/final/city_interval_metrics.csv | code/build.py | morph_*, city_population, city_light |
| data/final/city_typology.csv | code/build.py | все слои |
| data/final/computed_results.json | code/build.py | все слои |
| data/final/story.json | code/build.py | все слои (идентичен urban_overhang.json сайта) |

## Лицензии

- GHS-BUILT-S R2023A — CC BY 4.0, атрибуция: Pesaresi M., Politis P. (2023),
  European Commission, Joint Research Centre.
- OSM-производные — ODbL 1.0, © OpenStreetMap contributors.
- calDMSP — CC BY 4.0 (Li et al., Figshare 9828827); VNL — Earth Observation
  Group, Colorado School of Mines.
- Ряды населения — официальная статистика в компиляции pop-stat.mashke.org
  (использование с указанием источника).
- Результаты пакета — CC BY 4.0 (BY Maps).
