#!/usr/bin/env bash
# Единственная точка входа: воспроизводит прогноз v2026.1, бэктест и
# чувствительность, проверяет инварианты и сверяет с заявленными результатами.
# Требования: Python >= 3.10, PyYAML (pip install -r code/requirements.lock).
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
PY="${PYTHON:-python3}"

"$PY" -c "import yaml" 2>/dev/null || {
  echo "Нужен PyYAML: pip install -r code/requirements.lock"; exit 3; }

echo "== 1/5 Прогон прогноза (3 сценария, уровни 0-1) =="
"$PY" -m etl.forecast.run

echo "== 2/5 Бэктест 2009 -> 2019 =="
"$PY" -m etl.forecast.backtest

echo "== 3/5 Чувствительность =="
"$PY" -m etl.forecast.sensitivity

echo "== 4/5 Инварианты =="
"$PY" checks/tests/test_invariants.py

echo "== 5/5 Сверка с заявленными результатами =="
"$PY" code/verify.py

echo "ГОТОВО: прогноз воспроизведён и совпадает с заявленным."
