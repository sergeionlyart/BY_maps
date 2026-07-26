# Происхождение данных (PROVENANCE)

Каждое итоговое число пакета выводится по цепочке «первичный источник →
зафиксированное преобразование → входной файл → расчёт → итоговая
таблица». Контрольные суммы всех файлов пакета — в `manifest.json` и
`checks/checksums.sha256`; реестр источников — `sources/registry.csv`.

## Слой 1. Собственные источники INF-13 (собраны на этапе 1)

```text
Белстат, dataportal, индикатор 10106000001 «Численность пенсионеров»,
область, 2000-2020 (sha256 в реестре)
  → data/raw/pension/recipients_10106000001_2000-2020.json
  → etl/pension.py:load_pension_oblast()

Белстат, dataportal, индикатор 10106000002 «Средняя пенсия», область,
2000-2025 (ЛОВУШКА: запрос >~15 лет x 8 территорий разом иногда рвёт
HTTP/2-соединение - фетчено по одному году)
  → data/raw/pension/avg_pension_10106000002_2000-2025.json
  → etl/pension.py:load_pension_oblast()

Указ Президента №137 от 11.04.2016 «О совершенствовании пенсионного
обеспечения», п.1.1 (график +6 мес/год повышения пенсионного возраста,
2017-2022, официальный портал Президента)
  → data/curated/retirement_age.csv (ручная транскрипция графика указа,
     сверена вторичным источником myfin.by только для календарной привязки
     этапов - НЕ как замена первичного акта)
  → etl/pension.py:load_retirement_schedule() → age_boundary()

Белстат, инфографика «Население Республики Беларусь. На 1 января 2025 г.»
(PDF, прочитан программно pdftotext, НЕ вручную)
  → data/raw/pension/belstat_naselenie_2025-01-01.pdf
  → зашито константами в etl/pension.py:gate_g1()
    (below=1553708, above=2238235, total=9109280)

Закон РБ №118-З от 15.07.2021, ст.5 (ставка пенсионного страхования:
28% работодатель + 1% работник; подтверждено независимо двумя вторичными
источниками - kadroved.by, benefit.by, с идентичными цифрами 28/6/1)
  → data/raw/pension/fszn_rate_law118z_art5.html
  → зашито константой CONTRIB_RATE=0.29 в etl/pension.py

Our World in Data, зеркало UN WPP 2024 medium (первичные численности по
возрастным группам Беларуси; population.un.org/dataportalapi отдаёт 401
без токена - анонимного доступа к готовым индикаторам «support ratio» нет,
поэтому потенциальный коэффициент поддержки UN 2050 ВЫВЕДЕН из сырых
численностей, а не скопирован готовым значением)
  → data/raw/pension/owid_pop_age_groups_blr.csv
  → зашито константой un_psr=2.18 в etl/pension.py:gate_g4()
    ( = (3876755+1528760-948561)/2046308 )
```

## Слой 2. Переиспользованные без повторного скачивания источники других этапов

```text
OLAP-куб F201N Белстата (переписи 2009/2019, WP-F1)
  → data/curated/age2009.csv, age2019.csv
  → etl/pension.py:load_raion_census_struct(), load_national_census_struct()

Белстат, dataportal, индикатор 10218000003 (зарплата) и 10102000017
(занятые) по районам, УЖЕ завендорены этапами INF-03/INF-08
  → data/raw/wages/wage_10218000003_*.json (через etl/wages.py:load_wages)
  → data/raw/wages/empl_person_10102000017_*.json (через
    etl/pension.py:load_employment())

Geofabrik OSM (маршрутизация, INF-04)
  → data/curated/travel_times.csv
  → etl/pension.py:load_travel_times() → гейт G-7

UN WPP 2024 Medium (сводные показатели, реестр data/raw/registry_wpf1.csv,
переиспользовано моделью прогноза, follow_wpp: true в scenarios/base.yaml)
  → data/raw/wpp2024/blr_indicators_medium.csv
  → etl/forecast/data.py:wpp_trajectory() → etl/forecast/run.py (гейт G-2)

HMD (таблицы смертности через OWID, WP-F1/WP-F2)
  → data/curated/mortality.csv
  → etl/forecast/data.py:mortality_mx() → бэктест G-3, гейт G-2

WP P-1 (пирамиды 1989/1999, уже опубликованный ряд)
  → web/public/data/pyramids.json
  → etl/pension.py:load_national_pyramid_struct()

Модель прогноза населения v2026.4 (WP-F2/WP-F4, CCMPP + Гамильтон-Перри
+ IPF; сама модель НЕ меняется этим пакетом - только выгружена
дополнительная возрастная деталь по районам, см. docs/decisions/INF-13.md)
  → data/curated/forecast_age_by_v2026_4.json,
    forecast_age_raion_v2026_4.json
  → etl/pension.py:load_national_forecast(), load_raion_forecast()
```

## Цепочка расчёта

```text
retirement_age.csv ──────────────────────┐
age2009.csv, age2019.csv ─────────────────┤
age_current.csv (2026 jump-off) ──────────┼──> etl/pension.py:build()
pyramids.json (1989/1999) ─────────────────┤    (SR/TDR/crossing_year по
forecast_age_by/raion_v2026_4.json ────────┤     политикам x сценариям x
mortality.csv (бэктест G-3) ───────────────┤     стартовым рядам)
wages.csv, empl_person_*.json ─────────────┤
recipients_*.json, avg_pension_*.json ─────┤
travel_times.csv (G-7) ────────────────────┘
                                            │
                                            v
                              etl/pension.py:run_gates()
                              (G1: age_current.csv vs belstat_pdf-числа;
                               G2: run_scenario() независимый пересчёт;
                               G3: survival-only проекция 2009->2019;
                               G4: SR-2050 vs owid-числа;
                               G5: +-10% k/пенсия;
                               G7: travel_times <= 45 мин)
                                            │
                                            v
                          web/public/data/pension.json
                          data/curated/pension_inputs.csv
                          docs/notes/pension_validation.md
                                            │
                                            v
                          code/verify.py (этот пакет)
                          data/final/computed_results.json
```

## Итоговые файлы

| Файл | Производится | Ключевые входы |
|---|---|---|
| `web/public/data/pension.json` | `etl/pension.py:main()` | все входы выше |
| `data/curated/pension_inputs.csv` | `etl/pension.py:write_pension_inputs_csv()` | wages, employment, k_oblast, avg_pension, travel_times |
| `docs/notes/pension_validation.md` | `etl/pension.py:write_validation_notes()` | результаты `run_gates()` |
| `data/final/computed_results.json` | `code/verify.py` (этот пакет) | `web/public/data/pension.json` + `etl.pension.gate_g1()` |

## Лицензии

- Данные Белстата (dataportal, инфографика 01.01.2025) — открытые данные
  Белстата / официальная статистика Национального статистического комитета
  Республики Беларусь.
- Указ Президента №137 от 11.04.2016, Закон №118-З от 15.07.2021 —
  официальные правовые акты, не являются объектом авторского права.
- UN WPP 2024 (через OWID) — CC BY (Our World in Data), первичные данные
  UN World Population Prospects 2024.
- Времена в пути (INF-04) — производная OpenStreetMap, ODbL 1.0,
  © OpenStreetMap contributors.
- Переиспользованные ряды (переписи 2009/2019, зарплата, занятость,
  смертность, пирамиды, прогноз населения) — сохраняют лицензии своих
  первоисточников (см. `sources/registry.csv` и реестры этапов-доноров).
- Результаты пакета (`data/final/`, `web/public/data/pension.json`,
  `data/curated/pension_inputs.csv`) — CC BY 4.0 (BY Maps).
