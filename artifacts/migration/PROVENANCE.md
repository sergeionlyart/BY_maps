# Происхождение данных (INF-05, v1.0.0)

```
Дата-портал Белстата                Eurostat API (JSON-stat)
  индикаторы 10101300001/2/3          migr_resvalid / migr_resfirst
  128 территорий; районы с 1994,      citizen=BY, duration=TOTAL,
  области 1990-2019 + 2024-2025       reason=TOTAL, unit=PER,
  (2020-2023 НЕ публиковались);        31 geo, 2015-2025
  9 потоков на уровне областей             │
  уровне областей                          │
        │ (сырые JSON + тела               │   Публикации: BEROC/zerkalo,
        │  запросов завендорены)           │   PAP/ЦНИ, nashaniva, belsat,
        ▼                                  │   DHS, Демоскоп, IOM
  belstat_{net,arrivals,departures}_       │   (снапшоты с sha256)
  {raion,oblast,city}_*.json               │        │
        │                                  ▼        ▼
        │                    eurostat_migr_*_BY.json + снапшоты
        │                                  │
        ▼                                  ▼
  etl/migration.py: словари имён (RAION_RU2ID + «г. X») -> сальдо
  128 территорий, ставки на 1000; ярусы расселения из data.json;
  межобластная матрица из migration_internal.csv (куб F602, WP-F1)
        │
        ├── интервал оттока 2020-2026: etl/mirror.py (WP-F3, импорт;
        │   входы - data/raw/mirror/*.json + константы с источниками)
        ▼
  web/public/data/migration.json
```

Все шаги детерминированы; сетевых вызовов в run.sh нет. Матрица F602
получена в WP-F1 из OLAP переписи (census.belstat.gov.by, куб F602) и
включена как curated CSV; её первичное происхождение задокументировано
в пакете forecast.
