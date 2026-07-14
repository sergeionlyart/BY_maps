#!/usr/bin/env python3
"""Сверка воспроизведённого pyramids.json с заявленными результатами."""
import csv
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def computed_metrics() -> dict:
    d = json.loads(
        (PKG / "web/public/data/pyramids.json").read_text())
    s = d["series"]

    def tot(k):
        r = s[k]
        return sum(r["m"]) + sum(r["f"]) + r.get("unknown", 0)

    out = {
        "series_total": len(s),
        "census_1959": tot("1959"), "census_1970": tot("1970"),
        "census_1979": tot("1979"), "census_1989": tot("1989"),
        "census_2009": tot("2009"), "census_2019": tot("2019"),
        "estimate_2026": tot("2026"),
        "unknown_2009": s["2009"].get("unknown", 0),
        "model_2075_base": tot("2075:base"),
        "model_2075_negative": tot("2075:negative"),
        "model_2075_optimistic": tot("2075:optimistic"),
        "wpp_placeholder_series": sum(
            1 for rec in s.values()
            if "wpp" in rec.get("source", "").lower()
            or "placeholder" in rec.get("type", "")),
    }
    # кросс-чек WPP medium 2075 против base
    wpp = 0.0
    with open(PKG / "checks/wpp/blr_single_age_medium_2024-2100.csv") as f:
        for r in csv.DictReader(f):
            if r["Time"] == "2075":
                wpp += (float(r["PopMale"]) + float(r["PopFemale"])) * 1000
    out["wpp_medium_2075_gap_pct"] = round(
        (wpp / out["model_2075_base"] - 1) * 100, 1)
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
    failures = []
    for er in expected:
        got = computed.get(er["metric"])
        if got is None:
            failures.append(f"{er['metric']}: не вычислена")
        elif abs(got - er["value"]) > er["tolerance"]:
            failures.append(f"{er['metric']}: {got} != {er['value']} "
                            f"(допуск {er['tolerance']})")
    if failures:
        print("РАСХОЖДЕНИЯ:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print(f"OK: {len(expected)} метрик совпадают с заявленными.")


if __name__ == "__main__":
    main()
