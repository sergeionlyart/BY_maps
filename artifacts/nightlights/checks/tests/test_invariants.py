#!/usr/bin/env python3
"""Инварианты INF-08 (автономно, без pytest)."""
import csv
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PKG))


def main() -> None:
    # 1. целостность: sha256 зональной суммы = реестр
    reg = {r["id"]: r for r in
           csv.DictReader(open(PKG / "sources" / "registry.csv"))}
    zc = hashlib.sha256(
        (PKG / "data/raw/nightlights/zonal_light.csv").read_bytes()).hexdigest()
    assert reg["zonal_light"]["sha256"] == zc, "зональная сумма повреждена"
    # исходные композиты задокументированы (URL + sha256)
    for y in range(2015, 2024):
        r = reg[f"worldpop_viirs_fvf_{y}"]
        assert r["url"].startswith("https://data.worldpop.org")
        assert len(r["sha256"]) == 64

    from etl.nightlights import build, load_zonal, YEARS, TREND_YEARS, SHOCK_YEARS

    # 2. покрытие: 119 зон x 9 лет, без нулевых лет
    light = load_zonal()
    assert len(light) == 119
    assert sum(1 for z in light if z.startswith("r-")) == 118
    for z, ser in light.items():
        assert set(ser) == set(YEARS) and all(v > 0 for v in ser.values()), z

    # 3. Минск и Минский район - два ярчайших источника
    for y in YEARS:
        top2 = set(sorted(light, key=lambda z: -light[z][y])[:2])
        assert top2 == {"BY-HM", "r-minski"}, (y, top2)

    # 4. доли устойчивы (гашение версии продукта): CV доли Минска мал
    nat = {y: sum(light[z][y] for z in light) for y in YEARS}
    msh = [light["BY-HM"][y] / nat[y] for y in YEARS]
    assert statistics.pstdev(msh) / statistics.mean(msh) < 0.15

    # 5. окна тренда/шока не пересекаются, скачок VNL 2021 вне обоих
    assert set(TREND_YEARS).isdisjoint(SHOCK_YEARS)
    assert 2021 not in TREND_YEARS and 2021 not in SHOCK_YEARS

    b = build()
    rows = {r["id"]: r for r in b["rows"]}
    # 6. индекс воспроизводим; Минск ≈ 0, индустриальные < 0
    for r in b["rows"]:
        if r["div"] is not None:
            rec = math.log(r["lightRatio"]) - math.log(r["popRatio"])
            assert abs(rec - r["div"]) < 1e-3, r["id"]
    assert abs(rows["BY-HM"]["div"]) < 0.15
    for z in ("r-smalavicki", "r-barysauski", "r-homielski"):
        assert rows[z]["div"] < -0.1 and rows[z]["lightRatio"] < 1.0, z

    print("Инварианты выполнены: зональная сумма целостна, 119 зон без "
          "нулевых лет, доли устойчивы, индекс воспроизводим, Минск ≈ 0, "
          "индустриальные районы гаснут сильнее населения.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"ИНВАРИАНТ НАРУШЕН: {e}", file=sys.stderr)
        sys.exit(1)
