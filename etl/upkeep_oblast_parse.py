"""INF-16 `upkeep`: разбор свободнотекстовых погодовых рядов школьной
статистики 6 областных агентов-исследователей (майлстоун 1,
`data/raw/fiscal_pilot_2026-08-01/oblast_school_stats_*.json`).

Каждая область прислала данные в собственном текстовом формате
("Name=V1", "Name: v1→v2→...→vN", "Name v1/v2/v3") - это не единая
структура, а результат независимого веб-поиска шести суб-агентов.
`parse_series()` ниже - единственный разбор этих форматов, используется
и гейтом G-5 (майлстоун 1, latest-value), и `etl/upkeep.py`
(service_network_overhang, полный ряд) - не дублируется в двух местах.
"""
from __future__ import annotations

import re


def parse_series(value_str: str, name: str) -> list[float]:
    """Числовой ряд для района `name` внутри свободнотекстового `value_str`.
    Поддерживает форматы "Name=V", "Name: v1→v2→...→vN", "Name v1/v2/v3".
    Возвращает [] если `name` не найден или формат не распознан."""
    esc = re.escape(name)
    # 1) "Name: v1→v2→...→vN" или "Name v1→v2→..." (цепочка стрелкой)
    m = re.search(esc + r'[:\s]+([\d,\.]+(?:\s*[→/]\s*[\d,\.]+)+)', value_str)
    if m:
        parts = re.split(r'[→/]', m.group(1))
        out = []
        for p in parts:
            p = p.strip().rstrip('.').replace(',', '.')
            try:
                out.append(float(p))
            except ValueError:
                return []
        return out
    # 2) "Name=V" или "Name: V" (одна точка)
    m = re.search(esc + r'[=:]\s*([\d,\.]+)', value_str)
    if m:
        try:
            return [float(m.group(1).strip().rstrip('.').replace(',', '.'))]
        except ValueError:
            return []
    return []


def parse_year_labels(year_field: str, n_points: int) -> list[int]:
    """Годы для `n_points` точек ряда из поля `year` фигуры (агенты
    формулируют его по-разному: "2000/01–2018/19 (19 учебных лет)",
    "2015, 2018, 2019, 2020, 2021, 2022, 2023 (на начало учебного года)").
    Возвращает список из `n_points` целых лет (год начала учебного года)."""
    # явный список годов через запятую
    explicit = re.findall(r'(?<!\d)(20\d{2})(?!\d)', year_field)
    explicit = [int(y) for y in explicit]
    if len(explicit) == n_points:
        return explicit
    # диапазон "2000/01-2018/19" -> первый/последний год-токен "20XX" в строке,
    # равномерно n_points точек между границами (не ищем пару подряд - между
    # "2000" и "2018" стоит "/01-", которое \D+ не может пересечь)
    all_years = re.findall(r'20\d{2}', year_field)
    if all_years:
        y0, y1 = int(all_years[0]), int(all_years[-1])
        if n_points > 1:
            step = (y1 - y0) / (n_points - 1)
            return [round(y0 + i * step) for i in range(n_points)]
        return [y1]
    return []
