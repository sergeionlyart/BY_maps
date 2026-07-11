"""WP-F3: зеркальная статистика эмиграции 2020-2026 и ряд «adjusted».

Реконструкция интервальной оценки незарегистрированного чистого оттока
2020-2026 (накопленно, на 01.01.2026) из зеркальной статистики стран
приёма. Официальный ряд Белстата этот отток не отражает (независимые
ориентиры: 100-600 тыс.). Дата обращения ко всем источникам: 2026-07-11;
реестр с URL и sha256 - data/raw/mirror/registry.csv.

Три опорные величины (формулы прозрачны, каждая константа с источником):

- LOW - «документированные осевшие»: прирост стока действующих
  разрешений в ЕС 2019->2024, где польская отчётность Eurostat (включает
  нац. визы D, в т.ч. маятниковых) заменена стоком карт побыту UDSC,
  плюс Грузия. Ненаблюдаемые направления (РФ, Сербия, США...) - ноль.
- RAW_EU - прирост стока Eurostat migr_resvalid EU27 как есть
  (386 834 - 133 889 = 252 945): смешивает осевших и долгосрочно
  маятниковых, но официально опубликован (гейт приёмки TASK_SPEC).
- MID - среднее двух определений ЕС-прироста, досчитанное на
  ненаблюдаемые направления по опросным долям диаспоры (ЦНИ-2023:
  ЕС ~77,5%); HIGH - RAW_EU с тем же досчётом плюс маятниковый резидуал
  (GUS: 105 тыс. беларусов в Польше-2019 при 56 тыс. разрешений) -
  согласуется с официальным ориентиром МВД (350 тыс.) и верхом
  экспертных оценок.

Выходы: data/curated/migration_mirror.csv (ряды стоков/потоков),
data/curated/adjustment.csv (территория x год x low/mid/high),
приложение к docs/notes/adjustment.md.

Запуск: python -m etl.mirror
"""
from __future__ import annotations

import csv
import json

from .common import ROOT, OUT

RAW = ROOT / "data" / "raw" / "mirror"
CURATED = ROOT / "data" / "curated"

# ---------------------------------------------------------------- источники
# Каждая константа: значение, дата, источник (URL в registry.csv).

# Польша, сток карт побыту граждан BY (UDSC, ежемесячные отчёты):
UDSC_PL_CARDS_2026_01 = 144_219   # 01.01.2026, gov.pl/web/udsc (DOCX завендорен)
UDSC_PL_CARDS_END2024 = 125_000   # конец 2024, FREE Network brief 2026-04-27
                                  # («~125 тыс. держателей карт»)
PL_CARDS_END2019 = 17_000         # <17 тыс. карт до 2020 (Коршунов/ЦНИ по UDSC,
                                  # zerkalo 67856); согласуется с приростом
                                  # «новая миграция в Польшу - 113 тыс.» к 02.2024

# Грузия: граждане BY, осевшие после 2020 (Лузгина/BEROC, 01.01.2025)
GEORGIA_2025 = 12_800

# Недоучёт РФ в опросных долях: онлайн-выборка ЦНИ (гражданско-активная)
# даёт РФ лишь 3,7%; независимые оценки (Львовский/BEROC) - «десятки
# тысяч» без данных по РФ. Верхняя добавка к high (только он).
RU_UNDERCOUNT_HIGH = 40_000

# Опрос диаспоры ЦНИ (янв. 2023, n=1631): страна проживания сейчас
CNI_SHARES = {  # Diagram 2, PDF завендорен
    "PL": 0.450, "EU_other": 0.325,  # Балтия 10,3 + Старая Европа 10,6 + Юж/Вост/Сев 11,6
    "Caucasus": 0.104, "NewWorld": 0.051, "RU": 0.037, "other": 0.033,
}
CNI_EU_SHARE = CNI_SHARES["PL"] + CNI_SHARES["EU_other"]  # 0.775

# Возраст диаспоры (ЦНИ): 30% - 18-30 лет, 47% - 31-40, >3/4 моложе 40;
# пол: 53% мужчин / 46% женщин. Дети в опрос не входили (18+) - доля
# детей в потоке принята 15% (семейная миграция; допущение, см. записку).
ADULT_AGE_CNI = {"18-30": 0.30, "31-40": 0.47, "41+": 0.23}
CHILD_SHARE = 0.15
MALE_SHARE = 0.53

# Профиль поправки по 5-летним группам движка (сумма = 1):
# взрослые 85% по ЦНИ-долям, дети 15%
AGE_PROFILE = {
    "0-4": 0.05, "5-9": 0.06, "10-14": 0.04,
    "15-19": 0.025, "20-24": 0.10, "25-29": 0.13,
    "30-34": 0.20, "35-39": 0.20,
    "40-44": 0.09, "45-49": 0.05, "50-54": 0.03,
    "55-59": 0.015, "60-64": 0.01, "65-69": 0.0, "70-74": 0.0,
    "75-79": 0.0, "80+": 0.0,
}

# Территориальные ключи поправки (WP-F3: Минск 55-70%, облцентры 20-30%,
# остальное - крупные райцентры; берём середины интервалов спеки)
KEY_MINSK = 0.62
KEY_OBLCENTERS = 0.25
KEY_RAIONCENTERS = 0.13
OBL_CENTERS = {"c-brest": "BY-BR", "c-viciebsk": "BY-VI", "c-homiel": "BY-HO",
               "c-hrodna": "BY-HR", "c-mahilou": "BY-MA"}
# Минская область без собственного облцентра: её доля - только райцентры

# Временной профиль накопления (доли A по годам прибытия; из положительных
# приростов стока ЕС c ручным хвостом 2024-25: потоки продолжаются
# при снижающемся стоке - возвраты/вторичная миграция; см. записку)
TIME_PROFILE = {2020: 0.04, 2021: 0.28, 2022: 0.55, 2023: 0.08,
                2024: 0.03, 2025: 0.02}

ADJUSTMENT_YEARS = list(range(2020, 2027))  # накопленно на 01.01 года+1


# ------------------------------------------------------------ Eurostat

def _jsonstat_series(path) -> dict[str, dict[int, int]]:
    """{geo: {year: value}} из сохранённого ответа Eurostat JSON-stat."""
    d = json.loads(path.read_text())
    geos = d["dimension"]["geo"]["category"]["index"]
    times = d["dimension"]["time"]["category"]["index"]
    n_t = len(times)
    out: dict[str, dict[int, int]] = {}
    for g, gi in geos.items():
        for t, ti in times.items():
            v = d["value"].get(str(gi * n_t + ti))
            if v is not None:
                out.setdefault(g, {})[int(t)] = int(v)
    return out


def eu_stocks() -> dict:
    """Сток действующих разрешений граждан BY (migr_resvalid), 31.12."""
    return _jsonstat_series(RAW / "eurostat_migr_resvalid_BY_2019-2024.json")


def eu_first_permits() -> dict:
    """Первичные разрешения (migr_resfirst) по годам."""
    return _jsonstat_series(RAW / "eurostat_migr_resfirst_BY_2015-2024.json")


# ------------------------------------------------------------- интервал

def outflow_interval() -> dict:
    """Интервал накопленного незарегистрированного оттока на 01.01.2026.

    Возвращает {'low','mid','high', 'components': {...}} (человек)."""
    st = eu_stocks()
    raw_eu_gain = st["EU27_2020"][2024] - st["EU27_2020"][2019]  # 252 945

    # «осевшее» определение: Польша по картам UDSC вместо Eurostat (визы D)
    settled_2024 = st["EU27_2020"][2024] - st["PL"][2024] + UDSC_PL_CARDS_END2024
    settled_2019 = st["EU27_2020"][2019] - st["PL"][2019] + PL_CARDS_END2019
    settled_eu_gain = settled_2024 - settled_2019  # ~165,5 тыс.

    low = settled_eu_gain + GEORGIA_2025
    mid = round((settled_eu_gain + raw_eu_gain) / 2 / CNI_EU_SHARE)
    # маятниковый резидуал Польши-2019 (GUS 105,4 тыс. присутствовавших
    # против 55,9 тыс. разрешений): верхняя граница конверсии в эмиграцию
    pendular_residual = 105_404 - st["PL"][2019]
    high = round(raw_eu_gain / CNI_EU_SHARE) + pendular_residual + RU_UNDERCOUNT_HIGH
    return {
        "low": low, "mid": mid, "high": high,
        "components": {
            "raw_eu_gain": raw_eu_gain,
            "settled_eu_gain": settled_eu_gain,
            "settled_2024": settled_2024, "settled_2019": settled_2019,
            "georgia": GEORGIA_2025,
            "cni_eu_share": CNI_EU_SHARE,
            "pendular_residual": pendular_residual,
        },
    }


def territory_keys() -> dict[str, float]:
    """Доли территорий (области + Минск) в поправке; сумма = 1.

    Минск - KEY_MINSK; часть облцентров распределяется по областям
    пропорционально населению облцентров (01.01.2026), часть райцентров -
    пропорционально городскому населению области без облцентра."""
    data = json.loads((OUT / "data.json").read_text())["territories"]

    def pop26(t: str) -> float:
        p = data[t]["pop"]
        return float(p.get("2026", p[max(p)])[0])

    oc_pop = {c: pop26(c) for c in OBL_CENTERS}
    oc_sum = sum(oc_pop.values())

    # ключ райцентров: сумма городов области (без облцентров) по привязке
    # city_raion.csv - прозрачный прокси «крупных райцентров» спеки
    obl_of = {}
    for r in csv.DictReader(open(CURATED / "age2019.csv")):
        obl_of[r["territory_id"]] = r["oblast"]
    cmap = {r["city_id"]: r["raion_id"]
            for r in csv.DictReader(open(CURATED / "city_raion.csv"))}
    rc_pop: dict[str, float] = {}
    for c, rn in cmap.items():
        obl = obl_of.get(rn)
        if not obl or c in OBL_CENTERS:
            continue
        p = data[c]["pop"]
        if "2026" not in p and int(max(p)) < 2019:
            continue
        rc_pop[obl] = rc_pop.get(obl, 0.0) + pop26(c)
    rc_sum = sum(rc_pop.values())

    keys = {"BY-HM": KEY_MINSK}
    for c, obl in OBL_CENTERS.items():
        keys[obl] = keys.get(obl, 0.0) + KEY_OBLCENTERS * oc_pop[c] / oc_sum
    for obl, v in rc_pop.items():
        keys[obl] = keys.get(obl, 0.0) + KEY_RAIONCENTERS * v / rc_sum
    return keys


# --------------------------------------------------------------- выгрузка

def main() -> None:
    st, fp = eu_stocks(), eu_first_permits()
    interval = outflow_interval()
    keys = territory_keys()

    # зеркальные ряды
    with open(CURATED / "migration_mirror.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["indicator", "geo", "year", "value", "source"])
        for g, ys in sorted(st.items()):
            for y, v in sorted(ys.items()):
                w.writerow(["resvalid_stock", g, y, v, "Eurostat migr_resvalid"])
        for g, ys in sorted(fp.items()):
            for y, v in sorted(ys.items()):
                w.writerow(["first_permits", g, y, v, "Eurostat migr_resfirst"])
        w.writerow(["cards_stock", "PL", 2026, UDSC_PL_CARDS_2026_01, "UDSC 01.01.2026"])
        w.writerow(["cards_stock", "PL", 2024, UDSC_PL_CARDS_END2024, "FREE brief (UDSC)"])
        w.writerow(["cards_stock", "PL", 2019, PL_CARDS_END2019, "UDSC via ЦНИ/Коршунов"])
        w.writerow(["settled_stock", "GE", 2025, GEORGIA_2025, "Лузгина/BEROC"])

    # поправка по территориям и годам (накопленно на 01.01 следующего года)
    cum = 0.0
    cum_by_year = {}
    for y in range(2020, 2026):
        cum += TIME_PROFILE.get(y, 0.0)
        cum_by_year[y + 1] = cum          # на 01.01.(y+1)
    cum_by_year[2020] = 0.0               # на 01.01.2020 поправки ещё нет
    rows = []
    for y in ADJUSTMENT_YEARS:
        share = cum_by_year.get(y, 1.0)
        for t in ["BY"] + sorted(keys):
            k = 1.0 if t == "BY" else keys[t]
            rows.append({
                "territory_id": t, "year": y,
                "low": round(interval["low"] * share * k),
                "mid": round(interval["mid"] * share * k),
                "high": round(interval["high"] * share * k),
            })
    with open(CURATED / "adjustment.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["territory_id", "year", "low", "mid", "high"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    c = interval["components"]
    print(f"OK: migration_mirror.csv, adjustment.csv")
    print(f"  прирост стока ЕС 2019->2024: raw {c['raw_eu_gain']:,} | "
          f"осевшие {c['settled_eu_gain']:,}")
    print(f"  интервал накопленного оттока на 01.01.2026: "
          f"{interval['low']:,} / {interval['mid']:,} / {interval['high']:,}")
    print(f"  ключи территорий: " + ", ".join(
        f"{t} {v:.3f}" for t, v in sorted(keys.items())))
    assert abs(sum(keys.values()) - 1.0) < 1e-9


if __name__ == "__main__":
    main()
