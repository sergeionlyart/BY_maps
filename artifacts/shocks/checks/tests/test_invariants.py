#!/usr/bin/env python3
"""Инварианты INF-09 (автономно, без pytest)."""
import csv
import hashlib
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PKG))


def main() -> None:
    reg = {r["notes"]: r for r in
           csv.DictReader(open(PKG / "sources" / "registry.csv"))}
    for f in (PKG / "data/raw/shocks").glob("*.json"):
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        assert reg[f.name]["sha256"] == h, f.name

    from etl.shocks import build
    b = build()

    # обрыв ВМВ
    s = b["series"]
    assert s["1940"] > s["1950"]
    assert 1_200_000 < s["1940"] - s["1950"] < 1_500_000
    assert s["1970"] < s["1940"] <= s["1979"]

    # события сорсены и упорядочены
    prev = 0
    for e in b["events"]:
        assert len(e.get("sources", [])) >= 1, e["title"]
        assert e["year"] >= prev
        prev = e["year"]

    # доли-1897 корректны, отсортированы
    cities = b["census1897"]
    for c in cities:
        assert 0 <= c["jewishShare"] <= 100
        assert abs(c["jewishShare"] - c["jewish"] / c["total"] * 100) < 0.1
    assert cities == sorted(cities, key=lambda c: -c["jewishShare"])
    assert cities[0]["jewishShare"] >= 70

    # Холокост-города сорсены
    for t in b["holocaust"]:
        assert len(t.get("sources", [])) >= 1, t["ru"]

    print("Инварианты выполнены: сырьё целостно, обрыв ВМВ на месте, "
          "события сорсены и упорядочены, доли-1897 корректны, "
          "Холокост-города сорсены.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"ИНВАРИАНТ НАРУШЕН: {e}", file=sys.stderr)
        sys.exit(1)
