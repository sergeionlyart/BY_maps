#!/usr/bin/env python3
"""Инварианты INF-02 (автономно, без pytest): суммы пирамид равны
официальным итогам переписей; покрытие районов; направление старения;
свойства контрфакта."""
import csv
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent.parent

# Официальные итоги переписей 2009/2019 (Белстат, области и Минск), человек
OFFICIAL = {
    "BY-BR": (1401177, 1348115), "BY-VI": (1230821, 1135731),
    "BY-HO": (1440718, 1388512), "BY-HR": (1072381, 1026816),
    "BY-MI": (1422528, 1471240), "BY-MA": (1099374, 1024751),
    "BY-HM": (1836808, 2018281),
}


def main() -> None:
    a = json.loads((PKG / "web" / "public" / "data" / "aging.json").read_text())
    t = a["territories"]

    # 1. суммы пирамид = официальные итоги (допуск - округление 34 ячеек)
    for terr, (o09, o19) in OFFICIAL.items():
        s09 = sum(t[terr]["pyramid2009"]["m"]) + sum(t[terr]["pyramid2009"]["f"])
        s19 = sum(t[terr]["pyramid2019"]["m"]) + sum(t[terr]["pyramid2019"]["f"])
        assert abs(s09 - o09) <= 17, (terr, 2009, s09, o09)
        assert abs(s19 - o19) <= 17, (terr, 2019, s19, o19)

    # 2. все 118 районов, 17 групп, индикаторы в разумных диапазонах
    rs = {k: v for k, v in t.items() if k.startswith("r-")}
    assert len(rs) == 118, len(rs)
    for k, v in rs.items():
        assert len(v["pyramid2019"]["m"]) == 17 and len(v["pyramid2019"]["f"]) == 17, k
        assert 30 < v["median2019"] < 60, k
        assert 5 < v["share65_2019"] < 35, k

    # 3. старение: медиана выросла в подавляющем большинстве районов
    ups = sum(1 for v in rs.values() if v["median2009"] and v["median2019"] > v["median2009"])
    assert ups > 100, ups

    # 4. контрфакт: годы до порога кратны шагу 5 и лежат в горизонте 60 лет
    for k, v in rs.items():
        if v["yearsTo30"] is not None:
            assert v["yearsTo30"] % 5 == 0 and 0 <= v["yearsTo30"] <= 60, k

    # 5. CSV согласован с JSON
    rows = list(csv.DictReader(open(PKG / "data" / "curated" / "aging_indicators.csv")))
    assert len(rows) == len(t), (len(rows), len(t))
    by_id = {r["territory_id"]: r for r in rows}
    for k, v in t.items():
        assert float(by_id[k]["median2019"]) == v["median2019"], k

    # 6. целостность входных CSV: каждый territory_id - ровно одна область;
    #    районы + города области = область, до человека; у Минска нет
    #    дочерних территорий (ловит коллизии id вроде двух Октябрьских)
    for year in (2009, 2019):
        obls: dict = {}
        obl_tot: dict = {}
        child_tot: dict = {}
        for r in csv.DictReader(open(PKG / "data" / "curated" / f"age{year}.csv")):
            tid, obl, v = r["territory_id"], r["oblast"], int(r["pop"])
            obls.setdefault(tid, set()).add(obl)
            if tid.startswith(("r-", "c-")):
                child_tot[obl] = child_tot.get(obl, 0) + v
            elif tid == obl:
                obl_tot[obl] = obl_tot.get(obl, 0) + v
        bad = {k: sorted(o) for k, o in obls.items() if len(o) > 1}
        assert not bad, (year, bad)
        assert child_tot.get("BY-HM", 0) == 0, (year, child_tot.get("BY-HM"))
        for obl, tot in obl_tot.items():
            if obl != "BY-HM":
                assert child_tot.get(obl) == tot, (year, obl, child_tot.get(obl), tot)

    print("Инварианты выполнены: пирамиды сходятся с переписями, 118 районов, "
          f"старение подтверждено ({ups} районов), контрфакт корректен, "
          "входные CSV аддитивны до человека.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"ИНВАРИАНТ НАРУШЕН: {e}", file=sys.stderr)
        sys.exit(1)
