#!/usr/bin/env python3
"""Независимый пересчёт трёх чисел INF-22 «Второй сенсор» — свой код, без
импорта etl.sensors. Вход — только сырые CSV проекта; доли, логарифмы и ранги
написаны заново.

  (а) ρ Спирмена H1: Δln доли района, официальный ряд vs GHS-POP, 1990→2020,
      районы с обоими значениями на обеих эпохах (ожидается 117, без Дрибинского);
  (б) доля Минска в официальном ряду на эпоху 2020;
  (в) ρ H2 на СЫРЫХ радиансах VIIRS (а не на гармонизированных долях INF-08):
      Δln доли в свете 2013→2019 vs Δln доли в официальном ряду (data.json).

Запуск: python3 tools/checks/sensors_independent_check.py
"""
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def pearson(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    return num / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))


def rho(a, b):
    return pearson(ranks(a), ranks(b))


# --- (а), (б): reconciliation.csv ------------------------------------------
off, grid = {}, {}
for r in csv.DictReader(open(ROOT / "data/raw/grid/reconciliation.csv", encoding="utf-8")):
    e = int(r["epoch"])
    if r["official"]:
        off[(r["raion"], e)] = float(r["official"])
    grid[(r["raion"], e)] = float(r["grid_sum"])
zones = sorted({z for z, _ in grid})
both = [z for z in zones if all((z, e) in off and (z, e) in grid for e in (1990, 2020))]
def share(src, z, e):
    return src[(z, e)] / sum(src[(q, e)] for q in both)
dO = [math.log(share(off, z, 2020) / share(off, z, 1990)) for z in both if z != "BY-HM"]
dG = [math.log(share(grid, z, 2020) / share(grid, z, 1990)) for z in both if z != "BY-HM"]
print(f"(а) H1: n = {len(dO)}, rho = {rho(dO, dG):.4f}  (опубликовано 0.7895, n = 117)")
# в окне 1990→2020 доли считаются по набору зон окна (поправка 1: без
# Дрибинского района); по всем зонам — для сравнения, разница ~0,0002
tot_all = sum(off[(z, 2020)] for z in zones if (z, 2020) in off)
print(f"(б) доля Минска, официальный ряд 2020: по зонам окна = {share(off, 'BY-HM', 2020):.5f}"
      f"  (опубликовано 0.21492); по всем зонам = {off[('BY-HM', 2020)] / tot_all:.5f}")

# --- (в): zonal_vnl.csv + data.json -----------------------------------------
rad = {}
for r in csv.DictReader(open(ROOT / "data/raw/nightlights/zonal_vnl.csv", encoding="utf-8")):
    rad[(r["zone_id"], int(r["year"]))] = float(r["radiance"])
data = json.loads((ROOT / "web/public/data/data.json").read_text())
T = data["territories"]
zl = sorted(z for z, v in T.items() if v["level"] == "raion" or z == "BY-HM")
def pop(z, y):
    return float(T[z]["pop"][str(y)][0])
def sh(f, z, y):
    return f(z, y) / sum(f(q, y) for q in zl)
lr = lambda z, y: rad[(z, y)]  # noqa: E731
rz = [z for z in zl if z != "BY-HM"]
dO2 = [math.log(sh(pop, z, 2019) / sh(pop, z, 2013)) for z in rz]
dL2 = [math.log(sh(lr, z, 2019) / sh(lr, z, 2013)) for z in rz]
print(f"(в) H2 на сырых радиансах VIIRS: n = {len(rz)}, rho = {rho(dO2, dL2):.4f}"
      "  (опубликовано на долях INF-08 -0.132)")
