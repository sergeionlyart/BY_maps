#!/usr/bin/env python3
"""Сверка воспроизведённых индикаторов старения с заявленными (в допусках)."""
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def computed_metrics() -> dict:
    a = json.loads((PKG / "web" / "public" / "data" / "aging.json").read_text())
    t = a["territories"]
    rs = {k: v for k, v in t.items() if k.startswith("r-")}
    out = {
        "negative_natural_raions": sum(1 for v in rs.values() if (v["naturalCagr"] or 0) < 0),
        "crossing_30pct_raions": sum(1 for v in rs.values() if v["yearsTo30"] is not None),
    }
    for terr in list(rs) + ["BY-HM", "BY-BR", "BY-VI"]:
        rec = t[terr]
        out[f"share65_2019_{terr}"] = rec["share65_2019"]
        out[f"median2019_{terr}"] = rec["median2019"]
        if rec["yearsTo30"] is not None:
            out[f"yearsTo30_{terr}"] = rec["yearsTo30"]
        if rec["naturalCagr"] is not None:
            out[f"naturalCagr_{terr}"] = rec["naturalCagr"]
        out[f"pyramid2019_sum_{terr}"] = sum(rec["pyramid2019"]["m"]) + sum(rec["pyramid2019"]["f"])
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
