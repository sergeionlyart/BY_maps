#!/usr/bin/env python3
"""Сверка воспроизведённых результатов прогноза с заявленными (в допусках)."""
import csv
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def computed_metrics() -> dict:
    out = {}
    with open(PKG / "data" / "curated" / "forecast_v2026_1.csv") as f:
        for r in csv.DictReader(f):
            out[f"pop_{r['territory_id']}_{r['scenario']}_{r['year']}"] = float(r["pop"])
            if r["q10"]:
                out[f"q10_{r['territory_id']}_{r['scenario']}_{r['year']}"] = float(r["q10"])
            if r["q90"]:
                out[f"q90_{r['territory_id']}_{r['scenario']}_{r['year']}"] = float(r["q90"])
    bt = json.loads((PKG / "docs" / "notes" / "backtest_results.json").read_text())
    out["backtest_national_err_pct"] = bt["national"]["model_err_pct"]
    out["backtest_mape_model"] = bt["mape_model"]
    out["backtest_mape_naive"] = bt["mape_naive"]
    return out


def main() -> None:
    computed = computed_metrics()
    # зафиксировать воспроизведённые метрики (сверяется валидатором пакетов)
    final_dir = PKG / "data" / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "computed_results.json").write_text(json.dumps(
        [{"metric": k, "value": v} for k, v in sorted(computed.items())],
        ensure_ascii=False, indent=1))
    expected = json.loads((PKG / "checks" / "expected_results.json").read_text())
    failures = []
    for er in expected:
        got = computed.get(er["metric"])
        if got is None:
            failures.append(f"{er['metric']}: не воспроизведена")
        elif abs(got - er["value"]) > er["tolerance"]:
            failures.append(f"{er['metric']}: получено {got}, заявлено {er['value']} "
                            f"(допуск ±{er['tolerance']})")
        else:
            print(f"  OK {er['metric']}: {got}")
    if failures:
        print("РАСХОЖДЕНИЯ:", file=sys.stderr)
        for x in failures:
            print("  " + x, file=sys.stderr)
        sys.exit(1)
    print(f"Все {len(expected)} контрольных метрик воспроизведены в допусках.")


if __name__ == "__main__":
    main()
