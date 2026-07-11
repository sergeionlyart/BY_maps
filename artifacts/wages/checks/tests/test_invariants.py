#!/usr/bin/env python3
"""Инварианты INF-03 (автономно, без pytest)."""
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PKG))

from etl.wages import load_wages, build, MINSK_SUBURBS  # noqa: E402


def main() -> None:
    wages = load_wages()
    # 1. покрытие: 118 районов, полные годы 2010-2025
    raions = [t for t in wages if t.startswith("r-")]
    assert len(raions) == 118, len(raions)
    for t in raions:
        assert set(range(2010, 2026)) <= set(wages[t]), t
    # 2. контрольные точки страны и деноминация
    assert abs(wages["BY"][2024] - 2288.6) < 0.05
    assert 100 < wages["BY"][2010] < 150
    # 3. Минск выше страны во все годы
    for y in range(2010, 2026):
        assert wages["BY-HM"][y] > wages["BY"][y], y

    b = build()
    # 4. дифференциалы в правдоподобном коридоре
    for r in b["rows"]:
        assert 0.30 < r["wage_rel"] < 1.10, (r["id"], r["wage_rel"])
    # 5. терцили: крайние трети по 36-42 района
    from collections import Counter
    cnt = Counter(r["cls"] for r in b["rows"])
    for idx in (1, 3):
        lo = sum(v for k, v in cnt.items() if k[idx] == "0")
        hi = sum(v for k, v in cnt.items() if k[idx] == "2")
        assert 36 <= lo <= 42 and 36 <= hi <= 42, (idx, lo, hi)
    # 6. гейт: знак везде; t>3 классические; HC1 >= 2 везде,
    #    в основной и переписной > 3.5
    for name, v in b["variants"].items():
        assert v["beta"][1] > 0, name
        assert v["beta"][1] / v["se"][1] > 3, name
        assert v["beta"][1] / v["se_hc1"][1] >= 2.0, name
    for name in ("main", "window_2009_2019"):
        v = b["variants"][name]
        assert v["beta"][1] / v["se_hc1"][1] > 3.5, name
    # 7. выбросы содержательны
    out = set(b["outliers"])
    assert len(out) == 8 and (out & MINSK_SUBURBS)

    print("Инварианты выполнены: 118 районов, деноминация корректна, "
          "терцили сбалансированы, связь значима во всех спецификациях.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"ИНВАРИАНТ НАРУШЕН: {e}", file=sys.stderr)
        sys.exit(1)
