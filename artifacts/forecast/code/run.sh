#!/usr/bin/env bash
# Единственная точка входа: воспроизводит прогноз v2026.3 (уровни 0-3,
# ряды official/adjusted),
# бэктесты и чувствительность, проверяет инварианты и сверяет с заявленным.
# Требования: Python >= 3.10, PyYAML (pip install -r code/requirements.lock).
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
PY="${PYTHON:-python3}"

"$PY" -c "import yaml" 2>/dev/null || {
  echo "Нужен PyYAML: pip install -r code/requirements.lock"; exit 3; }

echo "== 1/7 Реконструкция оттока (WP-F3): интервал и adjustment.csv =="
"$PY" -m etl.mirror

echo "== 2/7 Прогон прогноза (3 сценария, уровни 0-3, ряды official/adjusted) =="
"$PY" -m etl.forecast.run

echo "== 3/7 Бэктест уровней 0-1 (2009 -> 2019) =="
"$PY" -m etl.forecast.backtest

echo "== 4/7 Бэктесты уровней 2-3 (районы 2019->2026, города <=2009->2019) =="
"$PY" -m etl.forecast.backtest_sub

echo "== 5/7 Чувствительность =="
"$PY" -m etl.forecast.sensitivity

echo "== 6/7 Инварианты =="
"$PY" checks/tests/test_invariants.py

echo "== 7/7 Сверка с заявленными результатами =="
"$PY" code/verify.py

echo "ГОТОВО: прогноз воспроизведён и совпадает с заявленным."
