#!/usr/bin/env python3
"""Инварианты INF-04 (автономно, без pytest)."""
import csv
import hashlib
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PKG))


def main() -> None:
    # 1. целостность графа: sha256 совпадает с реестром OSM
    reg = {r["id"]: r for r in
           csv.DictReader(open(PKG / "sources" / "registry.csv"))}
    h = hashlib.sha256(
        (PKG / "data/raw/osm/graph_edges.csv.gz").read_bytes()).hexdigest()
    assert h == reg["graph_edges"]["sha256"], "граф подменён или повреждён"

    # 2. реестр переходов: 15 записей, статусы 13/4/6, хронология полна
    borders = list(csv.DictReader(
        open(PKG / "data/curated/border_crossings.csv")))
    assert len(borders) == 15
    counts = tuple(sum(1 for b in borders if b[c] == "open")
                   for c in ("status_2019", "status_nadir", "status_2026"))
    assert counts == (13, 4, 6), counts
    for b in borders:
        if b["status_2019"] == "open" and b["status_2026"] == "closed":
            assert b["closed_date"] and b["closed_by"], b["name_ru"]

    a = json.loads((PKG / "web/public/data/access.json").read_text())
    t = a["territories"]
    # 3. покрытие и коридоры травел-таймов
    assert len(t) == 118
    for k, v in t.items():
        assert 0 <= v["minMinsk"] < 400, k
        assert v["eff"] <= v["minMinsk"] + 1e-9, k
        # доступность ЕС: 2019 лучшая, надир худший, 2026 между ними
        assert v["eu2019"] - 1e-9 <= v["eu2026"] <= v["euNadir"] + 1e-9, k

    # 4. пояса покрывают все районы; профиль немонотонный («тень»)
    prof = {p["belt"]: p for p in a["profileEff"]}
    assert sum(p["n"] for p in prof.values()) == 118
    assert prof["<45 мин"]["median"] > prof["1,5-2,5 ч"]["median"]
    assert prof[">2,5 ч"]["median"] > prof["1,5-2,5 ч"]["median"]

    # 5. регрессия: знаки поясов; кольцо остаётся дном и в модели
    names = a["beltNames"]
    reg_ = a["regression"]
    assert reg_["n"] == 118
    assert reg_["beta"][1 + names.index("<45 мин")] > 0
    assert reg_["beta"][1 + names.index("1,5-2,5 ч")] < 0
    assert reg_["beta"][1 + names.index("1,5-2,5 ч")] == min(
        reg_["beta"][1 + names.index(b)] for b in names)

    # 6. локализация пограничного шока: и нулевые, и >1,5-часовые потери
    deltas = [v["euDeltaNadir"] for v in t.values()]
    assert min(deltas) == 0 and max(deltas) > 90

    print("Инварианты выполнены: граф целостен, 118 районов, переходы "
          "13/4/6, профиль немонотонный, шок границы локализован.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"ИНВАРИАНТ НАРУШЕН: {e}", file=sys.stderr)
        sys.exit(1)
