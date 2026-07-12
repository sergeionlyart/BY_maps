"""INF-09 `shocks`: демографические шоки XX века.

Вопрос: какой вклад в сегодняшнюю карту внесли Первая мировая и
беженство 1915, граница 1921-1939, репрессии, Вторая мировая, Холокост
(исчезновение местечка как типа поселения), «неперспективные деревни»,
распад СССР?

Данные: национальный ряд населения проекта (1897-2026, включая обрыв
1940->1950); событийные аннотации с источниками
(data/raw/shocks/events.json); перепись-1897 по родному языку по городам
(Демоскоп; доля идиш = «местечко»); города «до/после» Холокоста
(доля евреев 1897 + население 1939/1959).

ВАЖНО про Холокост: сопоставление 1939->1959 по ОБЩЕМУ населению
вводит в заблуждение (многие города восстановились иным, нееврейским
населением). Настоящий шок - КОМПОЗИЦИОННЫЙ: еврейское большинство
местечек (55-90% в 1897) было уничтожено в 1941-1943, и местечко как
тип поселения исчезло. Публикуем долю-1897 как меру утраченного.

Запуск: python -m etl.shocks -> web/public/data/shocks.json
"""
from __future__ import annotations

import json

from .common import ROOT, OUT

RAW = ROOT / "data" / "raw" / "shocks"
VERSION = "1.0.0"

# годы национального ряда, релевантные шокам
SERIES_YEARS = [1897, 1913, 1940, 1950, 1959, 1970, 1979, 1989,
                1999, 2009, 2019, 2026]


def _by_series(data: dict) -> dict[str, int]:
    by = data["BY"]["pop"]
    return {str(y): int(by[str(y)][0]) for y in SERIES_YEARS if str(y) in by}


def _resolve(city_ru: str, data: dict, name2id: dict) -> str | None:
    return name2id.get(city_ru.strip())


def census_1897(data: dict, name2id: dict) -> list[dict]:
    """Города переписи-1897 с долей евреев (идиш); сортировка по доле."""
    raw = json.loads((RAW / "census_lang.json").read_text())
    out = []
    for c in raw.get("cities", []):
        total = c.get("total_1897") or 0
        jew = c.get("jewish") or 0
        if not total:
            continue
        cid = c.get("city_id") or _resolve(c["city_ru"], data, name2id)
        v = data.get(cid) if cid else None
        out.append({
            "id": cid, "ru": c["city_ru"], "total": total, "jewish": jew,
            "jewishShare": round(jew / total * 100, 1),
            "belarusian": c.get("belarusian"), "russian": c.get("russian"),
            "polish": c.get("polish"),
            "lat": v.get("lat") if v else None,
            "lon": v.get("lon") if v else None,
            "source": c.get("source_url", ""),
        })
    out.sort(key=lambda c: -c["jewishShare"])
    return out


def _census_shares(census: list[dict]) -> dict[str, float]:
    """Доля идиш из переписи-1897 по id и по имени (для сверки Холокоста)."""
    out = {}
    for c in census:
        sh = c["jewishShare"]
        if c.get("id"):
            out[c["id"]] = sh
        out[c["ru"]] = sh
    return out


def holocaust(data: dict, name2id: dict, census: list[dict]) -> list[dict]:
    raw = json.loads((RAW / "holocaust.json").read_text())
    cshare = _census_shares(census)
    out = []
    for t in raw.get("towns", []):
        cid = t.get("city_id") or _resolve(t["city_ru"], data, name2id)
        v = data.get(cid) if cid else None
        # доля евреев-1897: ПЕРЕСЧЁТ из переписи проекта (идиш/всё) - имеет
        # приоритет над скопированными энциклопедическими процентами (они
        # брались к иной базе населения и завышали до +11 п.п.); если города
        # нет в переписи - оценка разведки с пометкой basis
        census_sh = cshare.get(cid) or cshare.get(t["city_ru"])
        share = census_sh if census_sh is not None else t.get("jewish_share_1897")
        basis = "перепись-1897 (идиш/всё)" if census_sh is not None else "оценка источника"

        # население из рядов проекта (приоритет над оценками разведки)
        def pop(y):
            if v and str(y) in v["pop"]:
                return int(v["pop"][str(y)][0])
            return t.get(f"pop_{y}")
        out.append({
            "id": cid, "ru": t["city_ru"],
            "jewishShare1897": share, "shareBasis": basis,
            "jewishCount1897": t.get("jewish_count_1897"),
            "pop1939": pop(1939), "pop1959": pop(1959),
            "note": t.get("ghetto_note", ""),
            "sources": t.get("sources", []),
        })
    out.sort(key=lambda t: -(t["jewishShare1897"] or 0))
    return out


def build() -> dict:
    data = json.loads((OUT / "data.json").read_text())["territories"]
    name2id = {v["ru"]: v["id"] for v in data.values() if v["level"] == "city"}
    events = json.loads((RAW / "events.json").read_text()).get("events", [])
    events.sort(key=lambda e: e["year"])
    census = census_1897(data, name2id)
    return {
        "series": _by_series(data),
        "seriesYears": SERIES_YEARS,
        "events": events,
        "census1897": census,
        "holocaust": holocaust(data, name2id, census),
    }


def main() -> None:
    b = build()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "shocks.json").write_text(json.dumps(
        {"version": VERSION, **b}, ensure_ascii=False))

    s = b["series"]
    print(f"OK: shocks.json ({len(b['events'])} событий, "
          f"{len(b['census1897'])} городов-1897, {len(b['holocaust'])} местечек)")
    print(f"  ряд: 1897 {s.get('1897',0)/1e6:.2f}М · 1940 {s.get('1940',0)/1e6:.2f}М "
          f"-> 1950 {s.get('1950',0)/1e6:.2f}М (обрыв ВМВ) · 2026 {s.get('2026',0)/1e6:.2f}М")
    top = b["census1897"][:5]
    print("  «местечки» по доле евреев-1897:",
          ", ".join(f"{c['ru']} {c['jewishShare']:.0f}%" for c in top))


if __name__ == "__main__":
    main()
