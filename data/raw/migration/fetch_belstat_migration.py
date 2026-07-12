"""Выгрузка миграционных индикаторов дата-портала Белстата в scratchpad.

Индикаторы:
  10101300001 Число прибывших лиц
  10101300002 Число выбывших лиц
  10101300003 Миграционный прирост, убыль (-)

Годы в наличии: 1990-2019, 2024, 2025 (2020-2023 не опубликованы).
Лимит API ~10 лет на запрос -> чанки.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).parent
API = "https://dataportal.belstat.gov.by/osids-public-api/indicator"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

INDICATORS = {
    "10101300001": "arrivals",
    "10101300002": "departures",
    "10101300003": "net",
}

YEAR_CHUNKS = [
    list(range(1990, 2000)),
    list(range(2000, 2010)),
    list(range(2010, 2020)),
    [2024, 2025],
]

DIM_ORDER = ["razrez_594", "razrez_593", "priznak_455", "priznak_613",
             "priznak_536", "priznak_391", "priznak_451"]


def curl_json(url: str, post: dict | None = None) -> dict:
    cmd = ["curl", "-s", "--fail", "-m", "300", "-A", UA]
    if post is not None:
        cmd += ["-X", "POST", "-H", "Content-Type: application/json",
                "--data", json.dumps(post, ensure_ascii=False)]
    cmd.append(url)
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    return json.loads(out)


def flatten(nodes, depth=0, out=None):
    out = out if out is not None else []
    for n in nodes:
        out.append({"code": str(n["code"]), "name": n["name"], "depth": depth})
        flatten(n.get("childrens") or [], depth + 1, out)
    return out


def main() -> None:
    # dims одинаковые для всех трёх индикаторов - берём из cfg 10101300003
    cfg = json.load(open(HERE / "belstat_cfg_10101300003.json"))
    dims = {d["code"]: flatten(d["nodes"])
            for d in cfg["indicatorStructure"]["dimensions"]}
    (HERE / "belstat_migration_dims.json").write_text(
        json.dumps(dims, ensure_ascii=False, indent=1))

    terr_all = dims["razrez_594"]
    terr_top = [t["code"] for t in terr_all if t["depth"] <= 1]       # РБ+области+Минск (8)
    terr_raion = [t["code"] for t in terr_all if t["depth"] == 2]     # районы/города обл. (128)
    countries_all = [c["code"] for c in dims["razrez_593"]]           # всего+страны СНГ+группы
    country_total = ["261380"]                                        # Всего по странам
    flows_all = [f["code"] for f in dims["priznak_613"]]              # все 9 потоков
    flows_main = ["518463", "518464", "518465"]                       # всего/международная/внутриресп.
    edu_total = [e["code"] for e in dims["priznak_455"] if e["depth"] == 0]
    age_total = [a["code"] for a in dims["priznak_536"] if a["depth"] == 0]
    sex_total = [s["code"] for s in dims["priznak_391"] if s["depth"] == 0]
    loc_total = [x["code"] for x in dims["priznak_451"] if x["depth"] == 0]

    def body(ind, years, terr, countries, flows):
        return {
            "indicatorCode": ind,
            "valuesFilter": {
                "years": years,
                "periodicities": [],
                "units": ["210"],
                "dimensionOrder": DIM_ORDER,
                "dimensionParams": {
                    "razrez_594": terr,
                    "razrez_593": countries,
                    "priznak_455": edu_total,
                    "priznak_613": flows,
                    "priznak_536": age_total,
                    "priznak_391": sex_total,
                    "priznak_451": loc_total,
                },
                "simbolsAfterComma": 0,
            },
        }

    jobs = []
    for ind, tag in INDICATORS.items():
        for chunk in YEAR_CHUNKS:
            y0, y1 = chunk[0], chunk[-1]
            # 1) районный уровень: районы x 3 главных потока
            jobs.append((f"belstat_{tag}_raion_{y0}-{y1}.json",
                         body(ind, chunk, terr_raion, country_total, flows_main)))
            # 2) верхний уровень: РБ+области x все потоки x все страны
            jobs.append((f"belstat_{tag}_oblast_{y0}-{y1}.json",
                         body(ind, chunk, terr_top, countries_all, flows_all)))

    log = []
    for fname, b in jobs:
        dest = HERE / fname
        if dest.exists() and dest.stat().st_size > 200:
            print(f"skip {fname}")
            continue
        t0 = time.time()
        try:
            data = curl_json(f"{API}/indicatorValuesSearch", post=b)
            dest.write_text(json.dumps(data, ensure_ascii=False))
            nvals = len(data.get("dataList") or data.get("values") or []) \
                if isinstance(data, dict) else len(data)
            msg = f"OK {fname}: {dest.stat().st_size//1024} KB, top-level={type(data).__name__}, n={nvals}, {time.time()-t0:.1f}s"
        except subprocess.CalledProcessError as e:
            msg = f"FAIL {fname}: {e.stderr[:200] if e.stderr else e}"
        print(msg)
        log.append({"file": fname, "request_body": b, "result": msg})
        time.sleep(1.5)

    (HERE / "belstat_request_log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
