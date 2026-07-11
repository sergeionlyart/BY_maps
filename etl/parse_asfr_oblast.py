"""ASFR по областям и Минску из «Демографического ежегодника РБ 2019»
(табл. 4.10, стр. 275+): возрастные коэффициенты рождаемости на 1000 женщин,
7 групп (<20, 20-24, ..., 45-49), ряды 1969/70-2018.

Выход: data/curated/fertility_oblast.csv (year, oblast, age_group, asfr)
и колонка tfr = 5 * сумма(ASFR) / 1000.

Запуск: python -m etl.parse_asfr_oblast
"""
from __future__ import annotations

import csv
import re

import pdfplumber

from .common import ROOT, RAW

CURATED = ROOT / "data" / "curated"
PDF = RAW / "fertility_mortality" / "demyearbook2019.pdf"

OBL_MAP = {
    "Брестская область": "BY-BR", "Витебская область": "BY-VI",
    "Гомельская область": "BY-HO", "Гродненская область": "BY-HR",
    "г.Минск": "BY-HM", "г. Минск": "BY-HM",
    "Минская область": "BY-MI", "Могилевская область": "BY-MA",
}
AGES = ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49"]

ROW_RE = re.compile(
    r"^(?:(\d{4})\s*[–-]\s*\d{4}|(\d{4}))\s+"      # год или интервал лет
    r"([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s*$")


def parse() -> list[dict]:
    rows = []
    cur_obl = None
    with pdfplumber.open(PDF) as pdf:
        for pageno in range(270, 290):
            text = pdf.pages[pageno].extract_text() or ""
            if "коэффициенты рождаемости" not in text and cur_obl is None:
                continue
            for line in text.split("\n"):
                line = line.strip()
                for name, oid in OBL_MAP.items():
                    if line.startswith(name):
                        cur_obl = oid
                m = ROW_RE.match(line)
                if m and cur_obl:
                    year = int(m.group(1) or m.group(2))
                    vals = [float(v.replace(",", ".")) for v in m.groups()[2:10]]
                    asfr7, total = vals[:7], vals[7]
                    tfr = round(5 * sum(asfr7) / 1000, 3)
                    for age, a in zip(AGES, asfr7):
                        rows.append({"year": year, "oblast": cur_obl,
                                     "age_group": age, "asfr": a, "tfr": tfr})
            if cur_obl == "BY-MA" and "45-49" in text and pageno > 275:
                # Могилёвская - последняя; дочитываем страницу и выходим
                if any(r["oblast"] == "BY-MA" and r["year"] >= 2018 for r in rows):
                    break
    return rows


def main() -> None:
    rows = parse()
    CURATED.mkdir(parents=True, exist_ok=True)
    rows.sort(key=lambda r: (r["oblast"], r["year"], AGES.index(r["age_group"])))
    with open(CURATED / "fertility_oblast.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["year", "oblast", "age_group", "asfr", "tfr"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    obls = {r["oblast"] for r in rows}
    years = sorted({r["year"] for r in rows})
    print(f"OK: fertility_oblast.csv: {len(rows)} строк, {len(obls)} областей, "
          f"{years[0]}-{years[-1]}")
    for o in sorted(obls):
        t18 = [r["tfr"] for r in rows if r["oblast"] == o and r["year"] == 2018]
        print(f"  {o}: СКР-2018 = {t18[0] if t18 else 'нет'}")


if __name__ == "__main__":
    main()
