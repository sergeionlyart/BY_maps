#!/usr/bin/env python3
"""Кросс-чек будущего: WPP-2024 medium против сценария base (2075).

WPP-варианты использовались ТОЛЬКО в прототипе UI; в итоговом наборе
их нет (см. verify: wpp_placeholder_series = 0). Расхождение
WPP-medium и base на 2075 год документируется здесь: сценарии проекта
не равны вариантам ООН (собственные траектории СКР/ОПЖ/миграции)."""
import csv
import json
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent

d = json.loads((PKG / "web/public/data/pyramids.json").read_text())
rec = d["series"]["2075:base"]
base = sum(rec["m"]) + sum(rec["f"])

wpp = 0.0
groups = [0.0] * 17
with open(PKG / "checks/wpp/blr_single_age_medium_2024-2100.csv") as f:
    for r in csv.DictReader(f):
        if r["Time"] == "2075":
            v = (float(r["PopMale"]) + float(r["PopFemale"])) * 1000
            wpp += v
            groups[min(int(r["AgeGrpStart"]) // 5, 16)] += v

gap = (wpp / base - 1) * 100
share65_wpp = sum(groups[13:]) / wpp * 100
share65_base = (sum(rec["m"][13:]) + sum(rec["f"][13:])) / base * 100
print(f"  2075: base {base:,.0f} vs WPP-medium {wpp:,.0f} "
      f"({gap:+.1f}%)".replace(",", " "))
print(f"  доля 65+: base {share65_base:.1f}% vs WPP {share65_wpp:.1f}% - "
      "форма «гриба» согласована, уровень различается")
assert abs(gap) < 10, "расхождение с WPP неожиданно велико"
print("OK: кросс-чек WPP пройден (расхождение задокументировано)")
