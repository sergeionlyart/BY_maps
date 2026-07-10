"""Парсинг таблиц Демоскоп Weekly (итоги переписей СССР 1959-1989):
городское и сельское население по областям БССР.

Таблицы Демоскопа для всех четырёх переписей уже приведены к современному
составу областей (шесть областей, г. Минск отдельной строкой); сумма областей
и Минска в точности равна итогу по республике - это проверяется тестом.
"""
from __future__ import annotations

import re
from pathlib import Path

from .common import parse_html_rows, plain_num

OBL_RU = {
    "Брестская область": "BY-BR", "Витебская область": "BY-VI",
    "Гомельская область": "BY-HO", "Гродненская область": "BY-HR",
    "Минская область": "BY-MI", "Могилевская область": "BY-MA",
    "Могилёвская область": "BY-MA",
}


def _clean(name: str) -> str:
    return re.sub(r"[*.\s]+$", "", name).strip()


def _numbers(cells: list[str]) -> list[int]:
    return [n for n in (plain_num(c) for c in cells[1:]) if n is not None]


def parse_regions(path: Path, encoding: str = "windows-1251") -> dict:
    """Блок Белорусской ССР: {'country': (t,u,r), 'oblasts': {id: (t,u,r)},
    'minsk_city': (t, u, r)}. t/u/r - всё/городское/сельское население."""
    rows = parse_html_rows(path, encoding)
    in_by = False
    res = {"country": None, "oblasts": {}, "minsk_city": None}
    for cells in rows:
        name = _clean(cells[0])
        if not name:
            continue
        if "Белорусская ССР" in name:
            nums = _numbers(cells)
            res["country"] = (nums[0], nums[3], nums[6])
            in_by = True
            continue
        if not in_by:
            continue
        if name.endswith("ССР"):  # следующая республика
            break
        nums = _numbers(cells)
        if name in OBL_RU and len(nums) >= 7:
            res["oblasts"][OBL_RU[name]] = (nums[0], nums[3], nums[6])
        elif (re.search(r"г\.?\s*Минск|Минский горсовет", name) and len(nums) >= 4
              and res["minsk_city"] is None):
            # город республиканского подчинения: всё население городское.
            # В таблице 1989 г. есть и горсовет, и город - берём первую
            # строку (горсовет), согласованную с областными итогами.
            res["minsk_city"] = (nums[0], nums[0], 0)
    return res
