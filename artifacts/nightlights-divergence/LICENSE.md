# Лицензии

## Пакет

Код (`etl/`, `code/`, `checks/`), документация и итоговые данные
(`web/public/data/nightlights.json`, `data/raw/nightlights/zonal_light.csv`) —
**CC BY 4.0** со ссылкой на проект «Население Беларуси, 1897–2026» и
версию пакета.

## Входные данные

- Ночная светимость (зональная сумма из композитов VIIRS) — производная
  от EOG VNL 2.1/2.2 «average_masked» (Earth Observation Group, Payne
  Institute, Colorado School of Mines) в обработке WorldPop (University
  of Southampton, **CC BY 4.0**); при использовании цитировать оба
  источника — см. CITATION.cff и `sources/registry.csv`;
- Полигоны районов — geoBoundaries/OSM (как в основном проекте);
- Ряды населения — компиляция pop-stat.mashke.org по официальным
  переписям и оценкам Белстата.

Полный реестр с URL и sha256 каждого исходного композита — `sources/registry.csv`.
