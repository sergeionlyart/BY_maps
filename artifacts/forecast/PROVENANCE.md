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
     docs/notes/backtest_results.json   data/curated/forecast_v2026_1.csv
     docs/notes/sensitivity.json        web/public/data/forecast.json -> лендинг
```

Сценарные параметры: `etl/forecast/scenarios/*.yaml` (base подтягивает
траектории из `data/raw/wpp2024/blr_indicators_medium.csv` напрямую).
Единственные ручные константы — обоснованы в params/assumptions.yaml.
