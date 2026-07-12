#!/usr/bin/env bash
# Единственная точка входа: воспроизводит лестницу, сальдо районов,
# матрицу и внешнюю панель из завендоренного сырья, проверяет инварианты
# и сверяет с заявленным. Требования: Python >= 3.10, stdlib (~5 c).
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
PY="${PYTHON:-python3}"

echo "== 1/3 Лестница, сальдо, матрица, внешняя волна =="
"$PY" -m etl.migration

echo "== 2/3 Инварианты =="
"$PY" checks/tests/test_invariants.py

echo "== 3/3 Сверка с заявленными результатами =="
"$PY" code/verify.py

echo "ГОТОВО: INF-05 воспроизведён и совпадает с заявленным."
