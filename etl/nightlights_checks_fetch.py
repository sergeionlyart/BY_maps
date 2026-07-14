#!/usr/bin/env python3
"""Загрузка внешней статистики для проверки кандидатов H1-H3 (R4).

Дата-портал Белстата (osids-public-api), два индикатора:
  10206000003 - индекс промышленного производства, % к предыдущему году
                (районный разрез: кейсовые территории + страна/области);
  10207000004 - производство электроэнергии, млн кВт·ч
                (области x категории энергоисточников, включая
                «Атомная электростанция» - вклад БелАЭС для H3).

Занятость (10102000017) и зарплата (10218000003) по районам уже
завендорены в data/raw/wages/; миграционное сальдо районов - в
web/public/data/migration.json (панель INF-05).

Сырые ответы вендорятся в data/raw/nightlights/checks/ (+ registry.csv
с URL и sha256). Расчёт - etl/nightlights_checks.py (stdlib).

Запуск: python -m etl.nightlights_checks_fetch
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

from .common import ROOT

API = "https://dataportal.belstat.gov.by/osids-public-api/indicator"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DEST = ROOT / "data" / "raw" / "nightlights" / "checks"

# территории 10206000003 (razrez_594): кейсовые + агрегаты
IPI_TERR = {
    "699961": "Республика Беларусь",
    "919070": "Гродненская область",
    "919071": "г. Минск",
    "919072": "Минская область",
    "919158": "Островецкий",
    "919187": "Минский",
    "919193": "Смолевичский",
    "919200": "г. Жодино",
}
# лимит API - 10 лет на запрос: два окна (как в data/raw/wages/).
# районные значения публикуются с 2016 и по 2021 включительно
IPI_SPANS = [list(range(2012, 2021)), list(range(2021, 2026))]

ELEC_TERR = {
    "699961": "Республика Беларусь",
    "919070": "Гродненская область",
    "919071": "г. Минск",
    "919072": "Минская область",
}
ELEC_CATS = {   # priznak_414
    "517474": "Все категории энергоисточников",
    "517567": "Атомная электростанция",
    "517478": "Установки, работающие на базе сжигания топлива",
}
ELEC_SPANS = [list(range(2012, 2020)), list(range(2020, 2026))]


def _curl_json(url: str, post: dict | None = None) -> dict:
    cmd = ["curl", "-s", "--fail", "-m", "180", "-A", UA]
    if post is not None:
        cmd += ["-X", "POST", "-H", "Content-Type: application/json",
                "--data", json.dumps(post, ensure_ascii=False)]
    cmd.append(url)
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    return json.loads(out)


def fetch_ipi() -> list[Path]:
    out = []
    for years in IPI_SPANS:
        body = {
            "indicatorCode": "10206000003",
            "valuesFilter": {
                "years": years,
                "periodicities": [],
                "units": ["208"],   # процентов
                # ЛОВУШКА API: неиспользуемые классификации передаются
                # ПУСТЫМИ массивами (узлы-«всего» дают 0 строк); агрегат
                # «Промышленность» - код 1820 (перехвачено из UI портала)
                "dimensionOrder": ["razrez_594", "priznak_10261",
                                   "razrez_182", "razrez_614"],
                "dimensionParams": {
                    "razrez_594": list(IPI_TERR),
                    "priznak_10261": ["1820"],     # Промышленность (итог)
                    "razrez_182": [],
                    "razrez_614": [],
                },
                "simbolsAfterComma": 1,
            },
        }
        data = _curl_json(f"{API}/indicatorValuesSearch", post=body)
        dst = DEST / f"ipi_10206000003_{years[0]}-{years[-1]}.json"
        dst.write_text(json.dumps(data, ensure_ascii=False))
        out.append(dst)
    return out


def fetch_elec() -> list[Path]:
    out = []
    for years in ELEC_SPANS:
        body = {
            "indicatorCode": "10207000004",
            "valuesFilter": {
                "years": years,
                "periodicities": [],
                "units": ["403"],   # млн кВт·ч
                "dimensionOrder": ["razrez_594", "priznak_414"],
                "dimensionParams": {
                    "razrez_594": list(ELEC_TERR),
                    "priznak_414": list(ELEC_CATS),
                },
                "simbolsAfterComma": 1,
            },
        }
        data = _curl_json(f"{API}/indicatorValuesSearch", post=body)
        dst = DEST / f"elec_10207000004_{years[0]}-{years[-1]}.json"
        dst.write_text(json.dumps(data, ensure_ascii=False))
        out.append(dst)
    return out


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, fn, url in [
        ("индекс промышленного производства, % к предыдущему году",
         fetch_ipi, f"{API}/indicatorValuesSearch (10206000003)"),
        ("производство электроэнергии по областям и категориям, млн кВт·ч",
         fetch_elec, f"{API}/indicatorValuesSearch (10207000004)"),
    ]:
        for dst in fn():
            sha = hashlib.sha256(dst.read_bytes()).hexdigest()
            rows.append({
                "file": dst.name, "description": name, "url": url,
                "license": "Белстат, открытые данные",
                "accessed": dt.date.today().isoformat(), "sha256": sha,
            })
            print(f"OK: {dst.name} ({dst.stat().st_size // 1024} КБ)")
    with open(DEST / "registry.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"OK: {DEST / 'registry.csv'}")


if __name__ == "__main__":
    main()
