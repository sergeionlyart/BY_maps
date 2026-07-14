"""Генерация params/assumptions.yaml из канонического assumptions.json.

ТЗ требует человекочитаемый assumptions.yaml в пакете; код (stdlib,
без pyyaml) читает JSON. Этот скрипт держит YAML-зеркало в синхроне;
тест test_nightlights_v2.py сверяет оба файла через pyyaml.

Запуск: python -m etl.nightlights_yaml
"""
from __future__ import annotations

import json

import yaml

from .common import ROOT

PARAMS = ROOT / "artifacts" / "nightlights" / "params"


def main() -> None:
    data = json.loads((PARAMS / "assumptions.json").read_text())
    head = ("# ЗЕРКАЛО artifacts/nightlights/params/assumptions.json -\n"
            "# канонический файл JSON (пакет воспроизводится stdlib-only,\n"
            "# без pyyaml). Правки вносить в JSON и перегенерировать:\n"
            "#   python -m etl.nightlights_yaml\n")
    body = yaml.safe_dump(data, allow_unicode=True, sort_keys=False,
                          width=78)
    (PARAMS / "assumptions.yaml").write_text(head + body, encoding="utf-8")
    print("OK: assumptions.yaml")


if __name__ == "__main__":
    main()
