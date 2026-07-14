#!/usr/bin/env bash
# Единственная точка входа: воспроизводит pyramids.json из завендоренного
# сырья (переписи Демоскопа, годовые оценки Белстата, переписи OLAP,
# экспорт CCMPP), затем инварианты, кросс-чек WPP и сверку с заявленным.
# Требования: Python >= 3.10, stdlib.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
PY="${PYTHON:-python3}"

mkdir -p web/public/data

echo "== 1/4 Сборка pyramids.json =="
"$PY" -m etl.pyramids

echo "== 2/4 Инварианты =="
"$PY" checks/tests/test_invariants.py

echo "== 3/4 Кросс-чек WPP (сценарии проекта != варианты ООН) =="
"$PY" checks/wpp_crosscheck.py

echo "== 4/4 Сверка с заявленными результатами =="
"$PY" code/verify.py

echo "ГОТОВО: пирамида 1959-2075 воспроизведена и совпадает с заявленным."
