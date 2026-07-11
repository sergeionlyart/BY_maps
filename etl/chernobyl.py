"""INF-07 `chernobyl`: чернобыльский след - реестр зон, матчинг контролей,
сравнение траекторий.

Классификация районов - по официальным источникам:
- перечни НП в зонах радиоактивного загрязнения: пост. СМ РБ от 08.02.2021
  № 75 (действующий, 2022 НП) и от 11.01.2016 № 9 (2193 НП) - подсчёт НП
  по зонам в data/raw/chernobyl/districts_zones.json (агрегат официальных
  перечней, суммы сверены с итогами актов);
- закрытые (отселённые) территории с контрольно-пропускным режимом -
  табл. 12 издания МЧС «Беларусь и Чернобыль: 36 лет» (2022).

Класс 1 «зона эвакуации/отселения»: Брагинский, Хойникский, Наровлянский -
эвакуация 1986 г., территория Полесского заповедника (официальный список).
Класс 2 «сильно загрязнённые»: 9 районов с закрытыми отселёнными
территориями (все остальные районы табл. 12, кроме Климовичского: 534 га
и 0 отселённых НП со строениями - вне классификации, см. borderline).

Контрфактическая пара: каждому району классов 1-2 подбирается контрольный
район, максимально близкий по населению переписи-1979 (последняя перепись
до катастрофы), не входящий в перечни зон ни в одной редакции; предпочтение
востоку страны (вне Западной Беларуси 1921-1939 - иная траектория XX века)
и той же области. Контроль используется не более одного раза.

Запуск: python -m etl.chernobyl  ->  web/public/data/chernobyl.json
                                     data/curated/chernobyl_zones.csv
"""
from __future__ import annotations

import csv
import json
import math

from .common import ROOT, OUT

RAW = ROOT / "data" / "raw" / "chernobyl"
CURATED = ROOT / "data" / "curated"
VERSION = "1.0.0"

CLASS1 = ["Брагинский", "Хойникский", "Наровлянский"]
CLASS2 = [
    "Ветковский", "Чечерский", "Добрушский", "Кормянский", "Буда-Кошелевский",
    "Краснопольский", "Костюковичский", "Чериковский", "Славгородский",
]
# закрытые отселённые территории с КПП-режимом, га (табл. 12, на 2022 г.)
CLOSED_AREA_HA = {
    "Брагинский": 71564.5, "Хойникский": 88331.9, "Наровлянский": 70426.8,
    "Ветковский": 79634.0, "Чечерский": 24261.0, "Добрушский": 22960.3,
    "Кормянский": 10546.4, "Буда-Кошелевский": 4016.3,
    "Краснопольский": 26176.5, "Костюковичский": 17926.3,
    "Чериковский": 12990.7, "Славгородский": 7678.0, "Климовичский": 534.1,
}
BORDERLINE = {
    "Ельский": "12 НП в зоне 5-15 Ки (2021), но закрытых отселённых "
               "территорий нет - ниже порога класса 2",
    "Климовичский": "формально 13-й район с КПП-режимом, но всего 534 га "
                    "и 0 отселённых НП со строениями",
}
EVENTS = [
    {"year": 1986, "label": "Авария на ЧАЭС; эвакуация 30-км зоны (из трёх районов класса 1 — 22 тыс. чел.)"},
    {"year": 1988, "label": "Создан Полесский заповедник; отселение НП >15 Ки/км²"},
    {"year": 1991, "label": "Законы о соцзащите и правовом режиме территорий"},
    {"year": 2016, "label": "Перечень-2016: 2193 НП в зонах"},
    {"year": 2021, "label": "Перечень-2021: 2022 НП в зонах"},
]
NPA = {
    "current": "пост. Совета Министров РБ от 08.02.2021 № 75 "
               "(Нац. правовой портал, 11.02.2021, 5/48775): 2022 НП",
    "y2016": "пост. Совета Министров РБ от 11.01.2016 № 9 "
             "(Нац. правовой портал, 15.01.2016, 5/41546): 2193 НП",
}

BASE_YEAR = 1979  # последняя перепись до катастрофы


def _e(s: str) -> str:
    return s.replace("ё", "е").replace("Ё", "Е")


def load_zone_counts() -> dict:
    """{ru_район: {'2021': {PRK, PO, POSL}, '2016': {...}}} по агрегату перечней."""
    src = json.loads((RAW / "districts_zones.json").read_text())
    out: dict = {}
    for ed_key, ed in (("2021", src["2021_75"]), ("2016", src["2016_9"])):
        for key, zones in ed.items():
            _obl, name = key.split("|")
            rec = out.setdefault(_e(name), {})
            rec[ed_key] = {z: int(n) for z, n in zones.items()}
    return out


def main() -> None:
    data = json.loads((OUT / "data.json").read_text())["territories"]
    raions = {t: v for t, v in data.items() if v["level"] == "raion"}
    by_name = {_e(v["ru"].replace(" район", "")): t for t, v in raions.items()}

    zones = load_zone_counts()
    for name in zones:
        assert name in by_name, f"район перечня не найден в реестре: {name}"

    affected_names = CLASS1 + CLASS2
    contaminated_ids = {by_name[n] for n in zones}

    # кандидаты в контроли: ни одного НП в зонах в обеих редакциях,
    # есть перепись-1979, не ядро минской агломерации (аномальный рост,
    # не «естественная» траектория сельского района)
    minsk_suburbs = {"r-minski", "r-dziarzhynski", "r-smalavicki"}
    assert minsk_suburbs <= set(raions), minsk_suburbs - set(raions)
    candidates = [
        t for t, v in raions.items()
        if t not in contaminated_ids and "1979" in v["pop"] and t not in minsk_suburbs
    ]

    def cost(aff: dict, cand: dict) -> float:
        c = abs(math.log(cand["pop"]["1979"][0] / aff["pop"]["1979"][0]))
        if "west1921" in cand["flags"]:
            c += 0.5  # иная траектория XX века
        if cand["parent"] != aff["parent"]:
            c += 0.15
        return c

    used: set = set()
    pairs = []
    for name in sorted(affected_names, key=lambda n: -raions[by_name[n]]["pop"]["1979"][0]):
        t = by_name[name]
        aff = raions[t]
        best = min((c for c in candidates if c not in used),
                   key=lambda c: cost(aff, raions[c]))
        used.add(best)
        z = zones.get(name, {})
        pairs.append({
            "id": t,
            "ru": aff["ru"],
            "klass": 1 if name in CLASS1 else 2,
            "control": best,
            "controlRu": raions[best]["ru"],
            "pop1979": aff["pop"]["1979"][0],
            "controlPop1979": raions[best]["pop"]["1979"][0],
            "closedHa": CLOSED_AREA_HA.get(name),
            "np2021": z.get("2021", {}),
            "np2016": z.get("2016", {}),
        })
    pairs.sort(key=lambda p: (p["klass"], -(p["closedHa"] or 0)))

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "chernobyl.json").write_text(json.dumps({
        "version": VERSION,
        "baseYear": BASE_YEAR,
        "npa": NPA,
        "events": EVENTS,
        "classLabels": {
            "1": "зона эвакуации/отселения (ПГРЭЗ, эвакуация 1986)",
            "2": "сильно загрязнённые (закрытые отселённые территории)",
        },
        "borderline": BORDERLINE,
        "pairs": pairs,
    }, ensure_ascii=False))

    # CSV: все районы, встречающиеся в перечнях, + класс + счётчики
    rows = []
    for name, z in sorted(zones.items(), key=lambda kv: by_name[kv[0]]):
        t = by_name[name]
        klass = 1 if name in CLASS1 else 2 if name in CLASS2 else 0
        r21, r16 = z.get("2021", {}), z.get("2016", {})
        rows.append({
            "territory_id": t, "ru": raions[t]["ru"], "oblast": raions[t]["parent"],
            "class": klass,
            "np_prk_2021": r21.get("PRK", 0), "np_po_2021": r21.get("PO", 0),
            "np_posl_2021": r21.get("POSL", 0),
            "np_prk_2016": r16.get("PRK", 0), "np_po_2016": r16.get("PO", 0),
            "np_posl_2016": r16.get("POSL", 0),
            "closed_area_ha": CLOSED_AREA_HA.get(name, ""),
        })
    with open(CURATED / "chernobyl_zones.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    print(f"OK: chernobyl.json ({len(pairs)} пар, {len(rows)} районов в перечнях)")
    for p in pairs:
        a19, c19 = raions[p["id"]]["pop"].get("2019"), raions[p["control"]]["pop"].get("2019")
        ia = a19[0] / p["pop1979"] * 100 if a19 else None
        ic = c19[0] / p["controlPop1979"] * 100 if c19 else None
        print(f"  кл.{p['klass']} {p['ru']:26s} <-> {p['controlRu']:26s} "
              f"2019 к 1979: {ia:5.1f} против {ic:5.1f}")


if __name__ == "__main__":
    main()
