"""Загрузка сырых источников в data/raw.

Файлы в data/raw закоммичены (vendored) для воспроизводимости даже при
недоступности источников; повторная загрузка: python -m etl.fetch --force
"""
from __future__ import annotations

import subprocess
import sys
import urllib.parse
from pathlib import Path

from .common import RAW

GB = "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/BLR"

SOURCES: dict[str, str] = {
    # geoBoundaries (CC BY 3.0): области и районы
    "gb-BLR-ADM1.geojson": f"{GB}/ADM1/geoBoundaries-BLR-ADM1_simplified.geojson",
    "gb-BLR-ADM2.geojson": f"{GB}/ADM2/geoBoundaries-BLR-ADM2_simplified.geojson",
    # pop-stat.mashke.org (сост. Tim Bespyatov, по данным переписей и Белстата)
    "ps_div.html": "https://pop-stat.mashke.org/belarus-division.htm",
    "ps_cities.html": "https://pop-stat.mashke.org/belarus-cities.htm",
    # Демоскоп Weekly: переписи СССР, городское/сельское по областям
    "demo59.html": "https://www.demoscope.ru/weekly/ssp/ussr59_reg1.php",
    "demo70.html": "https://www.demoscope.ru/weekly/ssp/ussr70_reg1.php",
    "demo79.html": "https://www.demoscope.ru/weekly/ssp/ussr79_reg1.php",
    "demo89.html": "https://www.demoscope.ru/weekly/ssp/sng89_reg1.php",
}

WIKIDATA_QUERY = """
SELECT ?item ?ru ?be ?coord ?adminLabel ?areaM2 WHERE {
  VALUES ?cls { wd:Q79324274 wd:Q79323854 wd:Q1549591 wd:Q91733160 wd:Q91733790 wd:Q7930989 wd:Q3957 }
  ?item wdt:P17 wd:Q184 ; wdt:P31 ?cls ; wdt:P625 ?coord .
  OPTIONAL { ?item rdfs:label ?ru . FILTER(LANG(?ru)='ru') }
  OPTIONAL { ?item rdfs:label ?be . FILTER(LANG(?be)='be') }
  OPTIONAL { ?item wdt:P131 ?admin . ?admin rdfs:label ?adminLabel . FILTER(LANG(?adminLabel)='ru') }
  OPTIONAL { ?item p:P2046/psn:P2046/wikibase:quantityAmount ?areaM2 . }
}
"""

OVERPASS_DRYBIN = (
    '[out:json][timeout:60];'
    'relation["boundary"="administrative"]["admin_level"="6"]'
    '["name"~"Дрыбінскі раён|Дрибинский район"];out geom;'
)

UA = "BY-maps-ETL/1.0 (open research project)"


def _curl(url: str, dest: Path, post: str | None = None) -> None:
    cmd = ["curl", "-sL", "--fail", "-A", UA, "-o", str(dest)]
    if post:
        cmd += ["-X", "POST", "--data-urlencode", f"data={post}"]
    cmd.append(url)
    subprocess.run(cmd, check=True)
    print(f"  {dest.name}: {dest.stat().st_size} байт")


def main(force: bool = False) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        dest = RAW / name
        if dest.exists() and not force:
            print(f"  {name}: уже есть (пропуск)")
            continue
        _curl(url, dest)
    wd = RAW / "wikidata_settlements.json"
    if force or not wd.exists():
        q = urllib.parse.urlencode({"query": WIKIDATA_QUERY, "format": "json"})
        _curl(f"https://query.wikidata.org/sparql?{q}", wd)
    dr = RAW / "drybin_osm.json"
    if force or not dr.exists():
        _curl("https://overpass-api.de/api/interpreter", dr, post=OVERPASS_DRYBIN)


if __name__ == "__main__":
    main(force="--force" in sys.argv)
