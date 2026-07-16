# Локальные сценарии проекта. Python: .venv (shapely, pytest, pyyaml).

PY := .venv/bin/python

.PHONY: etl test artifact artifacts-validate web-build

etl:              ## пересборка данных: web/public/data/
	$(PY) -m etl.build && $(PY) -m etl.zipf

wpf1:             ## производные WP-F1: age2009/2019, age_current, миграция
	$(PY) -m etl.census_age && $(PY) -m etl.wpf1

forecast:         ## прогноз v2026.1: прогон + бэктест + чувствительность
	$(PY) -m etl.forecast.run
	$(PY) -m etl.forecast.backtest
	$(PY) -m etl.forecast.sensitivity

stage4:           ## INF-02 + INF-07: aging.json, chernobyl.json
	$(PY) -m etl.aging
	$(PY) -m etl.chernobyl

wpf3:             ## WP-F3: зеркальная статистика, adjustment.csv
	$(PY) -m etl.mirror

stage6:           ## INF-03 + INF-04: wages.json, access.json
	$(PY) -m etl.wages
	$(PY) -m etl.access

stage7:           ## INF-05 + INF-08: migration.json, nightlights.json
	$(PY) -m etl.migration
	$(PY) -m etl.nightlights

stage8:           ## INF-06 + INF-09: monotowns.json, shocks.json
	$(PY) -m etl.monotowns
	$(PY) -m etl.shocks

stage9:           ## INF-12: urban_overhang.json (метрики от вендоренных агрегатов)
	$(PY) -m etl.urban_registry
	$(PY) -m etl.urban

stage9-extract:   ## INF-12: растровые шаги (требует rasterio+numpy+scipy+pyosmium)
	$(PY) -m etl.urban_extract
	$(PY) -m etl.urban_morph
	$(PY) -m etl.urban_light
	$(PY) -m etl.urban_osm all
	$(PY) -m etl.urban_webgrids

test:             ## все проверки данных
	$(PY) -m pytest etl/tests/ -q

artifact:         ## make artifact SLUG=zipf - собрать и провалидировать пакет
	$(PY) -m etl.artifacts.build $(SLUG)
	$(PY) -m etl.artifacts.validate web/public/artifacts/by-maps-$(SLUG)-v*.zip

artifacts-validate:
	$(PY) -m etl.artifacts.build --all --check
	$(PY) -m etl.artifacts.validate --all

web-build:
	cd web && npm run test && npm run lint && npm run build
