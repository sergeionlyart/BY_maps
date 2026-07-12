#!/usr/bin/env python3
"""Сверка воспроизведённых результатов INF-05 с заявленными (в допусках)."""
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def computed_metrics() -> dict:
    m = json.loads(
        (PKG / "web" / "public" / "data" / "migration.json").read_text())
    ext = m["external"]
    out = {
        "raion_series": len(m["raions"]),
        "raion_sum_2019": sum(v["net"].get("2019", 0)
                              for v in m["raions"].values()),
        "intl_official_2019": m["intlOfficial"]["BY"]["2019"],
        "eu_stock_2019": ext["euStock"]["2019"],
        "eu_stock_2024": ext["euStock"]["2024"],
        "eu_first_2022": ext["euFirst"]["2022"],
        "pl_stock_latest": next(c["latest"] for c in ext["countries"]
                                if c["geo"] == "PL"),
        "matrix_total": m["matrix"]["total"],
        "top_flow": m["matrix"]["flows"][0]["n"],
        "net_minsk": m["matrix"]["net"]["BY-HM"],
        "interval_low": ext["interval"]["low"],
        "interval_mid": ext["interval"]["mid"],
        "interval_high": ext["interval"]["high"],
        "rural_1959": m["ladder"]["tiers"]["rural"][0],
        "rural_2026": m["ladder"]["tiers"]["rural"][-1],
        "minsk_2026": m["ladder"]["tiers"]["minsk"][-1],
        "rate_minski_1519": m["raions"]["r-minski"]["rate1519"],
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
