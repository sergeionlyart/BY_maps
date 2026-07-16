#!/usr/bin/env bash
# Единственная точка входа: воспроизводит расчёт INF-12 от вендоренных
# агрегатов (sources/raw) до итоговых таблиц и сверяет контрольные числа.
# Требования: Python >= 3.10, bash. Внешних зависимостей НЕТ (stdlib).
#
# Полное воспроизведение растровой части (GHSL -> морфология -> свет -> OSM)
# описано в README.md (code/fetch.py + rasterio/numpy/scipy/pyosmium);
# быстрый режим стартует от вендоренных зональных агрегатов.
set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONDONTWRITEBYTECODE=1
PY="${PYTHON:-python3}"

echo "== 1/3 Расчёт от sources/raw до data/final =="
"$PY" code/build.py

echo "== 2/3 Инварианты данных =="
"$PY" checks/tests/test_invariants.py

echo "== 3/3 Сверка с заявленными результатами =="
"$PY" code/verify.py

echo "ГОТОВО: расчёт воспроизведён и совпадает с заявленным."
