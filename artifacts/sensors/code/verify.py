#!/usr/bin/env python3
"""Сверка воспроизведённых результатов INF-22 с заявленными (в допусках).

Вердикты гипотез кодируются числом: 1 — подтверждена, 0 — опровергнута.
Гейты — 1 пройден, 0 нет. Это позволяет сверять их тем же механизмом
допусков, что и непрерывные метрики (допуск 0 = точное совпадение).
"""
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def computed_metrics(root: Path = PKG) -> dict:
    d = json.loads((root / "web" / "public" / "data" / "sensors.json").read_text())
    F, G, P, S = d["findings"], d["gates"], d["posthoc"], d["summary"]
    T = d["territories"]
    belts = {b["belt"]: b for b in P["belts_minsk"]}
    out = {
        "n_raions": len(T),
        "n_og_1990_2020": S["n_og"],
        "gates_passed_v1_v5": sum(1 for k in ("V-1", "V-2", "V-3", "V-4", "V-5")
                                  if G[k]["pass"]),
        "v4_light_rho_2018_2019": G["V-4"]["rho_2018_2019"],
        # H1 — подтверждена
        "h1_confirmed": 1 if F["H1"]["verdict"] == "confirmed" else 0,
        "h1_rho": F["H1"]["rho"],
        "h1_robust_2000_2020_rho": F["H1"]["robust_2000_2020_rho"],
        "h1_sign_agree": S["sign_agree_OG"],
        # H2-H4 — опровергнуты
        "h2_confirmed": 1 if F["H2"]["verdict"] == "confirmed" else 0,
        "h2_rho": F["H2"]["rho"],
        "h2_p": F["H2"]["p"],
        "h2_robust_dmsp_rho": F["H2"]["robust_dmsp_rho"],
        "h3_confirmed": 1 if F["H3"]["verdict"] == "confirmed" else 0,
        "h3_rho": F["H3"]["rho"],
        "h4_confirmed": 1 if F["H4"]["verdict"] == "confirmed" else 0,
        "h4_ratio": F["H4"]["ratio"],
        "minsk_share_official_2020": round(S["minsk_share"]["O"]["2020"], 4),
        "minsk_share_ghs_2020": round(S["minsk_share"]["G"]["2020"], 4),
        "posthoc_level_rho_2019": P["level_rho_light_vs_pop"]["2019"],
        "posthoc_light_up_pop_down": P["light_up_pop_down_1319"],
        "posthoc_median_dO_1319": P["median_dO_1319"],
        "posthoc_median_dL_1319": P["median_dL_1319"],
        "posthoc_persistence_rho": P["light_change_persistence_rho"],
        "posthoc_belt_60_120_dL": belts["60-120"]["median_dL"],
    }
    for rid in ("r-minski", "r-astraviecki", "r-smalavicki"):
        out[f"dL_1319_{rid}"] = T[rid]["dL_1319"]
        out[f"dO_1319_{rid}"] = T[rid]["dO_1319"]
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
