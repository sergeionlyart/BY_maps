# Происхождение данных: источник → преобразование → результат

```
Белстат OLAP (F201N)  Белстат дата-портал   Ежегодник-2019   HMD/HFD (OWID)   Перепись OLAP (F602)
  переписи 2009/2019    01.01.2019-2026       табл. 4.10       mx 1x1, ASFR      матрица миграции
        │                     │                   │                │                  │
        ▼                     ▼                   ▼                ▼                  ▼
  age2009.csv           age_current.csv     fertility_oblast   mortality.csv    migration_internal
  age2019.csv           (5-летние группы)   .csv (ASFR+СКР)    (табл. дожития)  .csv (обл. x возраст)
        │                     │                   │                │                  │
        └──────────┬──────────┴───────────┬───────┴────────┬───────┴──────────┬───────┘
                   ▼                      ▼                ▼                  ▼
             бэктест 2009->2019     jump-off 2026    ASFR-профили      таблицы дожития
             (backtest.py)          (data.py)        (run.py)          + Sx (lifetable.py)
                   │                      └───────┬────────┴──────────────────┘
                   │                              ▼
                   │                    CCMPP по областям x 3 сценария (ccmpp.py, run.py)
                   │                    + миграция (migration.py)
                   │                    + квантили из WPP 80% PI (blr_total_all_variants.csv)
                   ▼                              ▼
     docs/notes/backtest_results.json      областные структуры по годам
     docs/notes/sensitivity.json                  │
                                                  ▼
   age2009/age2019 (районы, 12 городов) ──> CCR Гамильтона-Перри + CCMPP
   data.json (ряды районов/городов) ──────> облцентров + стартовая калибровка
   city_raion.csv (привязка город-район)    к оценкам-2026 + IPF к области
   chernobyl_zones.csv (классы 1-2) ──────> (sub.py) + доли городов
                   │                              │
                   ▼                              ▼
     docs/notes/backtest_sub.json       data/curated/forecast_v2026_2.csv
     (районы 2019->2026, города         web/public/data/forecast.json -> лендинг
      <=2009 -> 2019)                   (уровни 0-3, 3 сценария)
```

Сценарные параметры: `etl/forecast/scenarios/*.yaml` (base подтягивает
траектории из `data/raw/wpp2024/blr_indicators_medium.csv` напрямую).
Ручные константы обоснованы в params/assumptions.yaml.

Уровень 2-3 (этап 5): `city_raion.csv` построен генератором
`etl/city_raion.py` репозитория (native: город - центр района в ручном
реестре; pip: point-in-polygon координат Wikidata по полигонам
geoBoundaries ADM2; manual: 4 гп без координат по справочникам);
результат завендорен и детерминирован - пакет shapely не требует.
`chernobyl_zones.csv` - реестр зон исследования INF-07 (официальные
перечни НП, пост. СМ РБ № 75/2021 и № 9/2016; см. пакет
by-maps-chernobyl). `data.json` - база проекта (pop-stat.mashke.org по
официальным переписям и оценкам; гармонизация - ручной реестр проекта).
