#!/usr/bin/env python3
"""Повторное получение крупных источников (полный режим воспроизведения).

Быстрый режим (code/run.sh) стартует от вендоренных зональных агрегатов и
внешних загрузок НЕ требует. Полный режим воссоздаёт агрегаты из первичных
растров и OSM:

  python3 code/fetch.py --check          # доступность источников (HEAD)
  python3 code/fetch.py --ghsl           # 40 тайлов GHS-BUILT-S (~0,8 ГБ)
  python3 code/fetch.py --osm            # снимок OSM Geofabrik (~0,35 ГБ)

Тайлы сохраняются в sources/external/ghsl/, PBF - в sources/external/osm/.
Каждый файл сверяется с sha256 из sources/raw/registry_ghsl.csv /
registry_osm.csv. ВНИМАНИЕ: belarus-latest.osm.pbf у Geofabrik - живой файл;
несовпадение sha256 для НОВОЙ загрузки не ошибка, а сигнал, что снимок
обновился после даты обращения (2026-07-16) - для него нужен новый релиз.

Дальнейшие шаги полного режима (требуют rasterio+numpy+scipy+pyosmium+PIL,
запускаются из корня репозитория BY_maps, см. README.md):
  python -m etl.urban_extract && python -m etl.urban_morph
  python -m etl.urban_light && python -m etl.urban_osm all
"""
import csv
import hashlib
import sys
import urllib.request
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
EXT = PKG / "sources" / "external"


def rows(name: str) -> list[dict]:
    with (PKG / "sources" / "raw" / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, dest: Path, want_sha: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and (not want_sha or sha256(dest) == want_sha):
        print(f"  есть: {dest.name}")
        return
    print(f"  скачиваю {url}")
    urllib.request.urlretrieve(url, dest)
    got = sha256(dest)
    if want_sha and got != want_sha:
        print(f"  ВНИМАНИЕ {dest.name}: sha256 {got[:12]}… != "
              f"заявленного {want_sha[:12]}… (источник обновился?)")
    else:
        print(f"  OK {dest.name}")


def check() -> None:
    import urllib.error
    for r in rows("registry_ghsl.csv")[:1] + rows("registry_osm.csv")[:1]:
        req = urllib.request.Request(r["url"], method="HEAD")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                print(f"  {r['id']}: HTTP {resp.status}, "
                      f"{resp.headers.get('Content-Length', '?')} байт")
        except urllib.error.URLError as e:
            print(f"  {r['id']}: НЕДОСТУПЕН ({e})")


def main() -> None:
    known = {"--check", "--ghsl", "--osm"}
    args = set(sys.argv[1:]) or {"--check"}
    unknown = args - known
    if unknown:
        print(f"неизвестные аргументы: {sorted(unknown)}; "
              f"допустимо: {sorted(known)}", file=sys.stderr)
        sys.exit(2)
    if "--check" in args:
        check()
    if "--ghsl" in args:
        for r in rows("registry_ghsl.csv"):
            fetch(r["url"], EXT / "ghsl" / (r["url"].rsplit("/", 1)[-1]),
                  r.get("sha256", ""))
    if "--osm" in args:
        for r in rows("registry_osm.csv"):
            fetch(r["url"], EXT / "osm" / "belarus-latest.osm.pbf",
                  r.get("sha256", ""))


if __name__ == "__main__":
    main()
