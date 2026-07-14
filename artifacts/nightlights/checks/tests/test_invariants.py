#!/usr/bin/env python3
"""Инварианты INF-08 v2 (автономно, без pytest, stdlib)."""
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PKG))

DMSP_YEARS = list(range(1992, 2014))
VNL_YEARS = list(range(2012, 2025))


def _zonal(fname, col):
    zones, by = defaultdict(dict), {}
    for r in csv.DictReader(open(PKG / "data/raw/nightlights" / fname)):
        y, v = int(r["year"]), float(r[col])
        if r["zone_id"] == "BY":
            by[y] = v
        else:
            zones[r["zone_id"]][y] = v
    return zones, by


def main() -> None:
    # 1. целостность: sha256 вырезок растров = реестр; источники
    #    задокументированы (URL + лицензия + sha256 глобального файла)
    reg = {r["id"]: r for r in
           csv.DictReader(open(PKG / "sources" / "registry.csv"))}
    for y in DMSP_YEARS:
        p = PKG / f"data/raw/nightlights/rasters/dmsp_{y}.tif"
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        assert reg[f"clip_dmsp_{y}"]["sha256"] == h, f"dmsp_{y} повреждён"
        assert len(reg[f"li_caldmsp_{y}"]["sha256"]) == 64
        assert reg[f"li_caldmsp_{y}"]["license"]
    for y in VNL_YEARS:
        p = PKG / f"data/raw/nightlights/rasters/vnl_{y}.tif"
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        assert reg[f"clip_vnl_{y}"]["sha256"] == h, f"vnl_{y} повреждён"
        assert len(reg[f"vnl_avg_{y}"]["sha256"]) == 64

    # 2. покрытие: 119 зон x все годы сегмента, без нулевых зоно-лет;
    #    сумма зон = страна (допуск 1% - приграничные пиксели маски)
    dmsp, dmsp_by = _zonal("zonal_dmsp.csv", "dn_sum")
    vnl, vnl_by = _zonal("zonal_vnl.csv", "radiance")
    for zones, by, years in [(dmsp, dmsp_by, DMSP_YEARS),
                             (vnl, vnl_by, VNL_YEARS)]:
        assert len(zones) == 119
        assert sum(1 for z in zones if z.startswith("r-")) == 118
        assert "BY-HM" in zones
        for z, ser in zones.items():
            assert set(ser) == set(years), z
            assert all(v > 0 for v in ser.values()), z
        for y, tot in by.items():
            s = sum(zones[z][y] for z in zones)
            assert 0.99 <= s / tot <= 1.0 + 1e-9, (y, s / tot)

    # 3. гейты гармонизации (ТЗ): R² моста >= 0,9; стык <= 5%
    from etl import nightlights_harmonize as H
    v = H.validation()
    assert v["bridge"]["r2"] >= 0.90, v["bridge"]
    assert abs(v["seam_gap"]) <= 0.05, v["seam_gap"]
    assert 0.5 < v["bridge"]["b"] < 2.5
    # спайк: «готовый» simVIIRS нестабильнее фактического VNL
    assert v["spike"]["vol_ratio"] > 1.0
    assert v["spike"]["zero_zone_years_sim"] > 0
    assert v["spike"]["zero_zone_years_vnl"] == 0
    # кросс-проверка против WorldPop fvf (независимая обработка)
    assert all(r > 0.9 for r in v["worldpop_r2"].values()), v["worldpop_r2"]

    # 4. модель: floor+bright = свет 2024; beta = пересчёту; сценарная
    #    монотонность; adjusted <= official; свет >= floor
    from etl import nightlights_model as M
    assump = M.load_assumptions()
    fl = M.load_floor()
    for z, f in fl.items():
        tot = vnl[z][2024] if z != "BY" else None
        if tot is not None:
            assert abs(f["floor"] + f["bright"] - tot) <= 0.011, z
    cross = M.estimate_beta_cross(assump)
    stored = assump["model"]["beta"]
    assert abs(stored["industrial"] - cross["industrial"]["beta"]) < 0.05
    assert abs(stored["rural"] - cross["rural"]["beta"]) < 0.05
    assert stored["minsk_agglo"] == 1.0 and stored["oblast_center"] == 1.0
    fut = M.future_light(assump)
    nodes = fut["nodes"]
    for j in M.JUMPOFFS:
        for s in M.SCENARIOS:
            for z, ser in fut["light"][j][s].items():
                assert all(x >= fl[z]["floor"] - 1e-9 for x in ser.values())
    nat_a = sum(v[nodes[0]] for v in fut["light"]["adjusted"]["base"]
                .values())
    nat_o = sum(v[nodes[0]] for v in fut["light"]["official"]["base"]
                .values())
    assert nat_a <= nat_o + 1e-6 and nat_o / nat_a - 1 < 0.02
    for z in fut["light"]["official"]["negative"]:
        assert (fut["light"]["official"]["negative"][z][nodes[-1]]
                <= fut["light"]["official"]["optimistic"][z][nodes[-1]]
                + 1e-9), z
        # анкер adjusted согласован: по зонам различие только за счёт
        # динамики рядов (допуск 2%)
        for t in (nodes[0], nodes[-1]):
            assert (fut["light"]["adjusted"]["base"][z][t]
                    <= fut["light"]["official"]["base"][z][t] * 1.02
                    + 1e-9), (z, t)

    # 5. финальный набор: структура, доли суммируются в 1, маркировка
    #    модельного сегмента отделена от наблюдений
    n = json.loads((PKG / "web/public/data/nightlights_v2.json")
                   .read_text())
    assert n["yearsObs"] == list(range(1992, 2025))
    assert len(n["rows"]) == 119
    assert n["segments"]["model"][0] > n["segments"]["vnl"][1]
    for y in (1992, 2011, 2012, 2024):
        s = sum(r["lshare"].get(str(y), 0) for r in n["rows"])
        assert abs(s - 1.0) < 2e-3, (y, s)
    for r in n["rows"]:
        for j in ("official", "adjusted"):
            for s in ("base", "negative", "optimistic"):
                assert len(r["model"][j][s]) == 10, (r["id"], j, s)

    print("Все инварианты INF-08 v2 выполнены "
          "(целостность, покрытие, гейты стыка, модель, финальный набор).")


if __name__ == "__main__":
    main()
