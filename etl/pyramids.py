#!/usr/bin/env python3
"""Датасет раздела «Пирамида» (INF-11, задачи P-1/P-4): национальные
возрастно-половые структуры 1959-2075.

Состав кадров (тип достоверности у каждого):
  census        1959, 1970, 1979, 1989 (Демоскоп, таблицы переписей
                БССР; единичные возрасты сведены в 17 групп, «возраст
                не указан» сохранён отдельно) и 2009, 2019 (OLAP F201N,
                до человека);
  estimate      1990-2018 (годовые оценки Белстата на 1 января,
                индикатор 10101100003) и 2020-2026 (age_current.csv);
  interpolated  1960-1969, 1971-1978, 1980-1988 - межпереписные кадры:
                когортный варп опорных пирамид (пирамида Y0 «стареет»
                сдвигом групп, Y1 «молодеет», линейное смешение) -
                визуальная интерполяция, числа приближённые;
  model         2030-2075 (шаг 5) x 3 сценария x 2 стартовых ряда -
                интерполяция модельных узлов CCMPP v2026.4
                (data/curated/forecast_age_by_v2026_4.json, задача P-3).
                WPP-заглушка прототипа сюда НЕ входит.

Инварианты (etl/tests/test_pyramids.py): суммы census/estimate равны
итогам источников до человека (в т.ч. 2009 = 9 503 807, 2019 =
9 413 446, 2026 = 9 056 080); unknown не теряется; порядок групп
фиксирован; будущее согласовано с итогами прогноза (+-0,1%).

Выход: web/public/data/pyramids.json
Запуск: python -m etl.pyramids
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict

from .common import ROOT, OUT

RAW = ROOT / "data" / "raw" / "pyramid"
GROUPS = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34",
          "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69",
          "70-74", "75-79", "80+"]
OBLASTS = {"BY-BR", "BY-HM", "BY-HO", "BY-HR", "BY-MA", "BY-MI", "BY-VI"}

# колонки «м, ж» в таблицах Демоскопа: 1959 - брачная (все м / все ж),
# 1970/79/89 - age-таблицы (все население: оба/м/ж)
CENSUS_COLS = {1959: (1, 3), 1970: (2, 3), 1979: (2, 3), 1989: (2, 3)}


# ---------- парсер Демоскопа ----------

def _cells(html: str) -> list[list[str]]:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    out = []
    for r in rows:
        cs = [re.sub(r"<[^>]+>|&nbsp;?|\s+", " ", c).strip()
              for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
        if cs and any(cs):
            out.append(cs)
    return out


def _int(s: str) -> int | None:
    s = s.replace(" ", "").replace("\xa0", "")
    return int(s) if s.isdigit() else None


def parse_census(year: int) -> dict:
    """Пирамида переписи из завендоренного HTML: 17 групп + unknown.

    Строки таблицы: единичные возрасты (агрегируем сами), 5-летние
    подытоги «а-б»/«а–б» (используем как контроль или напрямую для
    1979), «100+»/«100 лет и старше» -> 80+, «возраст не указан/
    неизвестен» -> unknown, «Всего» -> контроль сумм.
    """
    mcol, fcol = CENSUS_COLS[year]
    html = (RAW / f"census_{year}.html").read_bytes().decode("cp1251")
    g = {"m": defaultdict(int), "f": defaultdict(int)}
    totals = {}
    singles_seen = False
    for cs in _cells(html):
        label = cs[0].lower().replace("–", "-").replace(" ", "")
        if len(cs) <= max(mcol, fcol):
            continue
        m, f = _int(cs[mcol]), _int(cs[fcol])
        if m is None or f is None:
            if "возраст" in label and ("неуказан" in label
                                       or "неизвестен" in label):
                pass
            else:
                continue
        if label == "всего":
            totals = {"m": m, "f": f}
        elif "возраст" in label and ("неуказан" in label
                                     or "неизвестен" in label):
            # значения могли не распарситься выше - парсим напрямую
            m = _int(cs[mcol]) or 0
            f = _int(cs[fcol]) or 0
            g["m"]["unknown"] += m
            g["f"]["unknown"] += f
        elif label.isdigit():                       # единичный возраст
            singles_seen = True
            a = int(label)
            grp = GROUPS[min(a // 5, 16)]
            g["m"][grp] += m
            g["f"][grp] += f
        elif re.fullmatch(r"(\d+)\+|(\d+)лет(?:и)?истарше|(\d+)илистарше|(\d+)летистарше", label) \
                or re.fullmatch(r"\d+летистарше", label):
            n = int(re.match(r"\d+", label).group())
            grp = GROUPS[min(n // 5, 16)]
            # открытый верх («85 лет и старше», «100+») копится отдельно
            # от подытогов: он не дублирует единичные строки
            g["m"][grp] += m
            g["f"][grp] += f
        elif re.fullmatch(r"\d+-\d+", label):
            # 5-летние подытоги: в таблицах с единичными возрастами
            # дублируют накопленное - складываем отдельно и используем
            # только если единичных строк не было (1979)
            lo, hi = map(int, label.split("-"))
            if hi - lo == 4 and lo % 5 == 0:
                grp = GROUPS[min(lo // 5, 16)]
                g.setdefault("_sub", defaultdict(
                    lambda: {"m": 0, "f": 0}))
                g["_sub"][grp]["m"] += m
                g["_sub"][grp]["f"] += f
    if not singles_seen:
        for grp, mf in g.get("_sub", {}).items():
            g["m"][grp] += mf["m"]
            g["f"][grp] += mf["f"]
    g.pop("_sub", None)
    series = {s: [g[s].get(a, 0) for a in GROUPS] for s in ("m", "f")}
    unknown = g["m"].get("unknown", 0) + g["f"].get("unknown", 0)
    got = {s: sum(series[s]) + g[s].get("unknown", 0) for s in ("m", "f")}
    assert got["m"] == totals["m"] and got["f"] == totals["f"], (
        f"перепись-{year}: суммы групп не сходятся с «Всего»: "
        f"{got} != {totals}")
    out = {"type": "census",
           "source": f"Перепись-{year}, БССР (Демоскоп Weekly, "
                     f"data/raw/pyramid/census_{year}.html)",
           "m": series["m"], "f": series["f"]}
    if unknown:
        out["unknown"] = unknown
    return out


# ---------- годовые оценки Белстата (1990-2018) ----------

def _num(s) -> float | None:
    if s is None:
        return None
    s = str(s).replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_dataportal() -> dict[int, dict]:
    """{год: {m:[17], f:[17], total_m, total_f}} из вендоренных ответов."""
    per_year: dict[int, dict] = defaultdict(
        lambda: {"m": [0] * 17, "f": [0] * 17, "tm": None, "tf": None})
    grp_idx = {f"в возрасте {a} лет".replace("80+", "80"): i
               for i, a in enumerate(GROUPS)}
    grp_idx["в возрасте 80 лет и старше"] = 16
    sex_map = {"мужчины": "m", "женщины": "f"}
    for p in sorted(RAW.glob("dataportal_age_*.json")):
        d = json.loads(p.read_text())
        years = [int(y) for y in d["tableHeader"][0]]
        for row in d["tableRows"]:
            age_name = row[1]["value"]
            sex = sex_map.get(row[2]["value"])
            if sex is None:
                continue
            for i, y in enumerate(years):
                v = _num(row[4 + i]["value"] if 4 + i < len(row) else None)
                if v is None:
                    continue
                if age_name == "По всем возрастам":
                    per_year[y]["t" + sex] = round(v)
                elif age_name in grp_idx:
                    per_year[y][sex][grp_idx[age_name]] = round(v)
    return dict(per_year)


# ---------- переписи 2009/2019 и оценки 2020-2026 (curated) ----------

def load_census_olap(path) -> dict:
    g = {"m": defaultdict(int), "f": defaultdict(int)}
    with open(path) as f:
        for r in csv.DictReader(f):
            if r["territory_id"] in OBLASTS and \
                    r.get("locality") in ("urban", "rural"):
                a = r["age_group"].replace(" ", "")
                if "неопредел" in a.lower():
                    a = "unknown"
                elif a in ("80-84", "85-89", "90-94", "95-99", "100+",
                           "85+", "90+") or a.startswith("80и"):
                    a = "80+"
                g[r["sex"]][a] += int(r["pop"])
    series = {s: [g[s].get(a, 0) for a in GROUPS] for s in ("m", "f")}
    unknown = g["m"].get("unknown", 0) + g["f"].get("unknown", 0)
    out = {"m": series["m"], "f": series["f"]}
    if unknown:
        out["unknown"] = unknown
    return out


def load_current() -> dict[int, dict]:
    by_year: dict[int, dict] = defaultdict(
        lambda: {"m": defaultdict(int), "f": defaultdict(int)})
    with open(ROOT / "data/curated/age_current.csv") as f:
        for r in csv.DictReader(f):
            if r["territory_id"] == "BY" and r["locality"] == "total" \
                    and r["sex"] in ("m", "f"):
                a = r["age_group"].replace(" ", "")
                if a in ("80-84", "85-89", "90-94", "95-99", "100+",
                         "85+", "90+") or a.startswith("80и"):
                    a = "80+"
                by_year[int(r["year"])][r["sex"]][a] += int(r["pop"])
    out = {}
    for y, g in by_year.items():
        out[y] = {s: [g[s].get(a, 0) for a in GROUPS] for s in ("m", "f")}
    return out


# ---------- когортный варп (межпереписная интерполяция, P-4) ----------

def _age_shift(vals: list[int], years: float) -> list[float]:
    """«Состарить» пирамиду на years лет: доля k=years/5 каждой группы
    переезжает в следующую (верхняя 80+ накапливает)."""
    k = years / 5.0
    out = [0.0] * len(vals)
    for i, v in enumerate(vals):
        stay = v * (1 - k)
        move = v * k
        out[i] += stay
        if i + 1 < len(vals):
            out[i + 1] += move
        else:
            out[i] += move
    return out


def interpolate(y: int, y0: int, s0: dict, y1: int, s1: dict) -> dict:
    """Кадр года y между опорами (y0,s0) и (y1,s1): когортный варп."""
    w = (y - y0) / (y1 - y0)
    aged = {s: _age_shift(s0[s], y - y0) for s in ("m", "f")}
    # «омолодить» s1 на (y1-y): сдвиг с отрицательным временем -
    # реализуем как отдачу доли из следующей группы в предыдущую
    k = (y1 - y) / 5.0
    younger = {}
    for s in ("m", "f"):
        vals = s1[s]
        out = [0.0] * len(vals)
        for i, v in enumerate(vals):
            out[i] += v * (1 - k)
            if i - 1 >= 0:
                out[i - 1] += v * k
            else:
                out[i] += v * k
        younger[s] = out
    return {
        "type": "interpolated",
        "source": f"когортный варп {y0}<->{y1} (визуальная интерполяция)",
        "m": [round(a * (1 - w) + b * w)
              for a, b in zip(aged["m"], younger["m"])],
        "f": [round(a * (1 - w) + b * w)
              for a, b in zip(aged["f"], younger["f"])],
    }


# ---------- будущее из экспорта CCMPP (P-3) ----------

def load_model() -> dict[str, dict]:
    d = json.loads(
        (ROOT / "data/curated/forecast_age_by_v2026_4.json").read_text())
    assert d["age_groups"] == GROUPS
    nodes = d["node_years"]
    out = {}
    for key, per_year in d["series"].items():
        sid, jo = key.split(":")
        for y in range(2030, 2076, 5):
            lo = max(n for n in nodes if n <= y)
            hi = min(n for n in nodes if n >= y)
            w = 0.0 if hi == lo else (y - lo) / (hi - lo)
            series = {}
            for s in ("m", "f"):
                a, b = per_year[str(lo)][s], per_year[str(hi)][s]
                series[s] = [round(x * (1 - w) + z * w)
                             for x, z in zip(a, b)]
            skey = f"{y}:{sid}" if jo == "official" else f"{y}:{sid}:adjusted"
            out[skey] = {
                "type": "model",
                "source": f"CCMPP v2026.4, сценарий {sid}, старт {jo} "
                          f"(узлы {lo}/{hi})",
                **series}
    return out


ANNOTATIONS = [
    {"id": "A1", "year": 2009, "cohort": [1940, 1944],
     "title": "Шрам войны"},
    {"id": "A2", "year": 2009, "cohort": [1965, 1969],
     "title": "Эхо войны"},
    {"id": "A3", "year": 2019, "cohort": [1995, 1999],
     "title": "Провал девяностых"},
    {"id": "A4", "year": 2026, "cohort": [2020, 2026],
     "title": "Основание уходит"},
    {"id": "A5", "year": 2026, "groups": ["70-74", "75-79", "80+"],
     "title": "Где мужчины?"},
    {"id": "A6", "year": 2026, "title": "Точка равновесия пройдена"},
    {"id": "A7", "year": 2075, "title": "Пирамида или гриб?"},
]  # тексты аннотаций - в контенте страницы (pyramid.ru.md / be)


def build() -> dict:
    series: dict[str, dict] = {}

    # переписи Демоскопа
    census_hist = {}
    for y in (1959, 1970, 1979, 1989):
        census_hist[y] = parse_census(y)
        series[str(y)] = census_hist[y]

    # годовые оценки 1990-2018
    portal = parse_dataportal()
    for y in sorted(portal):
        if not (1990 <= y <= 2018):
            continue
        rec = portal[y]
        series[str(y)] = {
            "type": "estimate",
            "source": "оценка Белстата на 1 января "
                      "(дата-портал, 10101100003)",
            "m": rec["m"], "f": rec["f"]}

    # межпереписная интерполяция 1960-1989 (опоры: переписи и 1990)
    anchors = [(1959, census_hist[1959]), (1970, census_hist[1970]),
               (1979, census_hist[1979]), (1989, census_hist[1989]),
               (1990, series["1990"])]
    for (y0, s0), (y1, s1) in zip(anchors, anchors[1:]):
        for y in range(y0 + 1, y1):
            series[str(y)] = interpolate(y, y0, s0, y1, s1)

    # переписи 2009/2019 (до человека) и оценки 2020-2026
    for y, path in ((2009, "data/curated/age2009.csv"),
                    (2019, "data/curated/age2019.csv")):
        series[str(y)] = {
            "type": "census",
            "source": f"перепись-{y} (OLAP F201N, до человека)",
            **load_census_olap(ROOT / path)}
    cur = load_current()
    for y in sorted(cur):
        if y == 2019 or y in (2009,):
            continue
        series[str(y)] = {
            "type": "estimate",
            "source": "оценка Белстата на 1 января (age_current.csv)",
            **cur[y]}

    # будущее: CCMPP-экспорт (P-3)
    series.update(load_model())

    return {
        "version": "1.0.0",
        "unit": "человек",
        "age_groups": GROUPS,
        "note": ("Типы кадров: census (переписи 1959-1989 БССР/Демоскоп; "
                 "2009, 2019 - до человека), estimate (оценки Белстата "
                 "на 1 января), interpolated (когортный варп между "
                 "переписями - визуальная интерполяция), model "
                 "(CCMPP v2026.4, 3 сценария x 2 стартовых ряда). "
                 "unknown («возраст не указан») в бары не входит, "
                 "в итоги входит. Переписной таблицы 1999 года в "
                 "открытых машиночитаемых источниках нет - кадр 1999 "
                 "является официальной оценкой."),
        "annotations": ANNOTATIONS,
        "series": series,
    }


def main() -> None:
    data = build()
    dst = OUT / "pyramids.json"
    dst.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":")))
    s = data["series"]

    def tot(k):
        rec = s[k]
        return sum(rec["m"]) + sum(rec["f"]) + rec.get("unknown", 0)

    for k, expect in (("1959", 8054648), ("1970", 9002338),
                      ("1979", 9532516), ("1989", None),
                      ("2009", 9503807), ("2019", 9413446),
                      ("2026", 9056080)):
        got = tot(k)
        mark = "OK" if expect is None or got == expect else \
            f"MISMATCH (ожидалось {expect})"
        print(f"  {k} [{s[k]['type']}]: {got} {mark}")
    n_by_type = defaultdict(int)
    for rec in s.values():
        n_by_type[rec["type"]] += 1
    print(f"OK: {dst.name} | серий: {len(s)} | {dict(n_by_type)}")


if __name__ == "__main__":
    main()
