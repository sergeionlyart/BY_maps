"""INF-12: реестр городских сущностей для исследования «urban-overhang».

Строит city_registry.csv (детерминированно) из данных проекта:
  - web/public/data/data.json - 222 городских поселения с рядами населения
    (переписи 'c', оценки 'e') и координатами;
  - data/curated/city_raion.csv - привязка город->район (INF-05).

Критерий основной выборки (пререгистрация v0.1, заморожена 2026-07-16):
население >= 10 000 хотя бы в одном опорном году (1959-2026) + координаты +
не менее трёх демографических точек. Поглощённые города (Восточный->Минск,
Костюковка->Гомель) - в exclusions.csv с преемником.

Запуск: python -m etl.urban_registry
Выходы: data/curated/urban/city_registry.csv, data/curated/urban/exclusions.csv
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .common import OUT, ROOT

CURATED = ROOT / "data" / "curated"
URBAN_CURATED = CURATED / "urban"
BENCHMARKS = ["1959", "1970", "1979", "1989", "1999", "2009", "2019", "2026"]
MIN_PRIMARY_POP = 10_000

# Поглощённые поселения: ряд обрывается слиянием с более крупным городом.
# Форма: city_id -> (successor_city_id, год, причина)
ABSORBED = {
    "c-uschodni": ("c-minsk", 1997, "включён в состав Минска (1997)"),
    "c-kasciukouka": ("c-homiel", 2016, "включён в состав Гомеля (2016)"),
}

# Известные переименования (события, не перезапись истории).
RENAMES = {
    "c-navapolack": "до 1963 - посёлок Полоцкий",
    "c-svietlahorsk": "до 1961 - Шатилки",
    "c-chervien": "до 1923 - Игумен",
}


def _load_cities() -> dict:
    data = json.loads((OUT / "data.json").read_text())
    return {k: v for k, v in data["territories"].items()
            if v.get("level") == "city"}


def _city_raion() -> dict[str, str]:
    m: dict[str, str] = {}
    path = CURATED / "city_raion.csv"
    with path.open() as f:
        for row in csv.DictReader(f):
            m[row["city_id"]] = row["raion_id"]
    return m


def _bench_max(v: dict) -> int:
    return max((pv[0] for y, pv in v["pop"].items()
                if y in BENCHMARKS and isinstance(pv, list) and pv[0]),
               default=0)


def _peak(v: dict) -> tuple[int, int]:
    """(peak_year, peak_value) по всем точкам ряда."""
    best_y, best_p = 0, 0
    for y, pv in sorted(v["pop"].items()):
        if isinstance(pv, list) and pv[0] and pv[0] > best_p:
            best_y, best_p = int(y), pv[0]
    return best_y, best_p


def build() -> tuple[list[dict], list[dict]]:
    """-> (registry_rows, exclusion_rows), детерминированная сортировка."""
    cities = _load_cities()
    raion = _city_raion()
    rows: list[dict] = []
    excl: list[dict] = []
    for cid in sorted(cities):
        v = cities[cid]
        bmax = _bench_max(v)
        if bmax < MIN_PRIMARY_POP:
            continue
        n_points = sum(1 for pv in v["pop"].values()
                       if isinstance(pv, list) and pv[0])
        if cid in ABSORBED:
            succ, year, why = ABSORBED[cid]
            excl.append({
                "city_id": cid, "name_ru": v["ru"],
                "reason": why, "successor_city_id": succ,
                "decided_by": "registry (пререгистрация v0.1)",
                "date": "2026-07-16",
            })
            continue
        if not v.get("lat") or not v.get("lon"):
            excl.append({
                "city_id": cid, "name_ru": v["ru"],
                "reason": "нет координат - невозможно задать seed контура",
                "successor_city_id": "",
                "decided_by": "registry (пререгистрация v0.1)",
                "date": "2026-07-16",
            })
            continue
        if n_points < 3:
            excl.append({
                "city_id": cid, "name_ru": v["ru"],
                "reason": "менее трёх демографических точек",
                "successor_city_id": "",
                "decided_by": "registry (пререгистрация v0.1)",
                "date": "2026-07-16",
            })
            continue
        py, pv_ = _peak(v)
        rows.append({
            "city_id": cid,
            "name_ru": v["ru"],
            "name_be": v.get("be", ""),
            "name_variants": RENAMES.get(cid, ""),
            "settlement_type": "urban",
            "parent_district_id": raion.get(cid, v.get("raion", "")),
            "parent_region_id": v.get("parent", ""),
            "lat": v["lat"],
            "lon": v["lon"],
            "population_peak_year": py,
            "population_peak_value": pv_,
            "flags": "|".join(v.get("flags", [])),
            "notes": v.get("note", ""),
        })
    return rows, excl


def write_population_extract(rows: list[dict]) -> None:
    """Вендорный экстракт рядов населения выбранных городов (для пакета)."""
    cities = _load_cities()
    keep = {r["city_id"] for r in rows}
    out = URBAN_CURATED / "city_population.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["city_id", "year", "population", "status"])
        for cid in sorted(keep):
            for y, pv in sorted(cities[cid]["pop"].items()):
                if isinstance(pv, list) and pv[0]:
                    w.writerow([cid, y, pv[0], pv[1]])
    print(f"population extract -> {out}")


def main() -> None:
    URBAN_CURATED.mkdir(parents=True, exist_ok=True)
    rows, excl = build()
    reg_path = URBAN_CURATED / "city_registry.csv"
    with reg_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    exc_path = URBAN_CURATED / "exclusions.csv"
    with exc_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(excl[0].keys()))
        w.writeheader()
        w.writerows(excl)
    write_population_extract(rows)
    print(f"registry: {len(rows)} городов -> {reg_path}")
    print(f"exclusions: {len(excl)} -> {exc_path}")


if __name__ == "__main__":
    main()
