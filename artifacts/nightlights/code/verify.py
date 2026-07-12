#!/usr/bin/env python3
"""Сверка воспроизведённых результатов INF-08 с заявленными (в допусках)."""
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def computed_metrics() -> dict:
    n = json.loads(
        (PKG / "web" / "public" / "data" / "nightlights.json").read_text())
    rows = {r["id"]: r for r in n["rows"]}
    out = {
        "n_zones": len(n["rows"]),
        "n_with_div": sum(1 for r in n["rows"] if r["div"] is not None),
        "div_minsk": rows["BY-HM"]["div"],
        "div_zhodzina": rows["r-smalavicki"]["div"],
        "lr_zhodzina": rows["r-smalavicki"]["lightRatio"],
        "div_barysau": rows["r-barysauski"]["div"],
        "div_homiel": rows["r-homielski"]["div"],
        "div_orsha": rows["r-arshanski"]["div"],
        "nat_light_2015": n["natLight"]["2015"],
        "nat_light_2023": n["natLight"]["2023"],
    }
    return out


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
