#!/usr/bin/env python3
"""Сверка воспроизведённых результатов с заявленными (в допусках)."""
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent

computed = {r["metric"]: r["value"]
            for r in json.loads((PKG / "data/final/computed_results.json").read_text())}
expected = json.loads((PKG / "checks/expected_results.json").read_text())

failures = []
for er in expected:
    got = computed.get(er["metric"])
    if got is None:
        failures.append(f"{er['metric']}: метрика не воспроизведена")
    elif abs(got - er["value"]) > er["tolerance"]:
        failures.append(f"{er['metric']}: получено {got}, заявлено {er['value']} "
                        f"(допуск ±{er['tolerance']})")
    else:
        print(f"  OK {er['metric']}: {got} (заявлено {er['value']} ±{er['tolerance']})")

if failures:
    print("РАСХОЖДЕНИЯ:", file=sys.stderr)
    for f in failures:
        print("  " + f, file=sys.stderr)
    sys.exit(1)
print(f"Все {len(expected)} контрольных метрик воспроизведены в допусках.")
