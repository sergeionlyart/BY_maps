"""INF-12: морфологические контуры городов по GHS-BUILT-S (однократный шаг).

Алгоритм (пререгистрация v0.1, параметры заморожены):
  1) доля застройки ячейки = built_m2 / 10000;
  2) бинаризация по порогу (основной 0.10; чувствительность 0.05/0.20);
  3) морфологическое замыкание (радиус 100 м; чувствительность 0/200 м);
  4) связные компоненты (8-связность), компоненты < 5 га не образуют контура;
  5) компонент города = компонент, содержащий seed (координату города);
     если seed вне компонента - ближайшая размеченная ячейка в радиусе 2 км;
  6) слившиеся компоненты (несколько seed) делятся по ближайшему seed (EDT);
  7) MORPH_FIXED_FRAME = объединение контуров всех эпох + буфер 1 км,
     буферные ячейки - к ближайшей ячейке-владельцу;
  8) ядро = контур 1975 года; край = ячейки фикс-рамки, вошедшие в фонд позже.

Выходы (вендорятся, стабильная сортировка):
  data/raw/urban/morph_city_epoch.csv - динамический контур: город x эпоха x сценарий
  data/raw/urban/morph_fixed.csv      - фикс-рамка и ядро/край: город x эпоха x сценарий
  data/raw/urban/morph_flows.csv      - infill/edge по интервалам x сценарий
  data/raw/urban/morph_qa.csv         - отрицательные контроли (вода/лес/болото)
Промежуточные (в .gitignore):
  data/tmp/urban/owner_<sc>_<epoch>.npy.gz - карты принадлежности
  data/tmp/urban/fixed_<sc>.npz            - фикс-рамка + эпоха входа ячейки

Запуск (требует rasterio+numpy+scipy; однократно, после etl.urban_extract):
  python -m etl.urban_morph
"""
from __future__ import annotations

import csv
import gzip
import io
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform as rio_transform
from scipy import ndimage

from .common import ROOT
from .urban_registry import URBAN_CURATED

RAW = ROOT / "data" / "raw" / "urban"
RASTERS = RAW / "rasters"
TMP = ROOT / "data" / "tmp" / "urban"

EPOCHS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020]
CELL = 100.0            # м
CELL_AREA = 10_000.0    # м²
CLIP_MINX, CLIP_MAXY = 1_591_500.0, 6_511_500.0

THRESHOLDS = [0.05, 0.10, 0.20]
CLOSING_R = [0, 1, 2]              # ячейки (0/100/200 м)
PRIMARY_SC = "t10_c1"              # порог 0.10, замыкание 100 м
MIN_COMPONENT_CELLS = 5            # 5 га
SEED_SEARCH_R = 20                 # ячейки (2 км)
BUFFER_CELLS = 10                  # 1 км

# Отрицательные контроли: центры 3-км боксов без застройки
NEG_CONTROLS = {
    "naroch_lake": (26.75, 54.85),
    "naliboki_forest": (26.28, 53.87),
    "polesie_bog": (28.25, 52.30),
}


def scen_id(thr: float, cr: int) -> str:
    return f"t{int(thr * 100):02d}_c{cr}"


def load_registry() -> list[dict]:
    with (URBAN_CURATED / "city_registry.csv").open() as f:
        return list(csv.DictReader(f))


def seeds_rc(cities: list[dict]) -> np.ndarray:
    lons = [float(c["lon"]) for c in cities]
    lats = [float(c["lat"]) for c in cities]
    xs, ys = rio_transform("EPSG:4326", "ESRI:54009", lons, lats)
    rows = ((CLIP_MAXY - np.array(ys)) / CELL).astype(int)
    cols = ((np.array(xs) - CLIP_MINX) / CELL).astype(int)
    return np.stack([rows, cols], axis=1)


def structure(radius: int) -> np.ndarray:
    if radius <= 1:
        return np.ones((3, 3), bool)
    n = 2 * radius + 1
    y, x = np.ogrid[-radius:radius + 1, -radius:radius + 1]
    return (x * x + y * y) <= radius * radius


def read_epoch(epoch: int) -> np.ndarray:
    with rasterio.open(RASTERS / f"built_E{epoch}.tif") as s:
        a = s.read(1)
    a[a > 10_000] = 0     # nodata/выбросы вне диапазона продукта
    return a


def city_owner_map(binary: np.ndarray, seeds: np.ndarray,
                   ) -> tuple[np.ndarray, list[int], dict[int, list[int]]]:
    """Карта принадлежности ячеек городам.

    -> (owner uint8: 0=нет, i+1=город i; seed_label по городам,
        clusters: label -> [индексы городов слившегося компонента])
    """
    labels, _ = ndimage.label(binary, structure=np.ones((3, 3), bool))
    sizes = np.bincount(labels.ravel())
    n = len(seeds)
    seed_label: list[int] = []
    eff_rc = seeds.copy()          # фактическая ячейка привязки
    for i in range(n):
        r, c = seeds[i]
        lab = 0
        if 0 <= r < labels.shape[0] and 0 <= c < labels.shape[1]:
            lab = int(labels[r, c])
        if lab and sizes[lab] >= MIN_COMPONENT_CELLS:
            seed_label.append(lab)
            continue
        r0, r1 = max(0, r - SEED_SEARCH_R), r + SEED_SEARCH_R + 1
        c0, c1 = max(0, c - SEED_SEARCH_R), c + SEED_SEARCH_R + 1
        win = labels[r0:r1, c0:c1]
        valid = (win > 0) & (sizes[win] >= MIN_COMPONENT_CELLS)
        cand = np.argwhere(valid)
        if len(cand) == 0:
            seed_label.append(0)
            continue
        # КРУПНЕЙШИЙ валидный компонент в окне (не ближайший!): у монотонного
        # продукта появление мелкого осколка рядом с seed не должно
        # перепривязывать город (поправка A2 пререгистрации: коллапс Бреста).
        # Привязка - к ближайшей ячейке выбранного компонента.
        cand_labels = win[cand[:, 0], cand[:, 1]]
        best_lab = int(cand_labels[int(np.argmax(sizes[cand_labels]))])
        own = cand[cand_labels == best_lab]
        d2 = (own[:, 0] + r0 - r) ** 2 + (own[:, 1] + c0 - c) ** 2
        best = own[int(np.argmin(d2))]
        eff_rc[i] = (best[0] + r0, best[1] + c0)
        seed_label.append(best_lab)
    owner = np.zeros(labels.shape, np.uint8)
    by_label: dict[int, list[int]] = {}
    for i, lab in enumerate(seed_label):
        if lab:
            by_label.setdefault(lab, []).append(i)
    objects = ndimage.find_objects(labels)
    for lab, members in sorted(by_label.items()):
        sl = objects[lab - 1]
        comp = labels[sl] == lab
        region = owner[sl]
        if len(members) == 1:
            region[comp] = members[0] + 1
            owner[sl] = region
            continue
        # multi-source allocation: ближайший seed внутри компонента
        seed_arr = np.zeros(comp.shape, np.uint8)
        for i in members:
            rr = min(max(eff_rc[i][0] - sl[0].start, 0), comp.shape[0] - 1)
            cc = min(max(eff_rc[i][1] - sl[1].start, 0), comp.shape[1] - 1)
            seed_arr[rr, cc] = i + 1
        _, (ir, ic) = ndimage.distance_transform_edt(
            seed_arr == 0, return_indices=True)
        nearest = seed_arr[ir, ic]
        region[comp] = nearest[comp]
        owner[sl] = region
    return owner, seed_label, by_label


def perimeter_and_area(owner: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Периметр (в рёбрах ячеек) и площадь (в ячейках) по каждому городу."""
    area = np.bincount(owner.ravel(), minlength=n + 1)[1:]
    per = np.zeros(n + 1, np.int64)
    pad = np.pad(owner, 1)
    h, w = owner.shape
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb = pad[1 + dr:h + 1 + dr, 1 + dc:w + 1 + dc]
        diff = owner != nb
        per += np.bincount(owner[diff].ravel(), minlength=n + 1)
    return per[1:], area


def save_owner(path: Path, owner: np.ndarray) -> None:
    buf = io.BytesIO()
    np.save(buf, owner)
    path.write_bytes(gzip.compress(buf.getvalue(), 6))


def load_owner(path: Path) -> np.ndarray:
    return np.load(io.BytesIO(gzip.decompress(path.read_bytes())))


def zsum(owner: np.ndarray, weights: np.ndarray, n: int) -> np.ndarray:
    return np.bincount(owner.ravel(), weights=weights.ravel(),
                       minlength=n + 1)[1:]


def main() -> None:
    TMP.mkdir(parents=True, exist_ok=True)
    cities = load_registry()
    ids = [c["city_id"] for c in cities]
    seeds = seeds_rc(cities)
    n = len(cities)

    epoch_rows: list[dict] = []
    fixed_rows: list[dict] = []
    flow_rows: list[dict] = []
    qa_rows: list[dict] = []

    arrays: dict[int, np.ndarray] = {}

    for thr in THRESHOLDS:
        for cr in CLOSING_R:
            sc = scen_id(thr, cr)
            struct = structure(cr) if cr else None
            union_owner = None
            entry = None
            prev_owner = None
            prev_arr = None
            for ei, epoch in enumerate(EPOCHS):
                if epoch not in arrays:
                    arrays[epoch] = read_epoch(epoch)
                arr = arrays[epoch]
                binary = arr >= thr * CELL_AREA
                if struct is not None:
                    binary = ndimage.binary_closing(binary, structure=struct)
                owner, seed_label, by_label = city_owner_map(binary, seeds)
                save_owner(TMP / f"owner_{sc}_{epoch}.npy.gz", owner)
                per, area = perimeter_and_area(owner, n)
                built_dyn = zsum(owner, arr.astype(np.float64), n)
                if union_owner is None:
                    union_owner = np.zeros(owner.shape, np.uint8)
                    entry = np.zeros(owner.shape, np.uint8)
                newly = (owner > 0) & (union_owner == 0)
                union_owner[newly] = owner[newly]
                entry[newly] = ei + 1
                cluster_of: dict[int, str] = {}
                for lab, members in by_label.items():
                    if len(members) > 1:
                        for i in members:
                            cluster_of[i] = "|".join(
                                ids[j] for j in sorted(members) if j != i)
                for i in range(n):
                    epoch_rows.append({
                        "scenario": sc, "city_id": ids[i], "epoch": epoch,
                        "seed_found": 1 if seed_label[i] else 0,
                        "footprint_cells": int(area[i]),
                        "built_dyn_m2": round(float(built_dyn[i]), 1),
                        "perimeter_edges": int(per[i]),
                        "merged_with": cluster_of.get(i, ""),
                    })
                if prev_owner is not None:
                    delta = arr.astype(np.int32) - prev_arr.astype(np.int32)
                    pos = np.where(delta > 0, delta, 0).astype(np.float64)
                    neg = np.where(delta < 0, -delta, 0).astype(np.float64)
                    infill = zsum(np.where(prev_owner > 0, prev_owner, 0), pos, n)
                    outside = np.where(prev_owner == 0, owner, 0)
                    edge = zsum(outside, pos, n)
                    negsum = zsum(np.where(owner > 0, owner, 0), neg, n)
                    for i in range(n):
                        flow_rows.append({
                            "scenario": sc, "city_id": ids[i],
                            "epoch_start": EPOCHS[ei - 1], "epoch_end": epoch,
                            "infill_m2": round(float(infill[i]), 1),
                            "edge_m2": round(float(edge[i]), 1),
                            "negative_m2": round(float(negsum[i]), 1),
                        })
                prev_owner, prev_arr = owner, arr
            # MORPH_FIXED_FRAME: union + буфер 1 км
            dist, (ir, ic) = ndimage.distance_transform_edt(
                union_owner == 0, return_indices=True)
            fixed_owner = np.where(dist <= BUFFER_CELLS,
                                   union_owner[ir, ic], 0).astype(np.uint8)
            del dist, ir, ic
            np.savez_compressed(TMP / f"fixed_{sc}.npz",
                                fixed_owner=fixed_owner, entry=entry)
            # зоны фикс-рамки: ядро (контур 1975), край (вошло в фонд позже),
            # буфер (не входило в контур ни в одну эпоху) - строго раздельно,
            # согласованно со световыми зонами etl/urban_light.py
            fixed_cells = np.bincount(fixed_owner.ravel(), minlength=n + 1)[1:]
            core_owner = np.where(entry == 1, fixed_owner, 0)
            edge_owner = np.where(entry >= 2, fixed_owner, 0)
            buffer_owner = np.where(entry == 0, fixed_owner, 0)
            core_cells = np.bincount(core_owner.ravel(), minlength=n + 1)[1:]
            for ei, epoch in enumerate(EPOCHS):
                arrf = arrays[epoch].astype(np.float64)
                built_fixed = zsum(fixed_owner, arrf, n)
                built_core = zsum(core_owner, arrf, n)
                built_edge = zsum(edge_owner, arrf, n)
                built_buffer = zsum(buffer_owner, arrf, n)
                for i in range(n):
                    fixed_rows.append({
                        "scenario": sc, "city_id": ids[i], "epoch": epoch,
                        "fixed_cells": int(fixed_cells[i]),
                        "core_cells": int(core_cells[i]),
                        "built_fixed_m2": round(float(built_fixed[i]), 1),
                        "built_core_m2": round(float(built_core[i]), 1),
                        "built_edge_m2": round(float(built_edge[i]), 1),
                        "built_buffer_m2": round(float(built_buffer[i]), 1),
                    })
            print(f"scenario {sc}: ok")

    for name, (lon, lat) in NEG_CONTROLS.items():
        (x,), (y,) = rio_transform("EPSG:4326", "ESRI:54009", [lon], [lat])
        r, c = int((CLIP_MAXY - y) / CELL), int((x - CLIP_MINX) / CELL)
        for epoch in EPOCHS:
            box = arrays[epoch][max(0, r - 15):r + 15, max(0, c - 15):c + 15]
            qa_rows.append({
                "control": name, "epoch": epoch,
                "built_m2_3km_box": round(float(box.sum()), 1),
            })

    RAW.mkdir(parents=True, exist_ok=True)
    for fname, rows in [("morph_city_epoch.csv", epoch_rows),
                        ("morph_fixed.csv", fixed_rows),
                        ("morph_flows.csv", flow_rows),
                        ("morph_qa.csv", qa_rows)]:
        with (RAW / fname).open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"{fname}: {len(rows)} строк")


if __name__ == "__main__":
    main()
