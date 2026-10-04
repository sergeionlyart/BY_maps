"""INF-18 `agglomeration`: выгрузка статистики занятости с дата-портала Белстата.

Четыре выгрузки, все с osids-public-api, перечислены в записке разведки
`docs/notes/employment_coverage_recon_2026-10-04.md` (раздел «Блокер»):

1. **10218000001** «Среднесписочная численность работников» — районный уровень,
   2010-2024. Это **рабочие места по месту работы** (организации отчитываются по
   территории размещения) — числитель `job_ratio`. Главная выгрузка: без неё
   INF-18 не считается, см. пререгистрацию `docs/preregistration/agglomeration-v0.1.md`.
2. **10218000001** — страна / области / г. Минск. Нужна для нормировки на страну
   (метрика 2 пререгистрации) и для гейта A-1.
3. **10102000017** «Численность занятого населения в среднем за период» —
   страна / области / г. Минск. Районный разрез уже завендорен в
   `data/raw/wages/`, но **г. Минск в нём отсутствует**: страна, области и Минск
   отчитываются в unit 211 (тыс. человек), а запрос одного unit молча отбрасывает
   другой уровень. Нужна для гейта A-2 и потому, что Минск — ядро исследования.
4. **10202100049** «Индекс физического объёма ВРП в сопоставимых ценах» — области.
   Задел под INF-19: публикуется реальный рост, собирать дефлятор не нужно.

Коды территорий не захардкожены: дерево измерений берётся из
`indicatorViewCfgGet/{код}` того же API (как в `etl.fetch_age_current`).
Единицы измерения не угадываются: запрашиваются обе (210 «человек» и
211 «тыс. человек»), фактически вернувшаяся фиксируется в registry.csv.

Лимит API — 10 лет на запрос, поэтому ряд 2010-2024 берётся двумя окнами.

Сырые ответы вендорятся в `data/raw/agglomeration/` с отдельным registry.csv.
Реестр обособлен намеренно: правка общего `data/raw/osm/registry.csv` ломает
байт-воспроизводимость опубликованного пакета INF-04 (прецедент — красный гейт
`by-maps-access-v1.0.0.zip` с 2026-07-28).

Запуск: python -m etl.agglomeration_fetch [--dry-run]

`--dry-run` печатает тела запросов и ничего не скачивает — им проверяется
сборка запросов там, где сеть до дата-портала закрыта.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from .common import ROOT

API = "https://dataportal.belstat.gov.by/osids-public-api/indicator"
SEARCH = f"{API}/indicatorValuesSearch"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DEST = ROOT / "data" / "raw" / "agglomeration"
LICENSE = "открытые данные Белстата"

TERR_DIM = "razrez_594"          # «Территория Республики Беларусь»
UNITS_PERSON = ["210", "211"]    # человек / тыс. человек — запрашиваем обе
UNITS_PERCENT = ["208"]          # процентов
SPANS = ([*range(2010, 2020)], [*range(2020, 2025)])   # лимит API: 10 лет на запрос
GRP_SPANS = ([*range(2011, 2021)], [*range(2021, 2025)])

EMPL_WORKPLACE = "10218000001"   # среднесписочная численность работников (место работы)
EMPL_RESIDENCE = "10102000017"   # занятое население (место жительства)
GRP_INDEX = "10202100049"        # индекс физобъёма ВРП


def _curl_json(url: str, post: dict | None = None) -> dict:
    cmd = ["curl", "-s", "--fail", "-m", "180", "-A", UA]
    if post is not None:
        cmd += ["-X", "POST", "-H", "Content-Type: application/json",
                "--data", json.dumps(post, ensure_ascii=False)]
    cmd.append(url)
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    return json.loads(out)


def _flatten(nodes: list, depth: int = 0, out: list | None = None) -> list:
    out = out if out is not None else []
    for n in nodes:
        out.append({"code": str(n["code"]), "name": n["name"], "depth": depth})
        _flatten(n.get("childrens") or [], depth + 1, out)
    return out


def territories(indicator: str) -> list[dict]:
    """Дерево территорий индикатора: depth 0 — страна, 1 — области и Минск,
    2 — районы и города областного подчинения."""
    cfg = _curl_json(f"{API}/indicatorViewCfgGet/{indicator}")
    dims = {d["code"]: _flatten(d["nodes"])
            for d in cfg["indicatorStructure"]["dimensions"]}
    if TERR_DIM not in dims:
        raise SystemExit(f"{indicator}: нет измерения {TERR_DIM}; "
                         f"есть {sorted(dims)}")
    (DEST / f"dims_{indicator}.json").write_text(
        json.dumps(dims, ensure_ascii=False, indent=1))
    return dims[TERR_DIM]


def body(indicator: str, years: list[int], codes: list[str],
         units: list[str], decimals: int) -> dict:
    return {
        "indicatorCode": indicator,
        "valuesFilter": {
            "years": years,
            "periodicities": [],
            "units": units,
            "dimensionOrder": [TERR_DIM],
            "dimensionParams": {TERR_DIM: codes},
            "simbolsAfterComma": decimals,
        },
    }


def _rows(data: dict) -> int:
    return len(data.get("tableRows") or [])


def pull(indicator: str, years: list[int], codes: list[str], units: list[str],
         decimals: int, fn: str, title: str, notes: str,
         dry: bool, registry: list[dict]) -> None:
    b = body(indicator, years, codes, units, decimals)
    if dry:
        print(f"\n--- {fn} ({len(codes)} территорий, {years[0]}-{years[-1]}) ---")
        print(json.dumps(b, ensure_ascii=False, indent=1))
        return
    data = _curl_json(SEARCH, post=b)
    if _rows(data) == 0:
        raise SystemExit(f"{fn}: API вернул 0 строк — проверьте unit и коды территорий "
                         f"(ловушка: при запросе одного unit другой уровень молча выпадает)")
    dst = DEST / fn
    payload = json.dumps(data, ensure_ascii=False)
    dst.write_text(payload)
    registry.append({
        "id": fn.removesuffix(".json"),
        "title": title,
        "url": SEARCH,
        "license": LICENSE,
        "accessed": dt.date.today().isoformat(),
        "sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "notes": f"{notes}; строк: {_rows(data)}; "
                 f"запрошенные unit: {','.join(units)}; "
                 f"tableName: {data.get('tableName', '')}",
    })
    print(f"OK  {fn}  строк {_rows(data):4d}  {dst.stat().st_size // 1024} КБ")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="напечатать тела запросов и выйти, ничего не скачивая")
    args = ap.parse_args(argv)
    DEST.mkdir(parents=True, exist_ok=True)
    registry: list[dict] = []

    if args.dry_run:
        # коды территорий без сети недоступны — показываем структуру запросов
        demo = ["<коды территорий из indicatorViewCfgGet>"]
        for ind, spans, units, dec in (
            (EMPL_WORKPLACE, SPANS, UNITS_PERSON, 1),
            (EMPL_RESIDENCE, SPANS, UNITS_PERSON, 1),
            (GRP_INDEX, GRP_SPANS, UNITS_PERCENT, 1),
        ):
            for years in spans:
                pull(ind, years, demo, units, dec, f"{ind}_{years[0]}-{years[-1]}.json",
                     "", "", True, registry)
        print("\n--dry-run: ничего не скачано")
        return

    # 1-2. рабочие места по месту работы: районный уровень и агрегаты
    terr = territories(EMPL_WORKPLACE)
    raions = [t["code"] for t in terr if t["depth"] == 2]
    aggs = [t["code"] for t in terr if t["depth"] <= 1]
    print(f"{EMPL_WORKPLACE}: территорий всего {len(terr)}, "
          f"районного уровня {len(raions)}, агрегатов {len(aggs)}")
    if len(raions) < 100:
        print(f"ВНИМАНИЕ: районного уровня всего {len(raions)} — индикатор может "
              f"не публиковаться по районам; см. раздел 4 пререгистрации", file=sys.stderr)
    for years in SPANS:
        pull(EMPL_WORKPLACE, years, raions, UNITS_PERSON, 1,
             f"empl_workplace_{EMPL_WORKPLACE}_{years[0]}-{years[-1]}.json",
             f"Дата-портал Белстата, индикатор {EMPL_WORKPLACE} «Среднесписочная "
             f"численность работников», районный уровень, {years[0]}-{years[-1]}",
             "рабочие места ПО МЕСТУ РАБОТЫ — числитель job_ratio (INF-18)",
             False, registry)
        pull(EMPL_WORKPLACE, years, aggs, UNITS_PERSON, 1,
             f"empl_workplace_agg_{EMPL_WORKPLACE}_{years[0]}-{years[-1]}.json",
             f"То же, страна / области / г. Минск, {years[0]}-{years[-1]}",
             "нормировка на страну (метрика 2) и гейт A-1", False, registry)

    # 3. занятые по месту жительства: агрегаты (районный разрез — в data/raw/wages/)
    terr_res = territories(EMPL_RESIDENCE)
    aggs_res = [t["code"] for t in terr_res if t["depth"] <= 1]
    for years in SPANS:
        pull(EMPL_RESIDENCE, years, aggs_res, UNITS_PERSON, 1,
             f"empl_residence_agg_{EMPL_RESIDENCE}_{years[0]}-{years[-1]}.json",
             f"Дата-портал Белстата, индикатор {EMPL_RESIDENCE} «Численность занятого "
             f"населения в среднем за период», страна / области / г. Минск, "
             f"{years[0]}-{years[-1]}",
             "г. Минск отсутствует в районном unit 210 — ядро исследования берётся "
             "отсюда; гейт A-2", False, registry)

    # 4. задел под INF-19: реальный рост ВРП
    terr_grp = territories(GRP_INDEX)
    aggs_grp = [t["code"] for t in terr_grp if t["depth"] <= 1]
    for years in GRP_SPANS:
        pull(GRP_INDEX, years, aggs_grp, UNITS_PERCENT, 1,
             f"grp_index_{GRP_INDEX}_{years[0]}-{years[-1]}.json",
             f"Дата-портал Белстата, индикатор {GRP_INDEX} «Индекс физического объёма "
             f"ВРП в сопоставимых ценах, в % к соответствующему периоду», области, "
             f"{years[0]}-{years[-1]}",
             "снимает риск дефлятора ВРП (INF-19)", False, registry)

    reg = DEST / "registry.csv"
    with open(reg, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "title", "url", "license",
                                          "accessed", "sha256", "notes"])
        w.writeheader()
        w.writerows(registry)
    print(f"\nреестр: {reg.relative_to(ROOT)} ({len(registry)} записей)")


if __name__ == "__main__":
    main()
