#!/usr/bin/env python3
"""Воспроизводимый расчёт INF-01 `zipf` от сырого источника до итоговых чисел.

Самодостаточен: только стандартная библиотека Python (>= 3.10).
Вход:  sources/raw/ps_cities.html (таблица переписей городов Беларуси)
Выход: data/final/zipf_ranks.csv    - ранжировки городов по срезам
       data/final/zipf_slopes.csv   - наклоны rank-size (Габэ-Ибрагимов)
       data/final/primacy.csv       - примация (город-1 / город-2)
       data/final/computed_results.json - контрольные метрики для сверки

Параметры допущений можно варьировать (см. AGENT.md, задача 3):
  --top-n 40        другой размер топ-списка для оценки наклона
  --years 1959,2019 подмножество срезов
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent

YEARS = [1897, 1923, 1926, 1939, 1959, 1970, 1979, 1989, 1999, 2009, 2019, 2026]
SENSITIVITY_N = [20, 30, 50]
BASELINE_N = 30

CENSUS_RE = re.compile(r"^(\d{4})-\d{2}-\d{2}$")
ESTIMATE_RE = re.compile(r"^(\d{4})'$")

# заголовки областей в таблице (строки без данных)
OBLAST_HEADERS = {"Брэсцкая", "Віцебская", "Гомельская", "Гродзенская",
                  "Мінская", "Магілёўская", "г. Мінск"}


def parse_rows(html: str) -> list[list[str]]:
    """Строки таблицы pop-stat: незакрытые <td>/<th> (HTML4), без colspan."""
    rows = []
    for tr in re.split(r"<tr[^>]*>", html)[1:]:
        cells = [re.sub(r"<[^>]+>", "", td).replace("\xa0", " ").replace("&nbsp", "").strip()
                 for td in re.split(r"<t[dh][^>]*>", tr)[1:]]
        if cells:
            rows.append(cells)
    return rows


def popstat_num(cell: str) -> int | None:
    """'90,912' -> 90_912 (значения в тысячах, запятая - десятичный разделитель)."""
    cell = cell.strip()
    if not re.fullmatch(r"\d+(,\d+)?", cell or ""):
        return None
    if "," in cell:
        whole, frac = cell.split(",")
        return int(whole) * 1000 + int((frac + "000")[:3])
    return int(cell) * 1000


def parse_cities(html_path: Path) -> dict[str, dict]:
    """{be_name: {'lat': латинка, 'series': {год: население}}}.
    Перепись имеет приоритет над оценкой того же года."""
    rows = parse_rows(html_path.read_text(encoding="utf-8"))
    cols: list[tuple[int, str] | None] = []
    for cell in rows[0]:
        m = CENSUS_RE.match(cell)
        if m:
            cols.append((int(m.group(1)), "census"))
        else:
            m = ESTIMATE_RE.match(cell)
            cols.append((int(m.group(1)), "estimate") if m else None)

    cities: dict[str, dict] = {}
    for cells in rows[1:]:
        if len(cells) < 3:
            continue
        be, lat = cells[0], cells[1]
        if not be or be in OBLAST_HEADERS or be.startswith("©") or "Bespyatov" in lat:
            continue
        series: dict[int, int] = {}
        census_years: set[int] = set()
        for cell, col in zip(cells, cols):
            if col is None:
                continue
            year, dtype = col
            val = popstat_num(cell)
            if val is None:
                continue
            if dtype == "census":
                series[year] = val
                census_years.add(year)
            elif year not in census_years:
                series[year] = val
        if series:
            cities[be] = {"lat": lat, "series": series}
    return cities


def gi_fit(pops: list[int]) -> tuple[float, float, float]:
    """Оценка Габэ-Ибрагимова (2011): OLS log(rank - 1/2) ~ log(pop).
    Возвращает (наклон, ст. ошибка |b|*sqrt(2/N), перехват)."""
    n = len(pops)
    xs = [math.log(p) for p in pops]
    ys = [math.log(r - 0.5) for r in range(1, n + 1)]
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return b, abs(b) * math.sqrt(2 / n), my - b * mx


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=PKG / "sources" / "raw" / "ps_cities.html")
    ap.add_argument("--out", type=Path, default=PKG / "data" / "final")
    ap.add_argument("--top-n", type=int, default=None,
                    help="доп. размер топ-списка для стресса допущения N")
    ap.add_argument("--years", type=str, default=None,
                    help="срезы через запятую (по умолчанию все)")
    args = ap.parse_args()

    years = [int(y) for y in args.years.split(",")] if args.years else YEARS
    n_list = sorted(set(SENSITIVITY_N + ([args.top_n] if args.top_n else [])))

    cities = parse_cities(args.source)
    args.out.mkdir(parents=True, exist_ok=True)

    ranks_rows, slopes_rows, primacy_rows = [], [], []
    computed = []
    for y in years:
        ranked = sorted(((be, info["lat"], info["series"][y])
                         for be, info in cities.items() if y in info["series"]),
                        key=lambda r: -r[2])
        if len(ranked) < min(n_list):
            continue
        for rank, (be, lat, pop) in enumerate(ranked, 1):
            ranks_rows.append([y, rank, be, lat, pop])
        for n in n_list:
            if len(ranked) >= n:
                b, se, a = gi_fit([r[2] for r in ranked[:n]])
                slopes_rows.append([y, len(ranked), n, round(b, 4), round(se, 4), round(a, 4)])
                if n == BASELINE_N:
                    computed.append({"metric": f"zipf_slope_{y}_n{BASELINE_N}",
                                     "value": round(b, 4)})
                    if y == 2019:
                        computed.append({"metric": f"zipf_se_{y}_n{BASELINE_N}",
                                         "value": round(se, 4)})
        ratio = round(ranked[0][2] / ranked[1][2], 3)
        primacy_rows.append([y, ranked[0][0], ranked[0][2], ranked[1][0], ranked[1][2], ratio])
        computed.append({"metric": f"primacy_{y}", "value": ratio})
    n2019 = len([x for x in ranks_rows if x[0] == 2019])
    if n2019:
        computed.append({"metric": "n_cities_2019", "value": n2019})

    def write_csv(name: str, header: list[str], rows: list) -> None:
        with open(args.out / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(header)
            w.writerows(rows)

    write_csv("zipf_ranks.csv", ["year", "rank", "city_be", "city_lat", "pop"], ranks_rows)
    write_csv("zipf_slopes.csv", ["year", "n_available", "top_n", "slope", "se", "intercept"],
              slopes_rows)
    write_csv("primacy.csv", ["year", "city1", "pop1", "city2", "pop2", "ratio"], primacy_rows)
    (args.out / "computed_results.json").write_text(
        json.dumps(computed, ensure_ascii=False, indent=2))
    print(f"OK: {len(years)} срезов, {len(ranks_rows)} строк ранжировок -> {args.out}")


if __name__ == "__main__":
    main()
