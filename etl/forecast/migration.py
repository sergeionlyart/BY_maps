"""Миграция для CCMPP уровней 0-1.

Внутренняя (межобластная): матрица переписи-2019 (поток за год до переписи)
-> годовые чистые сальдо по областям с возрастным профилем; параметр
сценария `centripetal` масштабирует интенсивность (централизация страны).

Международная: сценарное чистое сальдо страны (чел/год по периодам),
распределяемое по областям стартовыми ключами WP-F3 (Минск 55-70% и т.д.)
и по возрастам - профилем внутренних мигрантов (молодёжный пик).
"""
from __future__ import annotations

from . import TERRITORIES, AGE_GROUPS, STEP
from .data import migration_matrix

# распределение международного сальдо по областям: стартовые ключи WP-F3
# (TASK_SPEC: Минск 55-70%, облцентры 20-30%); для уровня областей относим
# доли облцентров к их областям пропорционально населению центров
INTL_KEYS = {
    "BY-HM": 0.62,
    "BY-MI": 0.10,   # минская агломерация
    "BY-BR": 0.06, "BY-VI": 0.05, "BY-HO": 0.06, "BY-HR": 0.05, "BY-MA": 0.06,
}

# нормированный возрастной профиль мигрантов (доли группы в потоке) - считается
# из матрицы F602; половое распределение 50/50 (перепись не даёт пола в кубе)
_SEX_SPLIT = 0.5

# Матрица F602 - НАКОПЛЕННАЯ (lifetime) миграция: «предыдущее место
# жительства» без ограничения давности; суммарный межобластной объём
# 1,46 млн человек. Для годовых потоков матрица используется только как
# ПРОФИЛЬ направлений и возрастов, а объём калибруется константой:
# межобластная миграция РБ по данным ежегодников 2015-2019 - 55-65 тыс.
# перемещений в год (принято 60 тыс.; чувствительность +-50% - в WP-F5).
ANNUAL_INTEROBLAST_MOVES = 60_000


def _age_profile(year: int = 2019) -> dict[str, float]:
    m = migration_matrix(year)
    totals = dict.fromkeys(AGE_GROUPS, 0.0)
    for origin, dests in m.items():
        for dest, ages in dests.items():
            if origin == dest:
                continue
            for age, v in ages.items():
                a = "80+" if age.startswith(("80", "85")) else age
                if a in totals:
                    totals[a] += v
    s = sum(totals.values()) or 1.0
    return {a: v / s for a, v in totals.items()}


def internal_net_per_year(year: int = 2019) -> dict[str, dict[str, float]]:
    """Годовое чистое внутреннее сальдо: {terr: {age_group: net}}.

    Направления и возрастная структура - из lifetime-матрицы переписи;
    объём нормирован к ANNUAL_INTEROBLAST_MOVES перемещений в год.
    Сумма нетто по стране тождественно равна нулю.
    """
    m = migration_matrix(year)
    gross = sum(v for o, ds in m.items() for d, ages in ds.items()
                if o != d for v in ages.values())
    k = ANNUAL_INTEROBLAST_MOVES / gross if gross else 0.0
    net = {t: dict.fromkeys(AGE_GROUPS, 0.0) for t in TERRITORIES}
    for origin, dests in m.items():
        for dest, ages in dests.items():
            if origin == dest or origin not in net or dest not in net:
                continue
            for age, v in ages.items():
                a = "80+" if age.startswith(("80", "85")) else age
                if a in net[origin]:
                    net[origin][a] -= v * k
                    net[dest][a] += v * k
    return net


def step_net_migration(terr: str, period_start: int, scenario: dict) -> dict:
    """Чистая миграция территории за пятилетку {sex: {age: net}}:
    внутренняя (x centripetal) + международная (сценарная)."""
    profile = _age_profile()
    internal = internal_net_per_year()
    centr = scenario.get("centripetal", 1.0)

    intl_by_period = scenario["intl_net_per_year"]  # {"2026": чел/год, ...}
    # выбрать значение периода, в который попадает шаг
    starts = sorted(int(y) for y in intl_by_period)
    val = 0.0
    for y in starts:
        if period_start >= y:
            val = float(intl_by_period[str(y)])
    intl_terr_year = val * INTL_KEYS[terr]

    out = {"m": dict.fromkeys(AGE_GROUPS, 0.0), "f": dict.fromkeys(AGE_GROUPS, 0.0)}
    for a in AGE_GROUPS:
        net_year = internal[terr][a] * centr + intl_terr_year * profile[a]
        per_sex = net_year * STEP * _SEX_SPLIT
        out["m"][a] += per_sex
        out["f"][a] += per_sex
    return out
