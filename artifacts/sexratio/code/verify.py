#!/usr/bin/env python3
"""Сверка воспроизведённых результатов INF-20 с заявленными (в допусках).

Вердикты гипотез кодируются числом: 1 — подтверждена, 0 — опровергнута.
Гейты — 1 пройден, 0 нет. Это позволяет сверять их тем же механизмом
допусков, что и непрерывные метрики (допуск 0 = точное совпадение).
"""
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def computed_metrics(root: Path = PKG) -> dict:
    d = json.loads((root / "web" / "public" / "data" / "sexratio.json").read_text())
    F, G, P = d["findings"], d["gates"], d["posthoc"]
    T = d["territories"]
    out = {
        "country_sex_ratio_2019": d["country"]["sex_ratio_2019"],
        "n_raions": len(T),
        # H1 — опровергнута; предсказывался положительный знак
        "h1_confirmed": 1 if F["H1"]["verdict"] == "confirmed" else 0,
        "h1_median_r2539_2019": F["H1"]["median_r2539_2019"],
        "h1_spearman_rho": F["H1"]["spearman_rho"],
        "h1_spearman_p": F["H1"]["spearman_p"],
        "h2_confirmed": 1 if F["H2"]["verdict"] == "confirmed" else 0,
        "h2_minsk_r2539_2019": F["H2"]["cities"]["BY-HM"],
        "h2_brest_r2539_2019": F["H2"]["cities"]["c-brest"],
        "h3_confirmed": 1 if F["H3"]["verdict"] == "confirmed" else 0,
        "h3_raions_migration_dominant": F["H3"]["raions_migration_dominant"],
        "h4_confirmed": 1 if F["H4"]["verdict"] == "confirmed" else 0,
        "h4_max_r70_2019": F["H4"]["max_r70_2019"],
        "h4_median_r70_2019": F["H4"]["median_r70_2019"],
        "h4_median_r70_2046": F["H4"]["median_r70_2046"],
        "posthoc_census_perimeter_rho": P["census_perimeter_h1"]["spearman_rho"],
        "posthoc_size_rho": P["size_effect"]["spearman_rho"],
        "posthoc_narrow_age_spikes": len(P["narrow_age_male_spike"]),
        "female_surplus_raions_2019": d["female_surplus_2019"]["n"],
        "s4_census_median_0_4": G["S-4"]["census_2019"]["median"],
        "s6_net_residual": G["S-6"]["net_residual"],
        "gates_passed_s1_s6": sum(1 for k in ("S-1", "S-2", "S-3", "S-4", "S-5", "S-6")
                                  if G[k]["pass"]),
    }
    for rid in ("r-ivacevicki", "r-minski", "r-brescki"):
        out[f"r2539_2019_{rid}"] = T[rid]["summary"]["2019"]["r2539"]
        out[f"r70_2019_{rid}"] = T[rid]["summary"]["2019"]["r70"]
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
