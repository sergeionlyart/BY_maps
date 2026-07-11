#!/usr/bin/env bash
# Единственная точка входа: воспроизводит прогноз v2026.2 (уровни 0-3),
# бэктесты и чувствительность, проверяет инварианты и сверяет с заявленным.
# Требования: Python >= 3.10, PyYAML (pip install -r code/requirements.lock).
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
PY="${PYTHON:-python3}"

"$PY" -c "import yaml" 2>/dev/null || {
  echo "Нужен PyYAML: pip install -r code/requirements.lock"; exit 3; }

echo "== 1/6 Прогон прогноза (3 сценария, уровни 0-3) =="
"$PY" -m etl.forecast.run

echo "== 2/6 Бэктест уровней 0-1 (2009 -> 2019) =="
"$PY" -m etl.forecast.backtest

echo "== 3/6 Бэктесты уровней 2-3 (районы 2019->2026, города <=2009->2019) =="
"$PY" -m etl.forecast.backtest_sub

echo "== 4/6 Чувствительность =="
"$PY" -m etl.forecast.sensitivity

echo "== 5/6 Инварианты =="
"$PY" checks/tests/test_invariants.py

echo "== 6/6 Сверка с заявленными результатами =="
"$PY" code/verify.py

echo "ГОТОВО: прогноз воспроизведён и совпадает с заявленным."
