#!/usr/bin/env python3
"""Инварианты INF-05 (автономно, без pytest)."""
import csv
import hashlib
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PKG))


def main() -> None:
    # 1. целостность сырья: sha256 каждого файла = реестр
    reg = {r["notes"]: r["sha256"] for r in
           csv.DictReader(open(PKG / "sources" / "registry.csv"))}
    raw = PKG / "data" / "raw" / "migration"
    for f in raw.iterdir():
        if f.name == "registry.csv" or f.name.startswith("."):
            continue
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        assert reg.get(f.name) == h, f"хеш не совпал: {f.name}"

    from etl.migration import (build, oblast_flows, raion_net,
                               ESTIMATES, NON_EU)

    # 2. аддитивность: сумма районов области = область (2019, 2024)
    net = raion_net()
    flows = oblast_flows()
    data = json.loads(
        (PKG / "web/public/data/data.json").read_text())["territories"]

    def obl_of(t):
        v = data[t]
        return v["parent"] if v["level"] == "raion" else \
            data[v["raion"]]["parent"] if v.get("raion") else v["parent"]

    for obl in ("BY-BR", "BY-VI", "BY-HO", "BY-HR", "BY-MI", "BY-MA"):
        for y in (2019, 2024):
            s = sum(ser.get(y, 0) for t, ser in net.items()
                    if obl_of(t) == obl)
            want = flows[obl]["Всего по всем потокам миграции"][y]
            assert s == want, (obl, y, s, want)

    # 3. дыра 2020-2023 и покрытие
    assert len(net) == 128
    for t, ser in net.items():
        assert not set(ser) & {2020, 2021, 2022, 2023}, t

    b = build()
    # 4. ярусы: полное разбиение страны
    l = b["ladder"]
    for i, y in enumerate(l["years"]):
        total = sum(l["tiers"][k][i] for k in l["tiers"])
        want = float(data["BY"]["pop"][str(y)][0])
        assert abs(total - want) < 1, y

    # 5. матрица: нетто страны = 0, магнит один
    m = b["matrix"]
    assert sum(m["net"].values()) == 0
    assert m["net"]["BY-HM"] > 0
    assert all(v < 0 for k, v in m["net"].items() if k != "BY-HM")

    # 6. приёмка: у каждой внешней цифры источник + снапшот в реестре
    for e in ESTIMATES:
        assert e["who"] and e["published"] and e["snap"] in reg, e
        assert e["low"] <= e["high"]
    for n in NON_EU:
        assert n["src"] and n["snap"] in reg, n

    # 7. кумулятив хронологии монотонен и сходится к интервалу
    ext = b["external"]
    tl = ext["timeline"]
    for k in ("low", "mid", "high"):
        assert all(a <= b_ for a, b_ in zip(tl[k], tl[k][1:]))
        assert tl[k][-1] == ext["interval"][k]

    print("Инварианты выполнены: сырьё целостно, районы аддитивны "
          "области, дыра 2020-2023 подтверждена, ярусы полны, "
          "источники и интервалы на месте.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"ИНВАРИАНТ НАРУШЕН: {e}", file=sys.stderr)
        sys.exit(1)
