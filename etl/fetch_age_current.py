"""Текущие возрастно-половые структуры (2019-2026) с открытого API
дата-портала Белстата (osids-public-api, индикатор 10101100003
«Численность населения на начало периода», на 1 января).

Выгружает страну + области + Минск x 5-летние группы x пол x тип местности
в data/raw/age_current/dataportal_age5_2019-2026.json (сырой ответ API).

Запуск: python -m etl.fetch_age_current
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .common import ROOT

RAW_DIR = ROOT / "data" / "raw" / "age_current"
API = "https://dataportal.belstat.gov.by/osids-public-api/indicator"
INDICATOR = "10101100003"
YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _curl_json(url: str, post: dict | None = None) -> dict:
    cmd = ["curl", "-s", "--fail", "-m", "180", "-A", UA]
    if post is not None:
        cmd += ["-X", "POST", "-H", "Content-Type: application/json",
                "--data", json.dumps(post, ensure_ascii=False)]
    cmd.append(url)
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    return json.loads(out)


def flatten(nodes: list, depth: int = 0, out: list | None = None) -> list:
    out = out if out is not None else []
    for n in nodes:
        out.append({"code": str(n["code"]), "name": n["name"], "depth": depth})
        flatten(n.get("childrens") or [], depth + 1, out)
    return out


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cfg = _curl_json(f"{API}/indicatorViewCfgGet/{INDICATOR}")
    dims = {d["code"]: flatten(d["nodes"]) for d in cfg["indicatorStructure"]["dimensions"]}

    terr = [t for t in dims["razrez_594"] if t["depth"] <= 1]      # страна + области + Минск
    age = [a for a in dims["priznak_536"] if a["depth"] == 1 and
           ("-" in a["name"] or "+" in a["name"] or "старше" in a["name"])]
    sex = [s for s in dims["priznak_391"]]                          # оба пола + м + ж
    loc = [x for x in dims["priznak_451"]]                          # всего + город + село

    body = {
        "indicatorCode": INDICATOR,
        "valuesFilter": {
            "years": YEARS,
            "periodicities": [],
            "units": ["210"],  # человек
            "dimensionOrder": ["razrez_594", "priznak_536", "priznak_391", "priznak_451"],
            "dimensionParams": {
                "razrez_594": [t["code"] for t in terr],
                "priznak_536": [a["code"] for a in age],
                "priznak_391": [s["code"] for s in sex],
                "priznak_451": [x["code"] for x in loc],
            },
            "simbolsAfterComma": 0,
        },
    }
    print(f"территорий: {len(terr)}, возрастных групп: {len(age)}, "
          f"пол: {len(sex)}, местность: {len(loc)}, годы: {YEARS}")
    data = _curl_json(f"{API}/indicatorValuesSearch", post=body)
    dest = RAW_DIR / "dataportal_age5_2019-2026.json"
    dest.write_text(json.dumps(data, ensure_ascii=False))
    # справочник измерений - рядом (для парсера)
    (RAW_DIR / "dataportal_dims.json").write_text(
        json.dumps(dims, ensure_ascii=False, indent=1))
    print(f"OK: {dest} ({dest.stat().st_size // 1024} КБ)")


if __name__ == "__main__":
    main()
