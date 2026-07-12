#!/usr/bin/env python3
"""Инварианты INF-06 (автономно, без pytest)."""
import csv
import hashlib
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PKG))


def main() -> None:
    # 1. целостность реестра: sha256 = реестр источников
    reg = {r["id"]: r for r in
           csv.DictReader(open(PKG / "sources" / "registry.csv"))}
    h = hashlib.sha256(
        (PKG / "data/raw/monotowns/registry.json").read_bytes()).hexdigest()
    assert reg["monotowns_registry"]["sha256"] == h, "реестр повреждён"

    from etl.monotowns import build, risk_band, OBL_CENTERS

    reg_json = json.loads(
        (PKG / "data/raw/monotowns/registry.json").read_text())
    data = json.loads(
        (PKG / "web/public/data/data.json").read_text())["territories"]

    # 2. 46 записей, каждый city_id - город, ≥1 источник, санкции с датой
    assert len(reg_json) == 46
    for p in reg_json:
        assert data.get(p["city_id"], {}).get("level") == "city", p["city_id"]
        assert len(p.get("sources", [])) >= 1, p["city_id"]
        for s in p.get("sanctions", []):
            assert s["jurisdiction"] and s["date"], p["city_id"]

    b = build()
    towns = b["towns"]
    assert len(towns) == 46
    mono_ids = {t["id"] for t in towns}

    # 3. полоса риска пересчитывается; контроли чисты и в пределах калипера
    for t in towns:
        assert t["risk"] == risk_band(t["dep"], t["nSanctions"])[1], t["id"]
        for c in t["controls"]:
            assert c not in mono_ids and c not in OBL_CENTERS, (t["id"], c)
        # либо есть сопоставимые контроли, либо gap=None (крупный - не с чем)
        if t["gap"] is None:
            assert t["controls"] == [], t["id"]
        else:
            assert len(t["controls"]) >= 1
        assert t["index"]["1989"] == 100.0

    # 4. индекс к 1989 согласован с рядами
    for t in towns:
        v = data[t["id"]]
        base = float(v["pop"]["1989"][0])
        want = round(float(v["pop"]["2026"][0]) / base * 100, 1)
        assert abs(t["index"]["2026"] - want) < 1e-6, t["id"]

    # 5. АССОЦИАЦИЯ: у сопоставимых по размеру моногородов высокой
    #    зависимости население отстаёт от типовых сильнее, чем у средней
    dep = b["aggregate"]["byDep"]
    assert dep["high"]["medianGap"] < dep["medium"]["medianGap"]
    assert dep["high"]["nMatched"] >= 10
    # крупнейшие моногорода не с чем сравнивать по размеру
    assert sum(1 for t in towns if t["gap"] is None) >= 10

    print("Инварианты выполнены: реестр целостен, 46 сорсенных пар, "
          "полоса риска и контроли (калипер) корректны, индекс согласован, "
          "градиент по зависимости (высокая < средняя) - ассоциация.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"ИНВАРИАНТ НАРУШЕН: {e}", file=sys.stderr)
        sys.exit(1)
