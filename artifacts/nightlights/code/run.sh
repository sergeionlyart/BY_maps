#!/usr/bin/env bash
# Единственная точка входа: воспроизводит зональные суммы светимости,
# тренды и индекс расхождения из завендоренных лит-пикселей (стандартная
# библиотека - без rasterio), проверяет инварианты и сверяет с заявленным.
# Требования: Python >= 3.10, stdlib.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
PY="${PYTHON:-python3}"

echo "== 1/3 Зональные суммы, тренды, индекс расхождения =="
"$PY" -m etl.nightlights

echo "== 2/3 Инварианты =="
"$PY" checks/tests/test_invariants.py

echo "== 3/3 Сверка с заявленными результатами =="
"$PY" code/verify.py

echo "ГОТОВО: INF-08 воспроизведён и совпадает с заявленным."
