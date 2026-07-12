"""INF-05 `migration`: внутренняя и внешняя миграция.

Внутренняя панель: «миграционная лестница» село -> райцентр -> облцентр ->
Минск (ярусы расселения по рядам проекта, 1959-2026) и межобластная
матрица переписи-2019 (куб F602: накопленная, lifetime - используется
как карта направлений, НЕ как годовой поток).

Внешняя панель: страны назначения по зеркальной статистике (Eurostat
migr_resvalid по странам + национальные источники), интервал
незарегистрированного оттока 2020-2026 из WP-F3 (etl/mirror.py) и
хронология волны с точечными оценками из публичных источников.

Ограничение спеки INF-05: зеркальная статистика не даёт региона
происхождения - по районам НЕ раскладывается.

Запуск: python -m etl.migration -> web/public/data/migration.json
"""
from __future__ import annotations

import csv
import json

from .common import ROOT, OUT
from .census_age import RAION_RU2ID, _e
from .mirror import _jsonstat_series, outflow_interval, TIME_PROFILE
from .wages import CITY_RU2ID, OBL_RU2ID

CURATED = ROOT / "data" / "curated"
RAW_MIG = ROOT / "data" / "raw" / "migration"
VERSION = "1.0.0"

OBL_CENTERS = {"c-brest", "c-viciebsk", "c-homiel", "c-hrodna", "c-mahilou"}

# годы «лестницы»: переписи + текущая оценка (общая сетка всех ярусов)
LADDER_YEARS = [1959, 1970, 1979, 1989, 1999, 2009, 2019, 2026]

OBL_RU = {"BY-BR": "Брестская", "BY-VI": "Витебская", "BY-HO": "Гомельская",
          "BY-HR": "Гродненская", "BY-MI": "Минская", "BY-MA": "Могилёвская",
          "BY-HM": "г. Минск"}


def _pop(v: dict, year: int) -> float | None:
    p = v["pop"].get(str(year))
    return float(p[0]) if p else None


def ladder(data: dict) -> dict:
    """Ярусы расселения по годам: Минск / облцентры / райцентры /
    прочие города и пгт / село. Село = страна минус учтённые города
    (малые пгт без ранних данных чуть завышают село до 1989 - в note)."""
    raion_centers = set()
    for v in data.values():
        if v["level"] == "raion":
            raion_centers.update(v.get("center") or [])
    raion_centers -= OBL_CENTERS | {"c-minsk"}

    tiers = {"minsk": [], "oblCenters": [], "raionCenters": [],
             "otherUrban": [], "rural": []}
    cities = [v for v in data.values() if v["level"] == "city"]
    for y in LADDER_YEARS:
        total = _pop(data["BY"], y)
        minsk = _pop(data["c-minsk"], y)
        oblc = sum(_pop(data[c], y) or 0 for c in OBL_CENTERS)
        rc = sum(_pop(c, y) or 0 for c in cities
                 if c["id"] in raion_centers)
        urban = sum(_pop(c, y) or 0 for c in cities)
        other = urban - minsk - oblc - rc
        tiers["minsk"].append(round(minsk))
        tiers["oblCenters"].append(round(oblc))
        tiers["raionCenters"].append(round(rc))
        tiers["otherUrban"].append(round(other))
        tiers["rural"].append(round(total - urban))
    return {"years": LADDER_YEARS, "tiers": tiers,
            "nRaionCenters": len(raion_centers)}


def interoblast_matrix() -> dict:
    """Межобластная матрица F602 (перепись-2019, накопленная):
    42 направленных потока без диагонали, суммарно по возрастам."""
    flows: dict[tuple[str, str], int] = {}
    for r in csv.DictReader(open(CURATED / "migration_internal.csv")):
        if r["year"] != "2019" or r["origin_oblast"] == r["dest_oblast"]:
            continue
        key = (r["origin_oblast"], r["dest_oblast"])
        flows[key] = flows.get(key, 0) + int(r["migrants"])
    out = [{"from": a, "to": b, "n": n}
           for (a, b), n in sorted(flows.items(), key=lambda kv: -kv[1])]
    net = {}
    for f in out:
        net[f["to"]] = net.get(f["to"], 0) + f["n"]
        net[f["from"]] = net.get(f["from"], 0) - f["n"]
    return {"flows": out, "net": net, "total": sum(f["n"] for f in out),
            "oblNames": OBL_RU}


# ------------------------------------------------- Белстат, дата-портал

def _belstat_series(prefix: str, terr_of) -> dict[str, dict[int, int]]:
    """{terr_id: {год: значение}} из чанков ответов дата-портала.

    terr_of(name) -> id | None; поток - только «Всего по всем потокам
    миграции» (на районном уровне других нет)."""
    out: dict[str, dict[int, int]] = {}
    for f in sorted(RAW_MIG.glob(f"{prefix}_*.json")):
        d = json.loads(f.read_text())
        years = [int(y) for y in d["tableHeader"][0]]
        ndim = len(d["tableHeaderDimColumns"])
        for row in d["tableRows"]:
            if row[3]["value"] != "Всего по всем потокам миграции":
                continue
            tid = terr_of(row[0]["value"])
            if not tid:
                continue
            for i, y in enumerate(years):
                cell = row[ndim + i]["value"] if ndim + i < len(row) else None
                if cell not in (None, "", "-"):
                    out.setdefault(tid, {})[y] = int(
                        str(cell).replace(" ", "").replace(" ", ""))
    return out


def _raion_terr(name: str):
    if name in CITY_RU2ID:
        return CITY_RU2ID[name]
    return RAION_RU2ID.get(_e(name))


def raion_net() -> dict[str, dict[int, int]]:
    """Сальдо миграции 128 территорий (118 районов + 10 городов
    областного подчинения), 1994-2019 + 2024-2025 (2020-2023 Белстат
    не публиковал)."""
    return _belstat_series("belstat_net_raion", _raion_terr)


def oblast_flows() -> dict[str, dict[str, dict[int, int]]]:
    """{obl_id: {поток: {год: сальдо}}} - РБ, области, Минск; 9 потоков."""
    out: dict[str, dict[str, dict[int, int]]] = {}
    for f in sorted(RAW_MIG.glob("belstat_net_oblast_*.json")):
        d = json.loads(f.read_text())
        years = [int(y) for y in d["tableHeader"][0]]
        ndim = len(d["tableHeaderDimColumns"])
        for row in d["tableRows"]:
            tid = OBL_RU2ID.get(row[0]["value"])
            if not tid or row[1]["value"] != "Всего по странам":
                continue
            flow = row[3]["value"]
            for i, y in enumerate(years):
                cell = row[ndim + i]["value"] if ndim + i < len(row) else None
                if cell not in (None, "", "-"):
                    out.setdefault(tid, {}).setdefault(flow, {})[y] = int(
                        str(cell).replace(" ", "").replace(" ", ""))
    return out


# --------------------------------------------------- внешняя панель

# имена стран для UI
GEO_RU = {"PL": "Польша", "LT": "Литва", "DE": "Германия", "CZ": "Чехия",
          "LV": "Латвия", "EE": "Эстония", "IT": "Италия", "ES": "Испания",
          "NL": "Нидерланды", "FR": "Франция", "SE": "Швеция",
          "FI": "Финляндия", "AT": "Австрия", "BE": "Бельгия",
          "BG": "Болгария", "CY": "Кипр", "SK": "Словакия",
          "PT": "Португалия", "IE": "Ирландия", "NO": "Норвегия",
          "CH": "Швейцария", "EL": "Греция", "HU": "Венгрия",
          "RO": "Румыния", "HR": "Хорватия", "SI": "Словения",
          "DK": "Дания", "LU": "Люксембург", "MT": "Мальта",
          "IS": "Исландия", "EU27_2020": "ЕС-27"}

# точечные оценки волны 2020+ (все снапшоты - data/raw/migration/,
# реестр с sha256 и датами обращения - registry.csv; дата обращения
# ко всем источникам 2026-07-12)
ESTIMATES = [
    {"low": 100_000, "high": 500_000, "year": 2025,
     "label": "BEROC: диапазон оценок уехавших с 2020",
     "who": "А. Лузгина, BEROC («Банк идей»)", "published": "2025-09-19",
     "src": "zerkalo.io", "snap": "snap_zerkalo_beroc_100-500k.html"},
    {"low": 350_000, "high": 350_000, "year": 2023,
     "label": "«350 тысяч уехали» - оценка, озвученная в Минске",
     "who": "замминистра МВД, октябрь 2023", "published": "2023-10-25",
     "src": "zerkalo.io", "snap": "snap_zerkalo_350k_minsk.html"},
    {"low": 500_000, "high": 600_000, "year": 2024,
     "label": "Социолог Г. Коршунов (ЦНИ): 500-600 тыс.",
     "who": "Г. Коршунов, Центр новых идей", "published": "2024-05-09",
     "src": "pap.pl", "snap": "snap_dron_korshunov_mirror.html"},
    {"low": 386_834, "high": 386_834, "year": 2024,
     "label": "Действующие ВНЖ граждан РБ в ЕС (жёсткий пол)",
     "who": "Eurostat migr_resvalid, сток на 31.12.2024",
     "published": "2026-05-01", "src": "Eurostat / nashaniva.com",
     "snap": "snap_nashaniva_eurostat_386k.html"},
]

# не-ЕС направления: лучшая доступная точка (сток, не поток)
NON_EU = [
    {"geo": "GE", "name": "Грузия", "stock": 12_808, "asof": "01.01.2025",
     "src": "МВД Грузии (по udf.name/Wayback); перепись-2025 нашла лишь 4 473 гражданина BY - учёт стока спорен",
     "snap": "snap_udf_georgia_vnzh_3738_wayback.html"},
    {"geo": "RS", "name": "Сербия", "stock": 1_159, "asof": "31.12.2024",
     "src": "МВД Сербии / IOM 2025 (статус ≥1 года или ПМЖ); текст извлечён из PDF",
     "snap": "serbia_iom_text.txt"},
    {"geo": "US", "name": "США", "stock": 10_350, "asof": "FY2020-2024",
     "src": "DHS Yearbook 2024: green cards по стране рождения (сумма за 5 лет)",
     "snap": "snap_dhs_yearbook2024_table3.html"},
]

# аннотации хронологии
EVENTS = [
    {"year": 2020, "label": "август: выборы и протесты"},
    {"year": 2021, "label": "май: Ryanair; ноябрь: закрытие Кузницы"},
    {"year": 2022, "label": "февраль: война; пик первичных ВНЖ ЕС"},
    {"year": 2023, "label": "закрытия переходов Литвой/Латвией"},
    {"year": 2025, "label": "ноябрь: реоткрытие Кузницы и Бобровников"},
]


def external() -> dict:
    """Страны назначения, первичные ВНЖ, интервал WP-F3, хронология."""
    stocks = _jsonstat_series(RAW_MIG / "eurostat_migr_resvalid_BY.json")
    first = _jsonstat_series(RAW_MIG / "eurostat_migr_resfirst_BY.json")

    countries = []
    for geo, ser in stocks.items():
        if geo == "EU27_2020" or not ser:
            continue
        last_y = max(ser)
        if ser[last_y] < 1000 and ser.get(2019, 0) < 1000:
            continue
        countries.append({
            "geo": geo, "name": GEO_RU.get(geo, geo),
            "s2019": ser.get(2019), "latest": ser[last_y], "latestYear": last_y,
        })
    countries.sort(key=lambda c: -c["latest"])

    eu = stocks["EU27_2020"]
    iv = outflow_interval()
    interval = {"low": iv["low"], "mid": iv["mid"], "high": iv["high"]}

    # кумулятивная траектория неучтённого оттока по профилю WP-F3
    years = list(range(2020, 2027))
    cum = {k: [] for k in ("low", "mid", "high")}
    acc = 0.0
    for y in years:
        acc += TIME_PROFILE.get(y, 0.0)
        for k in cum:
            cum[k].append(round(interval[k] * acc))

    return {
        "countries": countries,
        "euStock": {str(y): v for y, v in sorted(eu.items())},
        "euFirst": {str(y): v for y, v in
                    sorted(first.get("EU27_2020", {}).items())},
        "nonEu": NON_EU,
        "interval": interval,
        "timeline": {"years": years, **cum},
        "estimates": ESTIMATES,
        "events": EVENTS,
        "accessed": "2026-07-12",
    }


def build() -> dict:
    data = json.loads((OUT / "data.json").read_text())["territories"]
    net = raion_net()
    flows = oblast_flows()

    # ставка сальдо на 1000 жителей: средняя 2015-2019 и 2024-2025
    rates = {}
    for tid, ser in net.items():
        v = data.get(tid)
        if not v:
            continue
        def rate(years):
            vals = [ser[y] for y in years if y in ser]
            pops = [float(v["pop"][str(y)][0]) for y in years
                    if y in ser and str(y) in v["pop"]]
            if not vals or not pops:
                return None
            return round(sum(vals) / len(vals) / (sum(pops) / len(pops)) * 1000, 2)
        rates[tid] = {
            "rate1519": rate(range(2015, 2020)),
            "rate2425": rate((2024, 2025)),
            "net": {str(y): n for y, n in sorted(ser.items())},
        }

    intl = {t: f.get("Международная миграция", {}) for t, f in flows.items()}
    return {
        "ladder": ladder(data),
        "matrix": interoblast_matrix(),
        "raions": rates,
        "intlOfficial": {t: {str(y): v for y, v in sorted(s.items())}
                         for t, s in intl.items()},
        "external": external(),
    }


def main() -> None:
    b = build()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "migration.json").write_text(json.dumps(
        {"version": VERSION, **b}, ensure_ascii=False))

    ext = b["external"]
    print(f"OK: migration.json (районных рядов {len(b['raions'])}, "
          f"стран {len(ext['countries'])})")
    print(f"  ЕС сток: 2019 {ext['euStock']['2019']:,} -> "
          f"2024 {ext['euStock']['2024']:,}")
    print(f"  интервал WP-F3: {ext['interval']['low']:,} / "
          f"{ext['interval']['mid']:,} / {ext['interval']['high']:,}")
    top = b["matrix"]["flows"][0]
    print(f"  крупнейший внутренний поток: {top['from']} -> {top['to']} "
          f"{top['n']:,} (накопленный, F602)")
    l = b["ladder"]["tiers"]
    print(f"  лестница 1959->2026: село {l['rural'][0]/1e6:.2f} -> "
          f"{l['rural'][-1]/1e6:.2f} млн; Минск {l['minsk'][0]/1e6:.2f} -> "
          f"{l['minsk'][-1]/1e6:.2f} млн")


if __name__ == "__main__":
    main()
