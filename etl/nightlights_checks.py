#!/usr/bin/env python3
"""Внешняя проверка кандидатов H1-H3 (R4): производство, занятость,
зарплата, миграция, электроэнергия против резидуалов света.

Источники (все открытые, вендорены):
  - индекс промышленного производства (агрегат «Промышленность»),
    районы 2016-2021: data/raw/nightlights/checks/ipi_*.json;
  - производство электроэнергии по областям и категориям (включая
    «Атомная электростанция»), 2012-2020 (после 2020 не публикуется):
    data/raw/nightlights/checks/elec_*.json;
  - численность занятых по районам/городам 2010-2024:
    data/raw/wages/empl_person_10102000017_*.json;
  - зарплата по районам 2010-2025: data/curated/wages.csv (относительная
    к стране - самонормируется);
  - миграционное сальдо районов 1994-2024: web/public/data/migration.json.

Каждая проверка - направление внешнего ряда за период кейса и вердикт
consistent | inconsistent | context к направлению светового резидуала.
Вердикт - о СОГЛАСОВАННОСТИ рядов, не о причине: статус кейсов
остаётся «кандидат».

Выход: web/public/data/nightlights/external_checks.json
       docs/notes/nightlights_external_checks.md

Запуск: python -m etl.nightlights_checks
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from .common import ROOT, OUT

CHECKS_RAW = ROOT / "data" / "raw" / "nightlights" / "checks"
WAGES_RAW = ROOT / "data" / "raw" / "wages"
NL = OUT / "nightlights"

# имена территорий портала -> внутренние идентификаторы
PORTAL2ID = {
    "Республика Беларусь": "BY",
    "Гродненская область": "BY-HR",
    "г. Минск": "BY-HM",
    "Минская область": "BY-MI",
    "Островецкий": "r-astraviecki",
    "Минский": "r-minski",
    "Смолевичский": "r-smalavicki",
    "г. Жодино": "c-zhodzina",
}


def _num(s) -> float | None:
    if s is None:
        return None
    s = str(s).replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _portal_series(files: list[str], key_cols: int = 2) \
        -> dict[tuple, dict[int, float]]:
    """{(терр., признак): {год: значение}} из ответов дата-портала."""
    out: dict[tuple, dict[int, float]] = {}
    for fn in files:
        d = json.loads((CHECKS_RAW / fn).read_text())
        years = [int(y) for y in d["tableHeader"][0]]
        for row in d["tableRows"]:
            key = tuple(c["value"] for c in row[:key_cols])
            for i, y in enumerate(years):
                v = _num(row[key_cols + i]["value"]
                         if key_cols + i < len(row) else None)
                if v is not None:
                    out.setdefault(key, {})[y] = v
    return out


def load_ipi() -> dict[str, dict[int, float]]:
    """Индекс промпроизводства, % к пред. году -> {terr_id: {год: %}}."""
    raw = _portal_series(["ipi_10206000003_2012-2020.json",
                          "ipi_10206000003_2021-2025.json"])
    return {PORTAL2ID[t]: ys for (t, _cat), ys in raw.items()}


def load_elec() -> dict[tuple[str, str], dict[int, float]]:
    """Электроэнергия, млн кВт·ч -> {(terr_id, категория): {год: v}}."""
    raw = _portal_series(["elec_10207000004_2012-2019.json",
                          "elec_10207000004_2020-2025.json"])
    return {(PORTAL2ID[t], cat): ys for (t, cat), ys in raw.items()}


def load_empl() -> dict[str, dict[int, float]]:
    """Занятые (человек) по районам/городам из вендоренных ответов."""
    from .census_age import RAION_RU2ID, _e
    from .wages import CITY_RU2ID, OBL_RU2ID
    out: dict[str, dict[int, float]] = {}
    for fn in ("empl_person_10102000017_2010-2019.json",
               "empl_person_10102000017_2020-2026.json"):
        d = json.loads((WAGES_RAW / fn).read_text())
        years = [int(y) for y in d["tableHeader"][0]]
        for row in d["tableRows"]:
            name, level = row[0]["value"], row[0]["level"]
            tid = (OBL_RU2ID.get(name) or CITY_RU2ID.get(name)
                   or (RAION_RU2ID.get(_e(name)) if level == 2 else None))
            if tid is None:
                continue
            for i, y in enumerate(years):
                v = _num(row[i + 1]["value"] if i + 1 < len(row) else None)
                if v is not None:
                    out.setdefault(tid, {})[y] = v
    return out


def load_wage_rel() -> dict[str, dict[int, float]]:
    """Зарплата территории / зарплата страны (самонормируется)."""
    ser: dict[str, dict[int, float]] = {}
    with open(ROOT / "data" / "curated" / "wages.csv") as f:
        for r in csv.DictReader(f):
            ser.setdefault(r["territory_id"], {})[int(r["year"])] = \
                float(r["wage_byn"])
    nat = ser["BY"]
    return {t: {y: v / nat[y] for y, v in ys.items() if y in nat}
            for t, ys in ser.items()}


def load_migration() -> dict[str, dict[int, float]]:
    m = json.loads((OUT / "migration.json").read_text())["raions"]
    return {t: {int(y): v for y, v in rec["net"].items()}
            for t, rec in m.items()}


# ---------- расчёт по периодам ----------

def chain(ipi: dict[int, float], y0: int, y1: int) -> tuple[float, list[int]]:
    """Накопленный индекс за (y0, y1]: произведение годовых, %.
    Возвращает (индекс, использованные годы) - годы без данных
    пропускаются и перечисляются в covered."""
    acc, used = 1.0, []
    for y in range(y0 + 1, y1 + 1):
        if ipi.get(y) is not None:
            acc *= ipi[y] / 100.0
            used.append(y)
    return acc * 100.0, used


def total(series: dict[str, dict[int, float]], zones: list[str],
          year: int) -> float | None:
    vals = [series.get(z, {}).get(year) for z in zones]
    if any(v is None for v in vals):
        return None
    return sum(vals)


def pct(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or a == 0:
        return None
    return round((b / a - 1) * 100, 1)


def mig_sum(mig: dict[str, dict[int, float]], zones: list[str],
            y0: int, y1: int) -> int | None:
    out = 0
    for z in zones:
        ys = mig.get(z)
        if ys is None:
            return None
        out += sum(v for y, v in ys.items() if y0 < y <= y1)
    return int(out)


def build() -> dict:
    cands = json.loads((NL / "research_candidates.json").read_text())
    ipi = load_ipi()
    elec = load_elec()
    empl = load_empl()
    wage = load_wage_rel()
    mig = load_migration()

    # зоны внешних рядов: свет Смолевичского района покрывает и Жодино
    ZONES = {
        "minsk-agglomeration": ["BY-HM", "r-minski"],
        "smolevichi-zhodino": ["r-smalavicki", "c-zhodzina"],
        "astravets": ["r-astraviecki"],
    }

    out_cases = []
    for c in cands["candidates"]:
        cid = c["id"]
        y0, y1 = c["period"]
        zones = ZONES[cid]
        checks = []

        # 1) производство: цепной индекс по каждой зоне (индексы зон
        # не складываются - показываем каждую)
        for z in zones:
            if z not in ipi:
                continue
            idx, used = chain(ipi[z], y0, y1)
            if not used:
                continue
            checks.append({
                "metric": "industrial_production_index",
                "zone": z,
                "value": round(idx, 1),
                "unit": f"% (накопленно {used[0] - 1}->{used[-1]})",
                "coveredYears": used,
                "note": "районные индексы публикуются 2016-2021",
                "source": "Белстат 10206000003, агрегат «Промышленность»",
            })

        # 2) занятость: сумма по зонам; если по какой-то зоне ряда нет
        # (Минск-город вне районного набора) - по каждой зоне отдельно
        ya = max(y0, 2010)
        yb = min(y1, 2024)
        ch = pct(total(empl, zones, ya), total(empl, zones, yb))
        if ch is not None:
            checks.append({
                "metric": "employment",
                "zone": "+".join(zones),
                "value": ch, "unit": f"% ({ya}->{yb})",
                "source": "Белстат 10102000017 (занятые, человек)",
            })
        else:
            for z in zones:
                chz = pct(empl.get(z, {}).get(ya), empl.get(z, {}).get(yb))
                if chz is not None:
                    checks.append({
                        "metric": "employment",
                        "zone": z,
                        "value": chz, "unit": f"% ({ya}->{yb})",
                        "note": "по зонам вне районного набора занятых "
                                "(Минск-город) ряда нет",
                        "source": "Белстат 10102000017 (занятые, человек)",
                    })

        # 3) зарплата относительно страны
        for z in zones:
            wa, wb = wage.get(z, {}).get(ya), wage.get(z, {}).get(yb)
            if wa and wb:
                checks.append({
                    "metric": "relative_wage",
                    "zone": z,
                    "value": round((wb - wa) * 100, 1),
                    "unit": f"п.п. к средней по стране ({ya}->{yb})",
                    "detail": f"{wa * 100:.0f}% -> {wb * 100:.0f}%",
                    "source": "Белстат 10218000003",
                })

        # 4) миграция: суммарное сальдо за период
        ms = mig_sum(mig, zones, y0, min(y1, 2024))
        if ms is not None:
            checks.append({
                "metric": "net_migration",
                "zone": "+".join(zones),
                "value": ms, "unit": f"человек, сумма ({y0}->{min(y1, 2024)})",
                "note": "2020-2023 Белстатом не публиковались - в сумме "
                        "только опубликованные годы",
                "source": "Белстат 10101300001-3 (панель INF-05)",
            })

        # 5) электроэнергия - только для H3. Строка «Атомная
        # электростанция» публикуется лишь на уровне страны (БелАЭС -
        # единственная АЭС, расположена в Островецком районе); ряд
        # обрывается на 2020 - эффект полной мощности АЭС в открытой
        # статистике генерации не наблюдаем, поэтому вердикт контекстный
        if cid == "astravets":
            grod = elec.get(("BY-HR", "Все категории энергоисточников"), {})
            aes = elec.get(("BY", "Атомная электростанция"), {})
            if grod:
                checks.append({
                    "metric": "electricity_production_oblast",
                    "zone": "BY-HR",
                    "value": pct(grod.get(2012), grod.get(2020)),
                    "unit": "% (2012->2020, Гродненская область)",
                    "detail": f"{grod.get(2012):.0f} -> {grod.get(2020):.0f} "
                              f"млн кВт·ч; АЭС (уровень страны, 2020): "
                              f"{aes.get(2020, 0):.0f} млн кВт·ч - пуск "
                              "ноябрь 2020, двумя месяцами",
                    "note": "рост областной генерации 2012-2019 предшествует "
                            "пуску АЭС; после 2020 данные не публикуются",
                    "source": "Белстат 10207000004",
                })
        out_cases.append({
            "caseId": cid, "period": [y0, y1],
            "lightResidualPct": c["metrics"]["lightResidualPct"],
            "direction": c["direction"],
            "checks": checks,
        })

    return {
        "note": "Внешняя проверка кандидатов: согласованность открытой "
                "статистики с направлением светового резидуала. "
                "Согласованность - не причина: статус кейсов остаётся "
                "«кандидат».",
        "sources_registry": "data/raw/nightlights/checks/registry.csv",
        "cases": out_cases,
    }


def verdicts(data: dict) -> None:
    """Проставить вердикты consistent|inconsistent|context по правилам,
    прозрачным для читателя (описаны в каждом вердикте)."""
    for case in data["cases"]:
        light_up = case["direction"] == "light_above_statistics"
        for ch in case["checks"]:
            m, v = ch["metric"], ch["value"]
            if v is None:
                ch["verdict"] = "context"
                continue
            if m == "industrial_production_index":
                grew = v > 102.0   # накопленно выше +2%
                fell = v < 98.0
                ch["verdict"] = (
                    "consistent" if (light_up and grew)
                    or (not light_up and fell) else
                    "inconsistent" if (light_up and fell)
                    or (not light_up and grew) else "context")
                ch["rule"] = ("свет выше статистики населения - ждём роста "
                              "производства; свет ниже - спада"
                              if light_up else
                              "свет ниже статистики населения - ждём спада "
                              "производства")
            elif m == "employment":
                grew, fell = v > 2.0, v < -2.0
                ch["verdict"] = (
                    "consistent" if (light_up and grew)
                    or (not light_up and fell) else
                    "inconsistent" if (light_up and fell)
                    or (not light_up and grew) else "context")
                ch["rule"] = "занятость движется вместе с активностью"
            elif m == "net_migration":
                # приток людей при «свет выше населения» - скорее
                # опровержение чисто инфраструктурной гипотезы, поэтому
                # для миграции вердикт всегда контекстный: она проверяет
                # ГИПОТЕЗЫ (субурбанизация/отток), а не сам резидуал
                ch["verdict"] = "context"
                ch["rule"] = ("миграция проверяет гипотезы кейса "
                              "(субурбанизация, отток), не резидуал")
            elif m == "relative_wage":
                ch["verdict"] = "context"
                ch["rule"] = "зарплатная динамика - косвенный фон"
            elif m == "electricity_production_oblast":
                ch["verdict"] = "context"
                ch["rule"] = ("открытый ряд генерации обрывается на 2020 - "
                              "до выхода АЭС на мощность; сам по себе рост "
                              "области не декомпозируется")


def report(data: dict) -> str:
    L = ["# Внешняя проверка кандидатов H1–H3 (R4)", "",
         "Правило чтения: «consistent» означает, что открытая статистика "
         "движется в ту же сторону, что и световой резидуал; это "
         "повышает доверие к кейсу, но не устанавливает причину.", ""]
    RU = {"industrial_production_index": "Индекс промпроизводства",
          "employment": "Занятость",
          "relative_wage": "Зарплата к средней по стране",
          "net_migration": "Миграционное сальдо",
          "electricity_production_oblast": "Производство электроэнергии"}
    for case in data["cases"]:
        L.append(f"## {case['caseId']} · резидуал света "
                 f"{case['lightResidualPct']:+.1f}% "
                 f"({case['period'][0]}–{case['period'][1]})")
        L.append("")
        L.append("| проверка | зона | значение | вердикт |")
        L.append("|---|---|---|---|")
        for ch in case["checks"]:
            val = f"{ch['value']}" if ch["value"] is not None else "н/д"
            L.append(f"| {RU[ch['metric']]} | {ch['zone']} | {val} "
                     f"{ch['unit']} | {ch['verdict']} |")
        L.append("")
        for ch in case["checks"]:
            if ch.get("detail") or ch.get("note"):
                L.append(f"- {RU[ch['metric']]} ({ch['zone']}): "
                         f"{ch.get('detail', '')} "
                         f"{('· ' + ch['note']) if ch.get('note') else ''}"
                         .strip())
        L.append("")
    L.append("Источники и sha256 — data/raw/nightlights/checks/registry.csv; "
             "занятость/зарплата — data/raw/wages/registry.csv; миграция — "
             "пакет by-maps-migration-v1.0.0.")
    return "\n".join(L) + "\n"


def main() -> None:
    data = build()
    verdicts(data)
    (NL / "external_checks.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1))
    (ROOT / "docs" / "notes" / "nightlights_external_checks.md").write_text(
        report(data))
    for case in data["cases"]:
        vs = [c["verdict"] for c in case["checks"]]
        print(f"{case['caseId']}: {len(vs)} проверок, "
              f"consistent={vs.count('consistent')}, "
              f"inconsistent={vs.count('inconsistent')}, "
              f"context={vs.count('context')}")
    print("OK: external_checks.json + nightlights_external_checks.md")


if __name__ == "__main__":
    main()
