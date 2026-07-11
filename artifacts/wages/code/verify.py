#!/usr/bin/env python3
"""Сверка воспроизведённых результатов INF-03 с заявленными (в допусках)."""
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def computed_metrics() -> dict:
    w = json.loads((PKG / "web" / "public" / "data" / "wages.json").read_text())
    out = {}
    for name, v in w["regressions"].items():
        out[f"beta_{name}"] = v["beta"][1]
        out[f"se_{name}"] = v["se"][1]
        out[f"se_hc1_{name}"] = v["seHc1"][1]
        out[f"r2_{name}"] = v["r2"]
        out[f"n_{name}"] = v["n"]
    for t, r in w["territories"].items():
        out[f"wage_rel_{t}"] = r["wageRel"]
        out[f"pop_change_{t}"] = r["popChange"]
    out["diag_3x3"] = sum(1 for r in w["territories"].values()
                          if r["cls"] in ("w0p0", "w2p2"))
    out["outliers_n"] = len(w["outliers"])
    out["wage_BY_2025"] = None
    import csv
    for row in csv.DictReader(open(PKG / "data" / "curated" / "wages.csv")):
        if row["territory_id"] == "BY" and row["year"] == "2025":
            out["wage_BY_2025"] = float(row["wage_byn"])
    return out


def main() -> None:
    computed = computed_metrics()
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
