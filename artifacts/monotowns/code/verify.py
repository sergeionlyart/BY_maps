#!/usr/bin/env python3
"""Сверка воспроизведённых результатов INF-06 с заявленными (в допусках)."""
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def computed_metrics() -> dict:
    m = json.loads(
        (PKG / "web" / "public" / "data" / "monotowns.json").read_text())
    a = m["aggregate"]
    return {
        "n_towns": len(m["towns"]),
        "n_industries": len(m["typology"]),
        "n_sanctioned": sum(1 for x in m["towns"] if x["nSanctions"]),
        "n_high_risk": a["byRisk"]["высокий"]["n"],
        "n_unmatched": sum(1 for x in m["towns"] if x["gap"] is None),
        "high_dep_gap": a["byDep"]["high"]["medianGap"],
        "medium_dep_gap": a["byDep"]["medium"]["medianGap"],
        "all_index": a["all"]["medianIndex2026"],
    }


def main() -> None:
    computed = computed_metrics()
    final_dir = PKG / "data" / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "computed_results.json").write_text(json.dumps(
        [{"metric": k, "value": v} for k, v in sorted(computed.items())],
        ensure_ascii=False, indent=1))
    expected = json.loads(
        (PKG / "checks" / "expected_results.json").read_text())

    failed = []
    for e in expected:
        got = computed.get(e["metric"])
        if got is None or abs(got - e["value"]) > e["tolerance"]:
            failed.append((e["metric"], e["value"], got))
    if failed:
        for m_, want, got in failed:
            print(f"РАСХОЖДЕНИЕ {m_}: заявлено {want}, получено {got}",
                  file=sys.stderr)
        sys.exit(1)
    print(f"Все {len(expected)} контрольных метрик воспроизведены в допусках.")


if __name__ == "__main__":
    main()
