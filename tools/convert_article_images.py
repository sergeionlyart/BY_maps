#!/usr/bin/env python3
"""Конвертация иллюстраций статьи «Полотно» (build/assets/grid/*.png,
1920x1080) в WebP для сайта: ширина 1600px, бюджет 200 КБ на кадр.
Качество подбирается по кадру (бинарный поиск), чтобы не терять деталь на
кадрах с текстом там, где бюджет позволяет, и не превышать его там, где нет.

Запуск:
    python tools/convert_article_images.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "build" / "assets" / "grid"
OUT = ROOT / "web" / "public" / "content" / "img" / "grid"
TARGET_W = 1600
BUDGET_BYTES = 200 * 1024


def encode_under_budget(img: Image.Image, path: Path) -> tuple[int, int]:
    """Бинарный поиск по quality от 40 до 92, пока размер не влезет в бюджет
    (или пока не дойдём до нижней границы — тогда сохраняем лучший вариант)."""
    lo, hi = 40, 92
    best_q = lo
    best_size = None
    while lo <= hi:
        q = (lo + hi) // 2
        img.save(path, format="WEBP", quality=q, method=6, lossless=False)
        size = path.stat().st_size
        if size <= BUDGET_BYTES:
            best_q, best_size = q, size
            lo = q + 1
        else:
            hi = q - 1
    if best_size is None:
        # даже quality=40 не влезает - сохраняем его и предупреждаем в отчёте
        img.save(path, format="WEBP", quality=lo, method=6, lossless=False)
        best_q, best_size = lo, path.stat().st_size
    else:
        img.save(path, format="WEBP", quality=best_q, method=6, lossless=False)
    return best_q, best_size


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pngs = sorted(SRC.glob("*.png"))
    total = 0
    over_budget = []
    for p in pngs:
        img = Image.open(p).convert("RGB")
        w, h = img.size
        target_h = round(h * TARGET_W / w)
        img = img.resize((TARGET_W, target_h), Image.LANCZOS)
        out_path = OUT / f"{p.stem}.webp"
        q, size = encode_under_budget(img, out_path)
        total += size
        flag = ""
        if size > BUDGET_BYTES:
            over_budget.append(p.stem)
            flag = "  ПРЕВЫШЕН БЮДЖЕТ"
        print(f"{p.stem:16} q={q:3} {size / 1024:6.1f} КБ  ({TARGET_W}x{target_h}){flag}")
    print(f"\nВсего: {len(pngs)} файлов, {total / 1024 / 1024:.2f} МБ")
    if over_budget:
        print(f"Превысили бюджет 200 КБ: {', '.join(over_budget)}")


if __name__ == "__main__":
    main()
