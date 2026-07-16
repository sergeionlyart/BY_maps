#!/usr/bin/env python3
"""Инварианты данных пакета INF-12 (автономно, stdlib, без pytest)."""
import csv
import json
import math
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[2]
RAW = PKG / "sources" / "raw"
FINAL = PKG / "data" / "final"

EPOCHS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020]
SCENARIOS = [f"t{t:02d}_c{c}" for t in (5, 10, 20) for c in (0, 1, 2)]

failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        failures.append(msg)


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --- реестр
reg = rows(RAW / "city_registry.csv")
ids = [r["city_id"] for r in reg]
check(len(ids) == len(set(ids)), "city_id не уникальны")
check(len(ids) >= 90, f"городов в реестре {len(ids)} < 90")
for r in reg:
    check(51.0 < float(r["lat"]) < 56.5 and 23.0 < float(r["lon"]) < 33.0,
          f"{r['city_id']}: координата вне Беларуси")

# --- морфология: покрытие и эпохи (2025/2030 GHSL - не наблюдения)
morph = rows(RAW / "morph_city_epoch.csv")
check(len(morph) == len(SCENARIOS) * len(EPOCHS) * len(reg),
      "morph_city_epoch: неполное покрытие сценарий x эпоха x город")
check({int(r["epoch"]) for r in morph} == set(EPOCHS),
      "эпохи не совпадают с 1975-2020")

# --- фикс-рамка: ядро + край + буфер = рамка (зоны без пересечений)
for r in rows(RAW / "morph_fixed.csv"):
    total = float(r["built_fixed_m2"])
    parts = (float(r["built_core_m2"]) + float(r["built_edge_m2"])
             + float(r["built_buffer_m2"]))
    check(abs(total - parts) <= max(1.0, 1e-6 * total),
          f"{r['city_id']} {r['epoch']} {r['scenario']}: ядро+край+буфер != рамка")

# --- потоки неотрицательны
for r in rows(RAW / "morph_flows.csv"):
    check(float(r["infill_m2"]) >= 0 and float(r["edge_m2"]) >= 0,
          f"{r['city_id']}: отрицательный поток")

# --- отрицательные контроли: вода/лес/болото
for r in rows(RAW / "morph_qa.csv"):
    check(float(r["built_m2_3km_box"]) < 90_000,
          f"контроль {r['control']} {r['epoch']}: аномальная застройка")

# --- формулы на публикуемых числах
story = json.loads((FINAL / "story.json").read_text())
n_main = 0
for cid, c in story["cities"].items():
    m = c.get("main")
    if not m:
        continue
    n_main += 1
    check(abs(m["mor"] - (m["bgr"] - m["pgr"])) < 1.5e-5,
          f"{cid}: MOR != BGR - PGR")
    pgr = (math.log(m["p2020"]) - math.log(m["p1990"])) / 30
    check(abs(pgr - m["pgr"]) < 1e-4, f"{cid}: PGR не сходится с уровнями")
    check(m["morLo"] - 1e-9 <= m["mor"] <= m["morHi"] + 1e-9,
          f"{cid}: MOR вне сценарного интервала")
    if m.get("ees") is not None:
        check(-1e-9 <= m["ees"] <= 1 + 1e-9, f"{cid}: EES вне [0,1]")
check(n_main >= 80, "городов с метриками главного интервала < 80")

# --- типология и качество
valid_types = {"T1", "T2", "T3", "T4", "T5", "T6", "TX"}
for r in rows(FINAL / "city_typology.csv"):
    check(r["primary_type"] in valid_types, f"{r['city_id']}: тип")
    check(r["quality_class"] in {"A", "B", "C", "X"}, f"{r['city_id']}: класс")

# --- запрет денежных полей (MVP)
for name in ("city_metrics.csv", "city_interval_metrics.csv",
             "city_typology.csv"):
    header = (FINAL / name).read_text(encoding="utf-8").splitlines()[0].lower()
    for bad in ("cost", "byn", "usd", "budget", "рубл"):
        check(bad not in header, f"{name}: денежное поле '{bad}'")

# --- свет: окна сенсоров
for r in rows(RAW / "city_light.csv"):
    y = int(r["year"])
    if r["sensor"] == "dmsp":
        check(1992 <= y <= 2013, f"DMSP вне окна: {y}")
    else:
        check(2012 <= y <= 2024, f"VNL вне окна: {y}")

# --- согласованность computed_results со story
comp = {r["metric"]: r["value"]
        for r in json.loads((FINAL / "computed_results.json").read_text())}
nat = story["national"]
for key in ("n_cities", "n_declining", "n_overhang_robust"):
    check(comp[key] == nat[key], f"computed vs story: {key}")
for t, n in nat["type_counts"].items():
    check(comp.get(f"type_counts.{t}") == n, f"type_counts.{t} расходится")

# --- кейсы: детерминированный алгоритм выбора (замороженный результат v1.0.0)
cases = {c["role"]: c["city_id"] for c in story["cases"]}
check("counterexample" in cases, "нет контрпримера (обязателен)")
FROZEN_CASES = {
    "satellite": "c-lahojsk",
    "monotown": "c-skidziel",
    "small_center": "c-chervien",
    "northeast": "c-krychau",
    "counterexample": "c-barysau",
}
for role, cid in FROZEN_CASES.items():
    check(cases.get(role) == cid,
          f"кейс {role}: получен {cases.get(role)}, заморожен {cid}")
counter = next(c for c in story["cases"] if c["role"] == "counterexample")
check(counter.get("strict") is False,
      "контрпример v1.0.0 нестрогий (слабейший навес) - флаг strict=false")

if failures:
    print(f"ПРОВАЛЕНО ({len(failures)}):", file=sys.stderr)
    for f in failures[:25]:
        print("  " + f, file=sys.stderr)
    sys.exit(1)
print("Все инварианты данных выполнены.")
