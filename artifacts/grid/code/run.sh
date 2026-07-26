#!/usr/bin/env bash
# Единственная точка входа: воспроизводит контрольные числа INF-15 из
# вендоренных промежуточных агрегатов (sources/raw) и сверяет их с
# заявленными. Требования: Python >= 3.10, bash. Внешних зависимостей
# НЕТ (stdlib) - тот же принцип, что у by-maps-urban-overhang.
#
# Полное воспроизведение сеточной части (GHS-POP тайлы -> клетки ->
# метрики -> прогноз -> кадры) описано в README.md (requirements-raster.txt:
# rasterio, scipy, Pillow); этот быстрый режим стартует от уже посчитанных
# JSON/CSV агрегатов, вендоренных в sources/raw/.
set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONDONTWRITEBYTECODE=1
PY="${PYTHON:-python3}"

echo "== 1/3 Пересчёт контрольных метрик из sources/raw =="
"$PY" code/build.py

echo "== 2/3 Инварианты данных =="
"$PY" checks/tests/test_invariants.py

echo "== 3/3 Сверка с заявленными результатами =="
"$PY" code/verify.py

echo "ГОТОВО: расчёт воспроизведён и совпадает с заявленным."
