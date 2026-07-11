#!/usr/bin/env python3
"""Сверка воспроизведённых результатов INF-07 с заявленными (в допусках)."""
import csv
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def computed_metrics() -> dict:
    c = json.loads((PKG / "web" / "public" / "data" / "chernobyl.json").read_text())
    d = json.loads((PKG / "web" / "public" / "data" / "data.json").read_text())["territories"]
    rows = list(csv.DictReader(open(PKG / "data" / "curated" / "chernobyl_zones.csv")))

    def idx2019(t: str, base: float) -> float:
        return d[t]["pop"]["2019"][0] / base * 100

    out = {
        "pairs_total": len(c["pairs"]),
        "class1_pairs": sum(1 for p in c["pairs"] if p["klass"] == 1),
        "districts_in_lists": len(rows),
        "np_total_2021": sum(int(r["np_prk_2021"]) + int(r["np_po_2021"]) + int(r["np_posl_2021"]) for r in rows),
        "np_total_2016": sum(int(r["np_prk_2016"]) + int(r["np_po_2016"]) + int(r["np_posl_2016"]) for r in rows),
        "closed_area_total_ha": round(sum(p["closedHa"] or 0 for p in c["pairs"]), 1),
    }
    gaps1 = []
    for p in c["pairs"]:
        a = idx2019(p["id"], p["pop1979"])
        g = a - idx2019(p["control"], p["controlPop1979"])
        out[f"idx2019_{p['id']}"] = round(a, 2)
        out[f"gap2019_{p['id']}"] = round(g, 2)
        if p["klass"] == 1:
            gaps1.append(g)
    out["mean_gap_class1"] = round(sum(gaps1) / len(gaps1), 2)
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
