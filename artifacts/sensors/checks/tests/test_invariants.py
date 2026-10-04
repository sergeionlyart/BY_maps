#!/usr/bin/env python3
"""Инварианты INF-21 (автономно, без pytest).

Повторяют блокирующие гейты пререгистрации V-1…V-5 (с поправкой 1 от
2026-10-04) и фиксируют вердикты, включая опровержения H2-H4.
"""
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PKG))

from etl.sensors import (LIGHT_SEAMS, WIN_L_DMSP, WIN_L_POST, WIN_L_PRE,  # noqa: E402
                         build, crosses_seam)


def main() -> None:
    r = build()
    g = r["gates"]
    for k in ("V-1", "V-2", "V-3", "V-4", "V-5"):
        assert g[k]["pass"], (k, g[k])
    # стыки сенсоров огней не пересекаются ни одним окном
    assert LIGHT_SEAMS == [(2011, 2012), (2020, 2021)]
    for w in (WIN_L_PRE, WIN_L_POST, WIN_L_DMSP):
        assert not crosses_seam(w), w
    # покрытие: 118 районов; из окна 1990-2020 выпадает только Дрибинский
    assert len(r["territories"]) == 118
    assert g["V-5"]["og_1990_2020_missing"] == ["r-drybinski"]
    # H1 подтверждена; H2-H4 опровергнуты — опровержения не должны исчезнуть
    f = r["findings"]
    assert f["H1"]["verdict"] == "confirmed" and f["H1"]["rho"] >= 0.60
    for h in ("H2", "H3", "H4"):
        assert f[h]["verdict"] == "refuted", h
    # гармонизация INF-08 не создала опровержение H2
    for y, dev in r["summary"]["vnl_raw_vs_lshare_max_pct"].items():
        assert dev < 2.0, (y, dev)
    # пост-хок помечен; уровни согласны, изменения — нет
    ph = r["posthoc"]
    assert "пост-хок" in ph["disclaimer"].lower()
    assert min(ph["level_rho_light_vs_pop"].values()) >= 0.80
    assert ph["median_dO_1319"] < 0 < ph["median_dL_1319"]
    print("Инварианты INF-21: все выполнены.")


if __name__ == "__main__":
    main()
