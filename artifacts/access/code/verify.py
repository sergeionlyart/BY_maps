#!/usr/bin/env python3
"""Сверка воспроизведённых результатов INF-04 с заявленными (в допусках)."""
import csv
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def computed_metrics() -> dict:
    a = json.loads((PKG / "web" / "public" / "data" / "access.json").read_text())
    out = {}
    names = a["beltNames"]  # без базового
    reg, now = a["regression"], a["regressionNoWage"]
    out["beta_suburb"] = reg["beta"][1 + names.index("<45 мин")]
    out["beta_ring"] = reg["beta"][1 + names.index("1,5-2,5 ч")]
    out["se_hc1_ring"] = reg["seHc1"][1 + names.index("1,5-2,5 ч")]
    out["beta_wage_control"] = reg["beta"][1 + len(names)]
    out["r2_main"] = reg["r2"]
    out["beta_suburb_nowage"] = now["beta"][1 + names.index("<45 мин")]

    prof = {p["belt"]: p for p in a["profileEff"]}
    out["n_belt_suburb"] = prof["<45 мин"]["n"]
    out["n_belt_ring"] = prof["1,5-2,5 ч"]["n"]
    out["median_suburb_eff"] = prof["<45 мин"]["median"]
    out["median_ring_eff"] = prof["1,5-2,5 ч"]["median"]
    out["median_far_eff"] = prof[">2,5 ч"]["median"]
    prof_m = {p["belt"]: p for p in a["profileMinsk"]}
    out["median_suburb_minsk"] = prof_m["<45 мин"]["median"]

    t = a["territories"]
    out["minsk_brest_min"] = t["r-brescki"]["minMinsk"]
    out["eu_delta_nadir_hrodna"] = t["r-hrodzienski"]["euDeltaNadir"]
    out["eu_delta_nadir_brest"] = t["r-brescki"]["euDeltaNadir"]

    borders = list(csv.DictReader(
        open(PKG / "data" / "curated" / "border_crossings.csv")))
    for col, name in (("status_2019", "crossings_2019"),
                      ("status_nadir", "crossings_nadir"),
                      ("status_2026", "crossings_2026")):
        out[name] = sum(1 for b in borders if b[col] == "open")
    return out


def main() -> None:
    computed = computed_metrics()
    final_dir = PKG / "data" / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "computed_results.json").write_text(json.dumps(
        [{"metric": k, "value": v} for k, v in sorted(computed.items())],
        ensure_ascii=False, indent=1))
    expected = json.loads((PKG / "checks" / "expected_results.json").read_text())

    failed = []
    for e in expected:
        got = computed.get(e["metric"])
        if got is None or abs(got - e["value"]) > e["tolerance"]:
            failed.append((e["metric"], e["value"], got))
    if failed:
        for m, want, got in failed:
            print(f"РАСХОЖДЕНИЕ {m}: заявлено {want}, получено {got}",
                  file=sys.stderr)
        sys.exit(1)
    print(f"Все {len(expected)} контрольных метрик воспроизведены в допусках.")


if __name__ == "__main__":
    main()
