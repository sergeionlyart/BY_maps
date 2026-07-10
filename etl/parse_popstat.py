"""Парсинг таблиц pop-stat.mashke.org (составитель Tim Bespyatov, по данным
переписей и оценкам Белстата): районы/области 1970-2026 и города 1897-2026."""
from __future__ import annotations

import re
from pathlib import Path

from .common import parse_html_rows, popstat_num
from .registry import OBLASTS

CENSUS_RE = re.compile(r"^(\d{4})-\d{2}-\d{2}$")
ESTIMATE_RE = re.compile(r"^(\d{4})'$")

# типы точек данных
CENSUS, ESTIMATE = "census", "estimate"


def _parse_year_columns(header: list[str]) -> list[tuple[int, str] | None]:
    """Для каждой колонки: (год, тип) либо None для колонок с названиями."""
    cols: list[tuple[int, str] | None] = []
    for cell in header:
        m = CENSUS_RE.match(cell)
        if m:
            cols.append((int(m.group(1)), CENSUS))
            continue
        m = ESTIMATE_RE.match(cell)
        if m:
            cols.append((int(m.group(1)), ESTIMATE))
            continue
        cols.append(None)
    return cols


def _series_from_row(cells: list[str], cols) -> dict[int, tuple[int, str]]:
    """Серия {год: (население, тип)}. Перепись имеет приоритет над оценкой
    того же года."""
    series: dict[int, tuple[int, str]] = {}
    for cell, col in zip(cells, cols):
        if col is None:
            continue
        year, dtype = col
        val = popstat_num(cell)
        if val is None:
            continue
        if year in series and series[year][1] == CENSUS:
            continue
        if year in series and dtype == ESTIMATE:
            continue
        series[year] = (val, dtype)
    return series


def parse_division(path: Path) -> dict:
    """Таблица 'Division of Belarus': страна, области, г. Минск, города
    областного подчинения и районы (административные итоги).

    Возвращает:
      country: серия
      minsk: серия
      oblasts: {oblast_id: серия}
      raions: {be_name: (латинка, oblast_id, серия)}
      obl_cities: {be_name: (латинка, oblast_id, серия)}  # города обл. подчинения
    """
    rows = parse_html_rows(path)
    cols = _parse_year_columns(rows[0])
    be_to_oblast = {v[2]: k for k, v in OBLASTS.items()}

    out = {"country": None, "minsk": None, "oblasts": {}, "raions": {}, "obl_cities": {}}
    cur_oblast = None
    seen: set[str] = set()
    for cells in rows[1:]:
        if len(cells) < 3:
            continue
        be, lat = cells[0], cells[1]
        if not be or be.startswith("©") or "Bespyatov" in lat:
            continue
        if be in seen:  # дублированные заголовки-строки (г. Мінск)
            continue
        seen.add(be)
        series = _series_from_row(cells, cols)
        if be == "Беларусь":
            out["country"] = series
        elif be == "г. Мінск":
            out["minsk"] = series
        elif be in be_to_oblast:
            cur_oblast = be_to_oblast[be]
            out["oblasts"][cur_oblast] = series
        elif be.startswith("г. "):
            out["obl_cities"][be[3:]] = (lat[3:].strip(), cur_oblast, series)
        elif series and cur_oblast:
            out["raions"][be] = (lat, cur_oblast, series)
    return out


def parse_cities(path: Path) -> dict[str, dict]:
    """Таблица 'Cities & towns of Belarus': все города и городские посёлки.

    Возвращает {be_name: {lat, oblast_id, series, note}}.
    Заголовки областей - строки без чисел; 'г. Мінск' - отдельный блок.
    """
    rows = parse_html_rows(path)
    cols = _parse_year_columns(rows[0])
    be_to_oblast = {v[2]: k for k, v in OBLASTS.items()}

    cities: dict[str, dict] = {}
    cur_oblast = None
    for cells in rows[1:]:
        if len(cells) < 2:
            continue
        be, lat = cells[0], cells[1]
        if not be or be.startswith("©") or "Bespyatov" in lat:
            continue
        if be == "г. Мінск":
            cur_oblast = "BY-HM"
            continue
        if be in be_to_oblast:
            cur_oblast = be_to_oblast[be]
            continue
        series = _series_from_row(cells, cols)
        note = ""
        for cell in cells[2:]:
            if cell and popstat_num(cell) is None and "…" not in cell:
                note = cell
                break
        # города-дубли в разных областях не встречаются в этой таблице
        cities[be] = {"lat": lat, "oblast": cur_oblast, "series": series, "note": note}
    return cities
