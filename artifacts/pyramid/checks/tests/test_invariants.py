#!/usr/bin/env python3
"""Инварианты пакета pyramid (stdlib, без pytest)."""
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent.parent
GROUPS = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34",
          "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69",
          "70-74", "75-79", "80+"]

fails = []


def check(name: str, ok: bool) -> None:
    print(("  ok  " if ok else "  FAIL") + f"  {name}")
    if not ok:
        fails.append(name)


d = json.loads((PKG / "web/public/data/pyramids.json").read_text())
s = d["series"]

check("порядок 17 групп фиксирован", d["age_groups"] == GROUPS)
check("типы кадров из допустимого набора",
      all(r["type"] in ("census", "estimate", "interpolated", "model")
          for r in s.values()))
check("у каждого кадра источник", all(r.get("source") for r in s.values()))
check("история 1959-2026 без разрывов",
      all(str(y) in s for y in range(1959, 2027)))
check("модельная сетка полная (10 лет x 3 сценария x 2 старта)",
      all(f"{y}:{sc}" in s and f"{y}:{sc}:adjusted" in s
          for y in range(2030, 2076, 5)
          for sc in ("base", "optimistic", "negative")))
check("переписи помечены census",
      all(s[k]["type"] == "census"
          for k in ("1959", "1970", "1979", "1989", "2009", "2019")))
check("кадр 1999 - оценка (переписной таблицы в открытом виде нет)",
      s["1999"]["type"] == "estimate")
check("unknown не входит в бары (2009: 296 отдельно)",
      s["2009"].get("unknown") == 296)
check("нет отрицательных значений",
      all(v >= 0 for r in s.values() for v in r["m"] + r["f"]))
check("будущее только из CCMPP (WPP-заглушки нет)",
      all("ccmpp" in r["source"].lower() for r in s.values()
          if r["type"] == "model")
      and not any("wpp" in r["source"].lower() for r in s.values()))

# монотонность старения: доля 65+ в base растёт от 2030 к 2075
def share65(k):
    r = s[k]
    tot = sum(r["m"]) + sum(r["f"])
    return (sum(r["m"][13:]) + sum(r["f"][13:])) / tot

check("доля 65+ (base) растёт 2030->2075",
      share65("2030:base") < share65("2050:base") < share65("2075:base"))

if fails:
    print(f"\nПровалено: {len(fails)}")
    sys.exit(1)
print("\nВсе инварианты выполнены.")
