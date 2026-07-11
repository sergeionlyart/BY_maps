"""Мини-версия etl/common.py для автономного пакета: ROOT = корень пакета."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CURATED = ROOT / "data" / "curated"
OUT = ROOT / "web" / "public" / "data"
