#!/usr/bin/env python3
"""Инварианты пакета nightlights-divergence (stdlib, без pytest)."""
import json
import math
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent.parent
NL = PKG / "web" / "public" / "data" / "nightlights"

fails = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("  ok  " if ok else "  FAIL") + f"  {name}" +
          (f" — {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


cands = json.loads((NL / "research_candidates.json").read_text())["candidates"]
decomp = json.loads((NL / "divergence_decomposition.json").read_text())
night = json.loads(
    (PKG / "web/public/data/nightlights_v2.json").read_text())

# 1. три кандидата, статус candidate, гейт заполнен
check("три кандидата со статусом candidate",
      len(cands) == 3 and all(c["status"] == "candidate" for c in cands))
check("releaseApproved — булев у каждого",
      all(isinstance(c["releaseApproved"], bool) for c in cands))

# 2. направление кейса подтверждено пересчётом и согласовано со знаком
for c in cands:
    r = c["metrics"]["lightResidual"]
    want_pos = c["direction"] == "light_above_statistics"
    check(f"направление соответствует знаку резидуала: {c['id']}",
          (r > 0) == want_pos and c["directionConfirmedByRecompute"])

# 3. резидуал = dl - beta*dp (внутренняя согласованность, допуск округления)
for c in cands:
    m = c["metrics"]
    check(f"резидуал согласован: {c['id']}",
          abs(m["lightResidual"]
              - (m["lightChangeLog"] - m["betaUsed"]
                 * m["populationChangeLog"])) < 1e-3)
    check(f"pct = expm1(резидуал): {c['id']}",
          abs(m["lightResidualPct"]
              - math.expm1(m["lightResidual"]) * 100) < 0.06)

# 4. зоны кейсов существуют в наборе
zone_ids = {r["id"] for r in night["rows"]}
for c in cands:
    check(f"зоны кейса в наборе: {c['id']}",
          all(z in zone_ids for z in c["zones"]))

# 5. декомпозиция: все 119 зон, у каждой оба резидуала
check("декомпозиция по всем зонам",
      len(decomp["rows"]) == len(night["rows"]))
check("оба резидуала у каждой зоны",
      all("residualLevel" in r and "residualShare" in r
          for r in decomp["rows"]))

# 6. запрет причинных формулировок без источника
CAUSAL = ["из-за", "вызвано", "привело", "потому что", "по причине"]
check("нет причинных формулировок",
      not any(w in json.dumps(c, ensure_ascii=False).lower()
              for c in cands for w in CAUSAL))

# 7. методпереходы периода помечены qualityFlags
h2 = next(c for c in cands if c["id"] == "smolevichi-zhodino")
check("H2: шаг VNL-2021 в qualityFlags",
      "vnl_2021_step_in_period" in h2["qualityFlags"])

# 8. внешняя проверка: 3 кейса, допустимые вердикты, источники Белстата
ext = json.loads((NL / "external_checks.json").read_text())
check("внешняя проверка: три кейса",
      {c["caseId"] for c in ext["cases"]} ==
      {c["id"] for c in cands})
check("вердикты из допустимого набора",
      all(ch["verdict"] in ("consistent", "inconsistent", "context")
          for c in ext["cases"] for ch in c["checks"]))
check("каждая проверка с источником",
      all(ch.get("source") for c in ext["cases"] for ch in c["checks"]))
check("нет причинных формулировок во внешней проверке",
      not any(w in json.dumps(ext, ensure_ascii=False).lower()
              for w in CAUSAL))
h3ext = next(c for c in ext["cases"] if c["caseId"] == "astravets")
check("генерация области - контекст (не оверклейм)",
      all(ch["verdict"] == "context" for ch in h3ext["checks"]
          if ch["metric"] == "electricity_production_oblast"))

if fails:
    print(f"\nПровалено: {len(fails)}")
    sys.exit(1)
print("\nВсе инварианты выполнены.")
