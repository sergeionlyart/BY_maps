# Происхождение данных (INF-04, v1.0.0)

```
Geofabrik: belarus-latest.osm.pbf          Разведка погранпереходов
  выгрузка 2026-07-10, 345 916 651 байт      granica.gov.pl, MSWiA, VSAT,
  md5 8c2f8714… (сверен с офиц. .md5)        ГПК РБ, Minsk Dialogue
        │  (PBF не вендорится)                     │ (снапшоты страниц - в
        ▼  etl/osm_graph.py (pyosmium):            │  репозитории проекта,
  дороги motorway..tertiary + _link                │  sha256 в реестре)
        │                                          ▼
        ▼                                   border_crossings_by_eu.csv
  data/raw/osm/graph_edges.csv.gz                  │ нормализация статусов
  833 438 рёбер, sha256 в registry.csv         ▼ (легковой трафик)
        │                            data/curated/border_crossings.csv
        │                              15 переходов: 2019 / надир / 2026
        ▼                                          │
  etl/access.py: гаверсинус -> минуты; Дейкстра от Минска, 6 облцентров
  и переходов ЕС (три состояния); снап 118 райцентров (для хостов -
  город областного подчинения)
        │
        ├── зарплатный контроль: etl/wages.py <- data/raw/wages/*.json
        │   (индикатор 10218000003, тот же вендоринг, что в пакете INF-03)
        ├── население района: web/public/data/data.json (минус город-хост)
        ▼
  пояса + профиль по медианам + OLS с HC1
        │
        ▼
  web/public/data/access.json + data/curated/travel_times.csv
```

Все шаги от `graph_edges.csv.gz` детерминированы; случайности и внешних
вызовов нет. Единственный шаг вне пакета — извлечение графа из PBF
(`etl/osm_graph.py`, включён как документация): он требует pyosmium и
исходный PBF, контрольные суммы обоих зафиксированы в
`sources/registry.csv`.
