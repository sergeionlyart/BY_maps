#!/usr/bin/env bash
# Единственная точка входа: воспроизводит типологию, полосу риска и
# matched-comparison из реестра моногородов и рядов городов, проверяет
# инварианты и сверяет с заявленным. Python >= 3.10, stdlib (~2 c).
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
PY="${PYTHON:-python3}"

echo "== 1/3 Типология, риск, matched-comparison =="
"$PY" -m etl.monotowns

echo "== 2/3 Инварианты =="
"$PY" checks/tests/test_invariants.py

echo "== 3/3 Сверка с заявленными результатами =="
"$PY" code/verify.py

echo "ГОТОВО: INF-06 воспроизведён и совпадает с заявленным."
