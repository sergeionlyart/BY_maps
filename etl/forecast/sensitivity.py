"""WP-F5, чувствительность: вариация ключевых допущений базового сценария
(+-0.1 СКР, +-1 год ОПЖ, +-50% международной миграции) -> эластичности
итогов 2050/2075.

Запуск: python -m etl.forecast.sensitivity -> docs/notes/sensitivity.json
"""
from __future__ import annotations

import copy
import json

from ..common import ROOT
from .run import load_scenarios, run_scenario


def _vary(scen: dict, what: str) -> dict:
    s = copy.deepcopy(scen)
    if what == "tfr+":
        s["tfr"] = {y: v + 0.1 for y, v in s["tfr"].items()}
    elif what == "tfr-":
        s["tfr"] = {y: max(v - 0.1, 0.5) for y, v in s["tfr"].items()}
    elif what == "e0+":
        s["e0_male"] = {y: v + 1 for y, v in s["e0_male"].items()}
        s["e0_female"] = {y: v + 1 for y, v in s["e0_female"].items()}
    elif what == "e0-":
        s["e0_male"] = {y: v - 1 for y, v in s["e0_male"].items()}
        s["e0_female"] = {y: v - 1 for y, v in s["e0_female"].items()}
    elif what == "mig+":
        s["intl_net_per_year"] = {y: v * 1.5 for y, v in s["intl_net_per_year"].items()}
    elif what == "mig-":
        s["intl_net_per_year"] = {y: v * 0.5 for y, v in s["intl_net_per_year"].items()}
    return s


def main() -> None:
    base = load_scenarios()["base"]
    ref = run_scenario(base)["BY"]
    out = {"reference": {"2050": round(ref[2051]), "2075": round(ref[2076])}}
    for what, label in [("tfr+", "СКР +0.1"), ("tfr-", "СКР -0.1"),
                        ("e0+", "ОПЖ +1 год"), ("e0-", "ОПЖ -1 год"),
                        ("mig+", "миграция x1.5"), ("mig-", "миграция x0.5")]:
        series = run_scenario(_vary(base, what))["BY"]
        out[what] = {
            "label": label,
            "2050": round(series[2051]),
            "2075": round(series[2076]),
            "delta_2050_pct": round((series[2051] / ref[2051] - 1) * 100, 2),
            "delta_2075_pct": round((series[2076] / ref[2076] - 1) * 100, 2),
        }
    dest = ROOT / "docs" / "notes" / "sensitivity.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for k, v in out.items():
        if k != "reference":
            print(f"  {v['label']:16s}: 2050 {v['delta_2050_pct']:+.2f}% | "
                  f"2075 {v['delta_2075_pct']:+.2f}%")


if __name__ == "__main__":
    main()
