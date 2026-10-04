#!/usr/bin/env python3
"""Инварианты INF-21 (автономно, без pytest).

Повторяют блокирующие гейты пререгистрации S-1…S-6 (с поправками от
2026-10-04) и фиксируют главные выводы, включая опровержение H1.
"""
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PKG))

from etl.sexratio import AGE_GROUPS, build  # noqa: E402


def main() -> None:
    r = build()
    g = r["gates"]
    # гейты S-1…S-6
    for k in ("S-1", "S-2", "S-3", "S-4", "S-5", "S-6"):
        assert g[k]["pass"], (k, g[k])
    # S-3: разбиение замкнуто, страна 2019 = итог переписи
    assert g["S-3"]["2019"]["country"] == 9_413_446
    # покрытие
    assert len(r["territories"]) == 118
    assert len(AGE_GROUPS) == 17
    for rid, t in r["territories"].items():
        for y in ("2009", "2019"):
            assert t["summary"][y]["r2539"] is not None, (rid, y)
    # H1 опровергнута с обратным знаком — факт опровержения не должен исчезнуть
    h1 = r["findings"]["H1"]
    assert h1["verdict"] == "refuted" and h1["spearman_rho"] < 0 and h1["spearman_p"] < 0.05
    # H2-H4 подтверждены
    for h in ("H2", "H3", "H4"):
        assert r["findings"][h]["verdict"] == "confirmed", h
    # 70+: мужчин меньше половины женщин в медиане
    assert r["findings"]["H4"]["median_r70_2019"] < 50
    # пост-хок помечен и повторяет знак на переписном периметре
    ph = r["posthoc"]
    assert "пост-хок" in ph["disclaimer"].lower()
    assert ph["census_perimeter_h1"]["n"] == 118
    assert ph["census_perimeter_h1"]["spearman_rho"] < 0
    print("Инварианты INF-21: все выполнены.")


if __name__ == "__main__":
    main()
