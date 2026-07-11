"""INF-01 `zipf`: иерархия городов и закон Ципфа, 1897-2026.

Оценка наклона rank-size распределения по каждому переписному срезу
методом Габэ-Ибрагимова (Gabaix & Ibragimov, 2011): OLS-регрессия
log(rank - 1/2) на log(население); поправка -1/2 снижает смещение малых
выборок, стандартная ошибка наклона = |b|*sqrt(2/N).

Базовый N = 30: это максимальный размер топ-списка, доступный во всех
срезах, включая 1897 год (43 города с данными). Чувствительность - N = 20
и N = 50 (с 1923 г.).

Запуск: python -m etl.zipf  ->  web/public/data/zipf.json
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from .common import RAW, OUT
from .parse_popstat import parse_cities
from .registry import city_id

YEARS = [1897, 1923, 1926, 1939, 1959, 1970, 1979, 1989, 1999, 2009, 2019, 2026]
BASELINE_N = 30
SENSITIVITY_N = [20, 30, 50]
TOP_KEEP = 50  # сколько городов среза сохраняем для скаттера


def gi_fit(pops: list[int]) -> dict:
    """Оценка Габэ-Ибрагимова по списку населений (убывание = ранги 1..N).

    Возвращает {'b': наклон, 'se': ст. ошибка, 'a': перехват, 'n': N}.
    """
    n = len(pops)
    if n < 3:
        raise ValueError("нужно не меньше трёх городов")
    xs = [math.log(p) for p in pops]
    ys = [math.log(r - 0.5) for r in range(1, n + 1)]
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    se = abs(b) * math.sqrt(2 / n)
    return {"b": b, "se": se, "a": a, "n": n}


def compute(raw_dir: Path = RAW) -> dict:
    cities = parse_cities(raw_dir / "ps_cities.html")
    per_year: dict[str, dict] = {}
    for y in YEARS:
        ranked = sorted(
            ((be, info["lat"], info["series"][y][0], info["series"][y][1])
             for be, info in cities.items() if y in info["series"]),
            key=lambda r: -r[2],
        )
        if len(ranked) < min(SENSITIVITY_N):
            continue
        slopes = {}
        for n in SENSITIVITY_N:
            if len(ranked) >= n:
                fit = gi_fit([r[2] for r in ranked[:n]])
                slopes[str(n)] = {"b": round(fit["b"], 4), "se": round(fit["se"], 4),
                                  "a": round(fit["a"], 4)}
        primacy = ranked[0][2] / ranked[1][2]
        per_year[str(y)] = {
            "n": len(ranked),
            "dtype": ranked[0][3][0] if isinstance(ranked[0][3], str) else ranked[0][3],
            "slopes": slopes,
            "primacy": round(primacy, 3),
            "top": [[city_id(lat), pop] for _, lat, pop, _ in ranked[:TOP_KEEP]],
        }
    return {
        "version": "1.0.0",
        "baselineN": BASELINE_N,
        "sensitivityN": SENSITIVITY_N,
        "years": [int(y) for y in per_year],
        "perYear": per_year,
    }


def main() -> None:
    res = compute()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "zipf.json").write_text(json.dumps(res, ensure_ascii=False))
    b19 = res["perYear"]["2019"]["slopes"]["30"]["b"]
    print(f"OK: {len(res['years'])} срезов; наклон 2019 (N=30) = {b19}; "
          f"примация 2026 = {res['perYear']['2026']['primacy']}")


if __name__ == "__main__":
    main()
