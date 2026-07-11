#!/usr/bin/env python3
"""Повторное получение сырого источника и сверка с завендоренной копией.

Скачивает актуальную версию таблицы городов pop-stat.mashke.org и сравнивает
её sha256 с зафиксированной в sources/registry.csv. Несовпадение НЕ ошибка:
источник живой и обновляется — это сигнал, что данные изменились после даты
обращения (2026-07-11), и для новой версии источника нужен новый релиз пакета.
"""
import csv
import hashlib
import sys
import urllib.request
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
URL = "https://pop-stat.mashke.org/belarus-cities.htm"


def main() -> None:
    with open(PKG / "sources" / "registry.csv", encoding="utf-8") as f:
        reg = {r["id"]: r for r in csv.DictReader(f)}
    pinned = reg["ps_cities"]["sha256"]

    vendored = PKG / "sources" / "raw" / "ps_cities.html"
    vendored_sha = hashlib.sha256(vendored.read_bytes()).hexdigest()
    print(f"завендоренная копия: sha256 {vendored_sha[:16]}… "
          f"({'совпадает' if vendored_sha == pinned else 'НЕ СОВПАДАЕТ'} с registry.csv)")

    req = urllib.request.Request(URL, headers={"User-Agent": "by-maps-artifact/1.0"})
    try:
        live = urllib.request.urlopen(req, timeout=60).read()
    except Exception as e:  # noqa: BLE001
        print(f"источник недоступен ({e}); используйте завендоренную копию", file=sys.stderr)
        sys.exit(2)
    live_sha = hashlib.sha256(live).hexdigest()
    if live_sha == pinned:
        print(f"живой источник: sha256 совпадает с зафиксированным ({live_sha[:16]}…)")
    else:
        print(f"живой источник ИЗМЕНИЛСЯ после даты обращения: sha256 {live_sha[:16]}… "
              f"(зафиксировано {pinned[:16]}…). Расчёт пакета остаётся валидным "
              f"для завендоренной копии.")


if __name__ == "__main__":
    main()
