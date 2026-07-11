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
