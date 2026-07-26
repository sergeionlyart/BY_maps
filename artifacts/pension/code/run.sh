#!/usr/bin/env bash
# Единственная точка входа: пересчитывает коэффициент поддержки (SR),
# коэффициент демографической нагрузки (TDR), год перехода порогов и
# условную денежную арифметику (CG) по 118 районам и стране, 1989-2056,
# проверяет инварианты и сверяет с заявленными результатами.
# Требования: Python >= 3.10 + PyYAML (code/requirements.lock) - единственная
# внешняя зависимость (нужна только для gate_g2, см. requirements.lock).
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
PY="${PYTHON:-python3}"

echo "== 1/3 Расчёт SR/TDR/crossing_year/CG (etl.pension) =="
"$PY" -m etl.pension

echo "== 2/3 Инварианты =="
"$PY" checks/tests/test_invariants.py

echo "== 3/3 Сверка с заявленными результатами =="
"$PY" code/verify.py

echo "ГОТОВО: показатели поддержки воспроизведены и совпадают с заявленными."
