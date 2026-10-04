#!/usr/bin/env bash
# Единственная точка входа: пересчитывает все оценки от вложенной таблицы
# ячеек (sources/raw/cells.csv.gz) до data/final/ и проверяет их.
# Требования: Python >= 3.10, bash. Внешних зависимостей нет (только
# стандартная библиотека). Время: ~80 секунд на обычном ноутбуке.
set -euo pipefail
cd "$(dirname "$0")/.."

# не засорять пакет байткодом: содержимое дерева должно оставаться
# ровно тем, что описано в манифесте
export PYTHONDONTWRITEBYTECODE=1

PY="${PYTHON:-python3}"

echo "== 1/3 Расчёт от sources/raw до data/final =="
"$PY" code/build.py

echo "== 2/3 Инварианты данных =="
"$PY" checks/tests/test_invariants.py

echo "== 3/3 Сверка с заявленными результатами =="
"$PY" code/verify.py

echo "ГОТОВО: расчёт воспроизведён и совпадает с заявленным."
