#!/usr/bin/env python3
"""Инварианты данных пакета zipf. Без внешних зависимостей: plain asserts.

Запуск: python3 checks/tests/test_invariants.py (из корня пакета или откуда
угодно - пути разрешаются от расположения файла).
"""
import csv
import math
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PKG / "code"))
from build import gi_fit, parse_cities  # noqa: E402


def rows(name):
    with open(PKG / "data" / "final" / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_ranks_contiguous_and_sorted():
    by_year = {}
    for r in rows("zipf_ranks.csv"):
        by_year.setdefault(r["year"], []).append((int(r["rank"]), int(r["pop"])))
    assert len(by_year) == 12, f"ожидалось 12 срезов, получено {len(by_year)}"
    for y, lst in by_year.items():
        lst.sort()
        assert [r for r, _ in lst] == list(range(1, len(lst) + 1)), f"{y}: ранги не сплошные"
        pops = [p for _, p in lst]
        assert all(a >= b for a, b in zip(pops, pops[1:])), f"{y}: население не убывает по рангу"


def test_slopes_sane():
    for r in rows("zipf_slopes.csv"):
        b, se = float(r["slope"]), float(r["se"])
        assert -2.0 < b < -0.5, f"{r['year']}/N={r['top_n']}: наклон {b} вне разумного диапазона"
        assert se > 0
        expected_se = abs(b) * math.sqrt(2 / int(r["top_n"]))
        assert abs(se - expected_se) < 0.001, f"{r['year']}: SE не соответствует формуле GI"


def test_known_anchor_values():
    ranks = rows("zipf_ranks.csv")
    minsk_1897 = next(r for r in ranks if r["year"] == "1897" and r["rank"] == "1")
    assert minsk_1897["city_be"] == "Мінск" and int(minsk_1897["pop"]) == 90_912
    top_2026 = next(r for r in ranks if r["year"] == "2026" and r["rank"] == "2")
    assert top_2026["city_be"] == "Гомель"


def test_primacy_monotone_postwar():
    pr = {r["year"]: float(r["ratio"]) for r in rows("primacy.csv")}
    assert pr["1939"] < 2 < pr["1959"], "послевоенный перелом примации не виден"
    assert pr["2026"] > 3.5


def test_gi_estimator_on_synthetic_zipf():
    """Проверка реализации эстиматора: на последовательности P_r = C/(r - 1/2)
    регрессия log(rank - 1/2) ~ log(pop) линейна ТОЧНО, и наклон обязан быть
    ровно -1 (машинная точность). Обычная гипербола P_r = C/r здесь не
    годится: поправка Габэ-Ибрагимова несмещена для выборок из
    парето-распределения, а на детерминированной гиперболе даёт ~-1.13."""
    pops = [1_000_000 / (r - 0.5) for r in range(1, 31)]
    b, se, _ = gi_fit(pops)
    assert abs(b + 1.0) < 1e-9, f"на синтетике GI b={b}, ожидалось ровно -1"
    assert abs(se - math.sqrt(2 / 30)) < 1e-9


def test_source_parses_to_full_city_set():
    cities = parse_cities(PKG / "sources" / "raw" / "ps_cities.html")
    assert len(cities) >= 220, f"городов в источнике {len(cities)}, ожидалось >=220"
    assert cities["Мінск"]["series"][2019] == 2_018_281


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"Все {len(fns)} инвариантов выполнены.")
