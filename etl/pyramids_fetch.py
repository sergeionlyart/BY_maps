#!/usr/bin/env python3
"""Добыча истории для раздела «Пирамида» (INF-11, задача P-2).

Два источника:
1. Демоскоп Weekly, возрастные таблицы всесоюзных переписей по БССР
   (reg=3, все население): 1959 - sng_mar_59.php (прямой age-таблицы
   за 1959 нет, берём колонки «все» из брачной), 1970/1979/1989 -
   sng_age_*.php. Единичные возрасты до 100+ и строка «возраст не
   указан». HTML вендорится как есть (cp1251) - парсер в etl/pyramids.py.
2. Дата-портал Белстата, индикатор 10101100003 (возрастные структуры,
   17 групп x пол): годовые оценки на 1 января. Исторические годы
   заполнены с 1990-х - вендорим окна 1990-2018 (2019-2026 уже есть в
   data/curated/age_current.csv). Лимит API - 10 лет на запрос.

Выход: data/raw/pyramid/*.html, dataportal_age_*.json, registry.csv.
Запуск: python -m etl.pyramids_fetch
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

from .common import ROOT

DEST = ROOT / "data" / "raw" / "pyramid"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
API = "https://dataportal.belstat.gov.by/osids-public-api/indicator"

DEMOSCOPE = {
    "census_1959.html": (
        "http://demoscope.ru/weekly/ssp/sng_mar_59.php?reg=3&gor=3",
        "Перепись-1959, БССР: пол x возраст (колонки «все» брачной "
        "таблицы; единичные возрасты + 5-летние подытоги, до 100+)"),
    "census_1970.html": (
        "http://demoscope.ru/weekly/ssp/sng_age_70.php?reg=3&gor=3",
        "Перепись-1970, БССР: пол x возраст, все население"),
    "census_1979.html": (
        "http://demoscope.ru/weekly/ssp/sng_age_79.php?reg=3&gor=3",
        "Перепись-1979, БССР: пол x возраст, все население"),
    # ЛОВУШКА: в sng_age_89 таблица «республики И ИХ РЕГИОНЫ» -
    # нумерация регионов сквозная, Белорусская ССР = reg 27 (не 3!)
    "census_1989.html": (
        "http://demoscope.ru/weekly/ssp/sng_age_89.php?reg=27&gor=3",
        "Перепись-1989, БССР: пол x возраст, все население"),
}

# priznak_536: 17 групп + итог; priznak_391: мужчины/женщины
AGE_NODES = ["518106", "518107", "518108", "518229", "518230", "518231",
             "518232", "518233", "518234", "518235", "518236", "518237",
             "518238", "518239", "518240", "518241", "518242", "518105"]
SEX_NODES = ["517379", "517380"]
SPANS = [list(range(1990, 2000)), list(range(2000, 2010)),
         list(range(2010, 2019))]


def _fetch(url: str, post: dict | None = None) -> bytes:
    cmd = ["curl", "-sS", "--fail", "-m", "180", "-L", "-A", UA]
    if post is not None:
        cmd += ["-X", "POST", "-H", "Content-Type: application/json",
                "--data", json.dumps(post, ensure_ascii=False)]
    cmd.append(url)
    return subprocess.run(cmd, capture_output=True, check=True).stdout


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    rows = []

    for fn, (url, desc) in DEMOSCOPE.items():
        raw = _fetch(url)
        (DEST / fn).write_bytes(raw)
        rows.append({
            "file": fn, "description": desc, "url": url,
            "license": "Демоскоп Weekly (открытая публикация; "
                       "ссылка обязательна)",
            "accessed": dt.date.today().isoformat(),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
        print(f"OK: {fn} ({len(raw) // 1024} КБ)")

    for years in SPANS:
        body = {"indicatorCode": "10101100003", "valuesFilter": {
            "years": years, "periodicities": [], "units": ["210"],
            "dimensionOrder": ["razrez_594", "priznak_536",
                               "priznak_391", "priznak_451"],
            "dimensionParams": {
                "razrez_594": ["699961"],          # Республика Беларусь
                "priznak_536": AGE_NODES,
                "priznak_391": SEX_NODES,
                "priznak_451": ["507552"],         # всего по местности
            },
            "simbolsAfterComma": 1}}
        raw = _fetch(f"{API}/indicatorValuesSearch", post=body)
        fn = f"dataportal_age_{years[0]}-{years[-1]}.json"
        (DEST / fn).write_bytes(raw)
        rows.append({
            "file": fn,
            "description": "Оценки Белстата на 1 января: 17 групп x пол, "
                           "Республика Беларусь (индикатор 10101100003)",
            "url": f"{API}/indicatorValuesSearch (10101100003)",
            "license": "Белстат, открытые данные",
            "accessed": dt.date.today().isoformat(),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
        print(f"OK: {fn} ({len(raw) // 1024} КБ)")

    with open(DEST / "registry.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"OK: {DEST / 'registry.csv'} ({len(rows)} записей)")


if __name__ == "__main__":
    main()
