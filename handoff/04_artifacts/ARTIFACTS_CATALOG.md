# Каталог артефактов BY Maps

Полный перечень материалов, доступных для скачивания и машинной проверки. Контрольные суммы sha256 вычислены по состоянию репозитория на 2026-07-12 (совпадает с опубликованным сайтом). Базовый URL: `https://by-population-maps.vercel.app`.

Машиночитаемая версия каталога: `catalog.json` (рядом с этим файлом; рекомендуемое размещение на сайте — `/artifacts/catalog.json`).

## Актуальные пакеты исследований (11)

| # | Исследование | Файл | Размер, байт | sha256 |
|---|---|---|---|---|
| INF-01 | Иерархия городов и закон Ципфа | `/artifacts/by-maps-zipf-v1.0.0.zip` | 69 741 | `d08c65ec…6ab2da3` |
| INF-02 | Старение районов | `/artifacts/by-maps-aging-v1.0.3.zip` | 728 714 | `dd1f7e43…72e619b` |
| INF-03 | Зарплата × динамика населения | `/artifacts/by-maps-wages-v1.0.0.zip` | 139 347 | `bde4b410…baca2678` |
| INF-04 | Транспортная доступность | `/artifacts/by-maps-access-v1.0.0.zip` | 14 284 335 | `bd4085f4…e96b6493` |
| INF-05 | Внутренняя и внешняя миграция | `/artifacts/by-maps-migration-v1.0.0.zip` | 2 459 850 | `8c4ac379…73d2a155` |
| INF-06 | Моногорода | `/artifacts/by-maps-monotowns-v1.0.0.zip` | 148 404 | `952d247e…3ec30911e` |
| INF-07 | Чернобыльский след | `/artifacts/by-maps-chernobyl-v1.0.0.zip` | 628 629 | `f81f86ec…34465196` |
| INF-08 | Ночные огни против статистики | `/artifacts/by-maps-nightlights-v1.0.0.zip` | 488 372 | `473d4304…7c6b89d7` |
| INF-09 | Демографические шоки XX века | `/artifacts/by-maps-shocks-v1.0.0.zip` | 116 252 | `e77b0911…e0c4bdb3`* |
| ML | ML-челленджер модели районов | `/artifacts/by-maps-mlchallenger-v1.0.0.zip` | 893 296 | `fcffd75a…0d5b03dd` |
| Прогноз | Прогноз населения 2026–2075 (v2026.4) | `/artifacts/by-maps-forecast-v1.3.0.zip` | 2 100 118 | `a693b366…fa494a58` |

*Полные sha256 — в `catalog.json` и в блоке ниже; в таблице усечены для читаемости.

```
sha256 (полные, актуальные версии):
bd4085f4f6f2c44b792aa9a2e7117d035ad80694c9b8546fc51ed762e96b6493  by-maps-access-v1.0.0.zip
dd1f7e436d039dd2230eb786f254822d78972b85b084e7a7ec212656f72e619b  by-maps-aging-v1.0.3.zip
f81f86ec5532020df92bb06634d4e81ad6b14c38bb96e0cb690e43af34465196  by-maps-chernobyl-v1.0.0.zip
a693b3663ad5ac5197bbae0da7b4badd9388e2a7f8ec25d28378e6a6fa494a58  by-maps-forecast-v1.3.0.zip
8c4ac37956bb202e6200e038eb9cd0e90fec58affa5a8c2d1bc2a4c573d2a155  by-maps-migration-v1.0.0.zip
fcffd75a2794cb1156d9c545a647394a6ceade9ca5d473e3c3f6aaf00d5b03dd  by-maps-mlchallenger-v1.0.0.zip
952d247e35451572067b19cef800e24391ab29d79164eaef38b41df3ec30911e  by-maps-monotowns-v1.0.0.zip
473d430482023f4787712bb6b0ab163c20ab1d963a37a52db625caa87c6b89d7  by-maps-nightlights-v1.0.0.zip
e77b0911a0714036ad2722f99ece12b23fd5cecc02153260a662d97be0c4bdb3  by-maps-shocks-v1.0.0.zip
bde4b4106417e5b518e77740099670d8912b00e32b0334c6942d753ebaca2678  by-maps-wages-v1.0.0.zip
d08c65ec8f2f6485461522f6655af51adae0af6e9d956e44749f591266ab2da3  by-maps-zipf-v1.0.0.zip
```

## Состав каждого пакета

`README.md` (вопрос → вывод → воспроизведение) · `manifest.json` (паспорт: файлы + sha256, источники, ожидаемые результаты с допусками, окружение) · `AGENT.md` (3 задания для LLM-агента) · `LIMITATIONS.md` · `PROVENANCE.md` · `CITATION.cff` · `LICENSE.md` · `sources/registry.csv` + `raw/` (сырые данные) · `data/intermediate/`, `data/final/` (обработанные наборы и таблицы расчётов) · `code/` (fetch.py, build.py, requirements.lock, `run.sh`) · `params/assumptions.yaml` · `checks/` (тесты, эталоны, checksums.sha256).

## Архивные версии (история релизов, доступны на сайте)

| Файл | Размер, байт | sha256 (полный) |
|---|---|---|
| by-maps-aging-v1.0.0.zip | 727 360 | `1d2fb37f9fd78ded2b84bd0770013bce2fda12207f68c4d7f4cbd301375bee52` |
| by-maps-aging-v1.0.1.zip | 727 661 | `c2a7aa94bba6e149785ed67a8b9d49262a40221c7c5e6c5f4db7981f3fa5e782` |
| by-maps-aging-v1.0.2.zip | 727 917 | `6fad08863edaf113742c70b04e918b851bf1e882a9ab3508d226249b6d997c4b` |
| by-maps-forecast-v1.0.0.zip | 841 762 | `c9d8ef85623610cb8f0ed6651d69c327239449eb42169b11ef442c54b47698d6` |
| by-maps-forecast-v1.0.1.zip | 841 753 | `074be0f7d815d04d47ed5bd1707f8e0cfa01ea91c43378f80965007a579cae4b` |
| by-maps-forecast-v1.1.0.zip | 1 098 719 | `7208813565d06d1f0678ac3f7d9115bcb7d8ad6f2061139baea6251f0f79a925` |
| by-maps-forecast-v1.2.0.zip | 2 087 758 | `47a5ce5bcfb59b98d5ff6a293c9a801bea7dda357976d3ce7a73610d58947486` |

## Наборы данных сайта

| Ресурс | Что содержит |
|---|---|
| `/data/data.json` | Все ряды населения 1897–2026 (страна, области, 118 районов, 222 города) с пометками достоверности (перепись/оценка/ретроспектива/вычислено), русские и белорусские названия, площади, панель урбанизации |
| `/data/forecast.json` | Прогноз v2026.4: все уровни, 3 сценария × 2 стартовых ряда (official/adjusted), квантили q05–q95 вероятностного веера |
| `/data/geo/*.geojson` | Границы областей, районов, городов (geoBoundaries CC BY 3.0 + OSM ODbL) |

## Документы и отчёты (в репозитории)

| Документ | Содержание |
|---|---|
| `docs/METHODOLOGY.md` | Гармонизация границ, уровни достоверности, ограничения |
| `docs/SOURCES.md` | Все источники с URL, лицензиями, датами обращения |
| `docs/ARTIFACT_STANDARD.md` | Нормативный стандарт пакетов (v1.0) |
| `docs/ROADMAP_FORECAST.md`, `docs/TASK_SPEC.md` | Дорожная карта и план работ |
| `docs/notes/validation.md` | Отчёт о валидации прогноза: бэктесты, калибровки, чувствительность |
| `docs/notes/adjustment.md` | WP-F3: оценка неучтённой эмиграции 178–416 тыс. |
| `docs/notes/*.json` | Машиночитаемые результаты бэктестов, кросс-чеков, чувствительности |
| `web/public/content/methods/*.md` | Методблоки всех 10 исследований (8 обязательных полей) |

## Код

Полный исходный код (ETL, модели, тесты, веб-приложение): репозиторий `github.com/sergeionlyart/BY_maps` (**должен стать публичным до релиза — задача T-01**). Git-теги версий пакетов: `artifact-<slug>-vX.Y.Z`.

## Как проверить целостность скачанного

```bash
sha256sum by-maps-zipf-v1.0.0.zip   # сверить с таблицей выше / catalog.json
```

Внутри пакета: `sha256sum -c checks/checksums.sha256` проверяет каждый файл пакета.

> **Примечание для группы разработки:** после любой пересборки пакетов контрольные суммы обязаны быть перегенерированы (см. T-09 в FIX_TASKS) — этот каталог фиксирует состояние на 2026-07-12.
