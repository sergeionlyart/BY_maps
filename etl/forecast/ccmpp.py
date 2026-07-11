"""Когортно-компонентная передвижка (CCMPP), шаг 5 лет, 5-летние группы.

Вход на шаг: структура {sex: {age_group: pop}}, коэффициенты передвижки
(survival_5y), ASFR (на 1000 женщин, 7 фертильных групп), чистая миграция
за пятилетку {sex: {age_group: net}}.

Рождения за шаг: сумма по фертильным группам среднегодовой экспозиции
женщин x ASFR x 5 лет; соотношение полов при рождении 105 мальчиков
на 100 девочек (1.05/2.05).
"""
from __future__ import annotations

from . import AGE_GROUPS, FERTILE, STEP

SRB_MALE = 1.05 / 2.05  # доля мальчиков при рождении


def project_step(pop: dict, surv: dict, asfr: dict[str, float],
                 net_mig: dict | None = None) -> tuple[dict, float]:
    """Один шаг t -> t+5. Возвращает (новая структура, рождений за шаг)."""
    new = {"m": dict.fromkeys(AGE_GROUPS, 0.0), "f": dict.fromkeys(AGE_GROUPS, 0.0)}

    for sex in ("m", "f"):
        S = surv[sex]["S"]
        # обычные переходы
        for g in range(len(AGE_GROUPS) - 2):        # 0-4..70-74 -> следующий
            new[sex][AGE_GROUPS[g + 1]] = pop[sex][AGE_GROUPS[g]] * S[g]
        # открытый интервал: (75-79 + 80+) -> 80+
        new[sex]["80+"] = (pop[sex]["75-79"] + pop[sex]["80+"]) * surv[sex]["S_open"]

    # рождения: экспозиция женщин = среднее численностей на начало/конец шага
    births = 0.0
    for g in FERTILE:
        exposure = 0.5 * (pop["f"][g] + new["f"][g])
        births += exposure * asfr.get(g, 0.0) / 1000.0 * STEP
    new["m"]["0-4"] = births * SRB_MALE * surv["m"]["L0_5l0"]
    new["f"]["0-4"] = births * (1 - SRB_MALE) * surv["f"]["L0_5l0"]

    # миграция (чистое сальдо за пятилетку, половина доживает шаг - упрощение:
    # добавляем в конце шага целиком; документировано)
    if net_mig:
        for sex in ("m", "f"):
            for g, v in net_mig[sex].items():
                new[sex][g] = max(new[sex][g] + v, 0.0)

    return new, births


def total(pop: dict) -> float:
    return sum(pop["m"].values()) + sum(pop["f"].values())
