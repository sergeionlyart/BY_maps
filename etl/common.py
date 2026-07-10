"""Общие утилиты ETL: парсинг HTML-таблиц и чисел."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CURATED = RAW / "curated"
OUT = ROOT / "web" / "public" / "data"


def parse_html_rows(path: Path, encoding: str = "utf-8") -> list[list[str]]:
    """Разбирает простые HTML-таблицы (pop-stat, demoscope) в список строк-ячеек.

    Таблицы этих сайтов используют незакрытые <td>/<th> (HTML4), без colspan.
    """
    html = path.read_bytes().decode(encoding, errors="replace")
    rows: list[list[str]] = []
    for tr in re.split(r"<tr[^>]*>", html)[1:]:
        cells = []
        for td in re.split(r"<t[dh][^>]*>", tr)[1:]:
            txt = re.sub(r"<[^>]+>", "", td)
            txt = txt.replace("\xa0", " ").replace("&nbsp", "").strip()
            cells.append(txt)
        if cells:
            rows.append(cells)
    return rows


def popstat_num(cell: str) -> int | None:
    """Число из ячейки pop-stat: значения даны в тысячах с запятой-разделителем.

    '9002,338' -> 9_002_338; '53,2' -> 53_200; '…'/пусто/текст -> None.
    """
    cell = cell.strip()
    if not cell or not re.fullmatch(r"\d+(,\d+)?", cell):
        return None
    if "," in cell:
        whole, frac = cell.split(",")
        # дробная часть - тысячные доли тысячи, дополняем нулями до 3 знаков
        frac = (frac + "000")[:3]
        return int(whole) * 1000 + int(frac)
    return int(cell) * 1000


def plain_num(cell: str) -> int | None:
    """Целое число из ячейки demoscope ('1204376')."""
    cell = cell.replace(" ", "").strip()
    return int(cell) if re.fullmatch(r"\d+", cell) else None
