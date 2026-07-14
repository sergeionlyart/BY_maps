#!/usr/bin/env bash
# Единственная точка входа: пересчитывает кандидатов H1-H3 и зональную
# декомпозицию резидуалов из завендоренных входов (nightlights_v2.json,
# data.json, params/assumptions.json) на стандартной библиотеке,
# затем прогоняет инварианты и сверку с заявленными результатами.
# Требования: Python >= 3.10, stdlib.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
PY="${PYTHON:-python3}"

mkdir -p docs/notes web/public/data/nightlights

echo "== 1/4 Пересчёт кандидатов H1-H3 и декомпозиции =="
"$PY" -m etl.nightlights_divergence

echo "== 2/4 Внешняя проверка (производство/занятость/зарплата/миграция/энергия) =="
"$PY" -m etl.nightlights_checks

echo "== 3/4 Инварианты =="
"$PY" checks/tests/test_invariants.py

echo "== 4/4 Сверка с заявленными результатами =="
"$PY" code/verify.py

echo "ГОТОВО: кандидаты H1-H3 и внешняя проверка воспроизведены и совпадают с заявленным."
