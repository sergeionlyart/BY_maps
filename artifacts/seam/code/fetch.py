#!/usr/bin/env python3
"""Загрузка глобальных растров «Шва на карте» и сверка sha256 (по желанию).

Для воспроизведения оценок загрузка НЕ нужна: code/run.sh работает от
вложенной таблицы ячеек sources/raw/cells.csv.gz. Этот скрипт нужен, чтобы
проверить, что источники по-прежнему доступны и не изменились после даты
обращения (2026-10-04), и чтобы пересобрать таблицу ячеек тяжёлым шагом
code/extract/seam_extract.py (numpy, rasterio, shapely).

Список файлов, адреса и sha256 — sources/registry_files.csv.
Только стандартная библиотека.

Запуск:  python3 code/fetch.py --list
         python3 code/fetch.py --source li_ntl_v10 --out /tmp/seam_raw
         python3 code/fetch.py --all --out /tmp/seam_raw          # ~570 МБ без VNL
         python3 code/fetch.py --source vnl_v21_zenodo --out ...  # глобальные VNL, несколько ГБ
Раскладка в --out совпадает с ожидаемой etl/seam_extract.py (SEAM_RAW):
ghsl/, wsf/, li/, glad/, misc/.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
import urllib.request
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
REGISTRY = PKG / "sources" / "registry_files.csv"
UA = "Mozilla/5.0 BY-maps-seam-artifact"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=1800) as r, open(part, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    part.replace(dest)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", action="append", default=[], help="id источника (можно несколько раз)")
    ap.add_argument("--all", action="store_true", help="все источники с sha256 (без VNL)")
    ap.add_argument("--list", action="store_true", help="показать источники и число файлов")
    ap.add_argument("--out", type=Path, default=Path.cwd() / "seam_downloads", help="папка загрузок")
    a = ap.parse_args()

    rows = list(csv.DictReader(open(REGISTRY, encoding="utf-8")))
    if a.list or not (a.source or a.all):
        by = {}
        for r in rows:
            by.setdefault(r["source_id"], 0)
            by[r["source_id"]] += 1
        for k, n in by.items():
            print(f"{k:24s} {n:3d} файл(ов)")
        return
    want = set(a.source)
    sel = [r for r in rows if (r["source_id"] in want) or (a.all and r["sha256"])]
    if not sel:
        sys.exit("нет файлов для выбранных источников (см. --list)")

    changed, failed = [], []
    for r in sel:
        dest = a.out / r["file"]
        if not dest.exists():
            print("загрузка", r["url"])
            try:
                download(r["url"], dest)
            except Exception as e:  # noqa: BLE001 - отчёт о недоступности, а не падение
                failed.append((r["file"], str(e)))
                print("  НЕДОСТУПНО:", e)
                continue
        if r["sha256"]:
            got = sha256_file(dest)
            if got != r["sha256"]:
                changed.append(r["file"])
                print(f"  ИЗМЕНИЛСЯ после {r['accessed']}: {r['file']} ({got[:12]}… вместо {r['sha256'][:12]}…)")
            else:
                print(f"  OK sha256 {r['file']}")
        else:
            print(f"  sha256 не зафиксирован (читался по сети): {r['file']}")

    print(f"\nфайлов: {len(sel)}, изменилось: {len(changed)}, недоступно: {len(failed)}")
    if changed or failed:
        print("Изменение или недоступность источника — НЕ ошибка пакета: оценки воспроизводятся от "
              "вложенной таблицы ячеек. Зафиксируйте это в отчёте (AGENT.md, задача 1).")
        sys.exit(1)


if __name__ == "__main__":
    main()
