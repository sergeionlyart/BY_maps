#!/usr/bin/env python3
"""Инварианты INF-13 (pension), автономно (stdlib, без pytest): покрытие
118 районов, диапазоны SR/TDR, согласованность порогов crossing_year,
логика подавления CG (G-7), интервализация crossing_year (следствие
непройденной G-3), и редакционный запрет (раздел 8 пререгистрации) на
формулировки, описывающие CG как самостоятельный районный бюджет: показатель
условный, ФСЗН - общереспубликанский фонд, отдельных территориальных
пенсионных балансов не существует и они не публикуются."""
import csv
import json
import re
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[2]

failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        failures.append(msg)


d = json.loads((PKG / "web" / "public" / "data" / "pension.json").read_text())
terr = d["territories"]
raions = {k: v for k, v in terr.items() if k.startswith("r-")}
years_t = d["years"]["territory"]
years_n = d["years"]["national"]
thresholds = d["thresholds"]  # [2.0, 1.5, 1.0]

# --- 1. покрытие 118 районов, длина рядов
check(len(raions) == 118, f"районов {len(raions)} != 118")
for r, v in raions.items():
    sr = v["sr"]["as_is"]["base:official"]
    tdr = v["tdr"]["as_is"]["base:official"]
    check(len(sr) == len(years_t), f"{r}: длина ряда SR {len(sr)} != {len(years_t)}")
    check(len(tdr) == len(years_t), f"{r}: длина ряда TDR {len(tdr)} != {len(years_t)}")

# --- 2. диапазоны SR/TDR (правдоподобные значения, не проверка точных чисел -
#     точные числа сверяет code/verify.py против checks/expected_results.json)
for r, v in raions.items():
    for policy in d["policy_variants"]:
        for key in d["series_keys"]:
            for val in v["sr"][policy][key]:
                check(val is None or 0.0 < val < 20.0, f"{r} {policy} {key}: SR вне диапазона {val}")
            for val in v["tdr"][policy][key]:
                check(val is None or 0.0 <= val < 5.0, f"{r} {policy} {key}: TDR вне диапазона {val}")

# --- 3. crossing_year монотонен по порогу: чем ниже порог, тем позже (или так
#     же) достигается переход (SR убывает во времени в подавляющем большинстве
#     траекторий 1989-2056)
for r, v in raions.items():
    for policy in d["policy_variants"]:
        for key in d["series_keys"]:
            c = v["crossing"][policy][key]
            y20, y15, y10 = c["2.0"], c["1.5"], c["1.0"]
            if y20 is not None and y15 is not None:
                check(y20 <= y15, f"{r} {policy} {key}: crossing(2.0)={y20} > crossing(1.5)={y15}")
            if y15 is not None and y10 is not None:
                check(y15 <= y10, f"{r} {policy} {key}: crossing(1.5)={y15} > crossing(1.0)={y10}")
nat_c = d["national"]["crossing"]
for policy in d["policy_variants"]:
    for key in d["series_keys"]:
        c = nat_c[policy][key]
        y20, y15, y10 = c["2.0"], c["1.5"], c["1.0"]
        if y20 is not None and y15 is not None:
            check(y20 <= y15, f"нац. {policy} {key}: crossing(2.0)={y20} > crossing(1.5)={y15}")
        if y15 is not None and y10 is not None:
            check(y15 <= y10, f"нац. {policy} {key}: crossing(1.5)={y15} > crossing(1.0)={y10}")

# --- 4. G-3 не пройдена на районном уровне (docs/decisions/INF-13.md,
#     VALIDATION.md) -> crossing_year района публикуется ИНТЕРВАЛОМ у ВСЕХ
#     районов (meta.validation.G3_backtest == false); национальный
#     crossing_interval не публикуется вовсе (поле отсутствует на верхнем
#     уровне national)
check(d["meta"]["validation"]["G3_backtest"] is False,
      "ожидалось G3_backtest=false (см. docs/notes/pension_validation.md)")
for r, v in raions.items():
    check(v["crossing_interval"] is not None, f"{r}: crossing_interval отсутствует, хотя G-3 не пройдена")
check("crossing_interval" not in d["national"], "national не должен публиковать crossing_interval")

# --- 5. подавление CG (G-7): cg_suppressed == commute_zone_45min ровно
#     (та же булева величина публикуется дважды под разными именами);
#     подавленные районы -> cg=null; неподавленные -> непустой словарь с
#     3 сериями "<сценарий>:official"
n_suppressed = 0
n_with_cg = 0
for r, v in raions.items():
    check(v["cg_suppressed"] == v["commute_zone_45min"],
          f"{r}: cg_suppressed != commute_zone_45min")
    if v["cg_suppressed"]:
        n_suppressed += 1
        check(v["cg"] is None, f"{r}: район подавлен (G-7), но cg не null")
    else:
        check(isinstance(v["cg"], dict) and len(v["cg"]) > 0,
              f"{r}: район не подавлен, но cg пуст/отсутствует")
        if v["cg"]:
            n_with_cg += 1
            expected_keys = {f"{sid}:official" for sid in ("base", "negative", "optimistic")}
            check(set(v["cg"].keys()) <= expected_keys,
                  f"{r}: неожиданные ключи серии cg {sorted(v['cg'].keys())}")
check(0 < n_suppressed < 118, f"n_suppressed вне разумного диапазона: {n_suppressed}")
check(d["meta"]["validation"]["G7_commute_bias"] == "fallback_applied",
      "G-7: ожидался запасной вариант (подавление CG), см. раздел 7 п.7 ТЗ")

# --- 6. G-1: публикация не остановлена (если бы G-1 не прошла - раздел 13 ТЗ
#     требует остановки публикации; в самой pension.json такого флага нет,
#     но meta.validation.G1_national_shares обязана быть true)
check(d["meta"]["validation"]["G1_national_shares"] is True,
      "G-1 не пройдена -> публикация не должна была продолжаться (раздел 13 ТЗ)")

# --- 7. зафиксированные параметры не разъехались с кодом
check(d["contribution_rate"] == 0.29, f"contribution_rate изменился: {d['contribution_rate']}")
check(thresholds == [2.0, 1.5, 1.0], f"thresholds изменились: {thresholds}")
check(sorted(d["policy_variants"]) == sorted(["as_is", "65_60", "67_62"]),
      f"policy_variants изменились: {d['policy_variants']}")
check(len(d["retirement_schedule"]) == 98,
      f"retirement_schedule: ожидался весь график 1959-2056 (98 лет), получено {len(d['retirement_schedule'])}")
check(d["retirement_schedule"]["2016"] == {"m": 60.0, "f": 55.0},
      "retirement_schedule[2016]: ожидался последний год до начала перехода (60.0/55.0)")
check(d["retirement_schedule"]["2022"] == {"m": 63.0, "f": 58.0},
      "retirement_schedule[2022]: ожидался финал графика (63.0/58.0)")
check(d.get("policy_applies_from") == 2026,
      f"policy_applies_from изменился: {d.get('policy_applies_from')}")

# --- 7б. находка проверяющего-скептика C (docs/decisions/INF-13.md): для
#     конкретного района CG(y) = K_r * SR(y), K_r - константа района. Значит
#     отношение cg/sr должно быть примерно постоянным по годам того же
#     района (допуск - только ошибка округления обеих величин до 2 знаков).
n_ratio_checked = 0
for r in raions:
    cg_series = terr[r].get("cg")
    if not cg_series:
        continue
    sr_ao = terr[r]["sr"]["as_is"]["base:official"]
    ratios = []
    for y_str, cg_v in cg_series.get("base:official", {}).items():
        y = int(y_str)
        if y in years_t and cg_v is not None:
            sr_v = sr_ao[years_t.index(y)]
            if sr_v:
                ratios.append(cg_v / sr_v)
    if len(ratios) >= 2:
        n_ratio_checked += 1
        mean_ratio = sum(ratios) / len(ratios)
        # оба значения (SR, CG) округлены до 2 знаков в экспорте - при малых
        # CG (некоторые районы-хосты с крупным городом обл. подчинения дают
        # K_r ~0,02-0,10) относительная ошибка округления велика, поэтому
        # допуск - относительный ЛИБО абсолютный (что больше)
        tol = max(0.03 * mean_ratio, 0.01)
        check(max(ratios) - min(ratios) <= tol,
              f"{r}: cg/sr не похоже на константу района (находка C) - {ratios}")
check(n_ratio_checked > 100, f"CG=K_r*SR проверено только у {n_ratio_checked} районов")

# --- 8. согласованность data/curated/pension_inputs.csv (регенерируется тем
#     же прогоном) с числом районов
rows = list(csv.DictReader(open(PKG / "data" / "curated" / "pension_inputs.csv")))
terr_in_csv = {r["territory_id"] for r in rows}
check(terr_in_csv <= set(raions), "pension_inputs.csv: территория вне номенклатуры районов")
check(len(terr_in_csv) > 100, f"pension_inputs.csv: районов в выгрузке {len(terr_in_csv)} подозрительно мало")

# --- 9. редакционный запрет: точная формулировка раздела 8 пререгистрации
#     (см. PREREGISTRATION.md) не должна появляться нигде в пакете, КРОМЕ
#     дословной цитаты самой пререгистрации, где она формулирует сам запрет,
#     а не описывает CG. Строка ниже собрана из частей, чтобы не дублировать
#     в исходном тексте ЭТОГО файла ту же связку слов.
_BANNED_PARTS = ("бюджет", "района")
BANNED = _BANNED_PARTS[0] + " " + _BANNED_PARTS[1]
EXEMPT_FILES = {"PREREGISTRATION.md"}  # дословная цитата замороженного раздела 8
hits = []
for p in PKG.rglob("*"):
    if p.is_file() and p.name not in EXEMPT_FILES and p.suffix in (
            ".md", ".yaml", ".yml", ".json", ".py", ".csv", ".cff"):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if BANNED in text.lower():
            hits.append(str(p.relative_to(PKG)))
check(not hits, f"запрещённая формулировка найдена вне PREREGISTRATION.md: {hits}")

if failures:
    print(f"ПРОВАЛЕНО ({len(failures)}):", file=sys.stderr)
    for f in failures[:30]:
        print("  " + f, file=sys.stderr)
    sys.exit(1)
print(f"Все инварианты выполнены: 118 районов, {n_suppressed} подавлено CG (G-7), "
      f"{n_with_cg} с рассчитанным CG, crossing_year интервализован у всех районов (G-3), "
      "запрещённая фраза не найдена.")
