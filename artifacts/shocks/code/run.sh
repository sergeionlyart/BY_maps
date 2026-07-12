#!/usr/bin/env bash
# Единственная точка входа: воспроизводит национальный ряд, доли-1897 и
# события из сырья, проверяет инварианты и сверяет с заявленным.
# Python >= 3.10, stdlib (~2 c).
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
PY="${PYTHON:-python3}"
echo "== 1/3 Ряд, доли-1897, события =="
"$PY" -m etl.shocks
echo "== 2/3 Инварианты =="
"$PY" checks/tests/test_invariants.py
echo "== 3/3 Сверка с заявленными результатами =="
"$PY" code/verify.py
echo "ГОТОВО: INF-09 воспроизведён и совпадает с заявленным."
