#!/usr/bin/env python3
"""Инварианты INF-07 (автономно, без pytest): суммы НП равны официальным
итогам перечней; контроли чистые и уникальные; эффект класса 1."""
import csv
import json
import math
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent.parent


def main() -> None:
    c = json.loads((PKG / "web" / "public" / "data" / "chernobyl.json").read_text())
    d = json.loads((PKG / "web" / "public" / "data" / "data.json").read_text())["territories"]
    rows = list(csv.DictReader(open(PKG / "data" / "curated" / "chernobyl_zones.csv")))

    # 1. суммы НП по зонам = официальные итоги актов, до единицы
    s21 = sum(int(r["np_prk_2021"]) + int(r["np_po_2021"]) + int(r["np_posl_2021"]) for r in rows)
    s16 = sum(int(r["np_prk_2016"]) + int(r["np_po_2016"]) + int(r["np_posl_2016"]) for r in rows)
    assert s21 == 2022, s21
    assert s16 == 2193, s16

    # 2. классификация: 3 + 9; класс 1 - официальный список эвакуации
    k1 = [p for p in c["pairs"] if p["klass"] == 1]
    assert len(k1) == 3 and len(c["pairs"]) == 12
    assert {p["ru"] for p in k1} == {"Брагинский район", "Хойникский район",
                                     "Наровлянский район"}

    # 3. контроли: уникальны, вне перечней, сопоставимы по населению-1979
    zone_ids = {r["territory_id"] for r in rows}
    controls = [p["control"] for p in c["pairs"]]
    assert len(set(controls)) == len(controls)
    for p in c["pairs"]:
        assert p["control"] not in zone_ids, p["controlRu"]
        assert abs(math.log(p["controlPop1979"] / p["pop1979"])) < 0.8, p["ru"]

    # 4. эффект: каждый район класса 1 отстал от контроля к 2019 г.
    def idx(t, base):
        return d[t]["pop"]["2019"][0] / base * 100
    for p in k1:
        assert idx(p["id"], p["pop1979"]) < idx(p["control"], p["controlPop1979"]), p["ru"]

    # 5. события аннотированы
    years = [e["year"] for e in c["events"]]
    assert years == sorted(years) and years[0] == 1986

    print("Инварианты выполнены: итоги перечней сходятся до единицы (2022/2193), "
          "12 пар, класс 1 отстал от контролей.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"ИНВАРИАНТ НАРУШЕН: {e}", file=sys.stderr)
        sys.exit(1)
