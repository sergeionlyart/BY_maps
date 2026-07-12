#!/usr/bin/env python3
"""Сверка воспроизведённого ML-challenger с заявленными метриками (в допусках).
Все числа детерминированы (сеяный бустинг, SEED=20260712)."""
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def computed_metrics() -> dict:
    d = json.loads((PKG / "web" / "public" / "data" / "mlchallenger.json").read_text())
    s, p, h, g = d["skill"], d["permutationNull"], d["mapeHorserace"], d["goldWindow"]
    dist = {x["id"]: x for x in d["districts"]}
    return {
        "n_districts": d["n"],
        "oofR2_full": s["oofR2_full"],
        "oofR2_ctrlOnly": s["oofR2_ctrlOnly"],
        "incrementalExo": s["incrementalExo"],
        "best_m": s["best_m"],
        "repeatedCV_median": s["repeatedCV"]["median"],
        "perm_p": p["p"],
        "perm_realR2": p["realR2"],
        "mape_ccr": h["ccr"],
        "mape_ccr_plus_ml": h["ccr_plus_ml"],
        "mape_naive": h["naive"],
        "gold_oofR2": g["oofR2_vs_declinemean"],
        "imp_mig_rate1519": d["importance"]["mig_rate1519"]["mean"],
        "resid_smalavicki": dist["r-smalavicki"]["ccrResid"],
        "resid_minski": dist["r-minski"]["ccrResid"],
        "signalDetected": 1 if d["signalDetected"] else 0,
    }


def main() -> None:
    computed = computed_metrics()
    final = PKG / "data" / "final"
    final.mkdir(parents=True, exist_ok=True)
    (final / "computed_results.json").write_text(json.dumps(
        [{"metric": k, "value": v} for k, v in sorted(computed.items())],
        ensure_ascii=False, indent=1))
    expected = json.loads((PKG / "checks" / "expected_results.json").read_text())
    fail = []
    for er in expected:
        got = computed.get(er["metric"])
        if got is None:
            fail.append(f"{er['metric']}: не воспроизведена")
        elif abs(got - er["value"]) > er["tolerance"]:
            fail.append(f"{er['metric']}: получено {got}, заявлено {er['value']} "
                        f"(допуск ±{er['tolerance']})")
        else:
            print(f"  OK {er['metric']}: {got}")
    if fail:
        print("РАСХОЖДЕНИЯ:", file=sys.stderr)
        for x in fail:
            print("  " + x, file=sys.stderr)
        sys.exit(1)
    print(f"Все {len(expected)} контрольных метрик воспроизведены в допусках.")


if __name__ == "__main__":
    main()
