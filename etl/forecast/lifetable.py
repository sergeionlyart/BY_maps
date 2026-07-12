"""Таблицы дожития: из однолетних mx (HMD) - 5-летние коэффициенты
передвижки и целевое масштабирование смертности к заданному e0.

Методика:
  qx = mx/(1+(1-ax)*mx), a0 = 0.14 (младенческая), иначе 0.5;
  Lx = l(x+1) + ax*(lx - l(x+1)); 5-летние nLx суммированием;
  переходы: S_g = nL(g+1)/nL(g) для групп до 70-74 -> 75-79;
  открытый интервал (стандарт ООН): P80+(t+5) = (P75-79 + P80+) * T80/T75,
  где T75 = nL(75-79) + T80;
  доживание родившихся за шаг до группы 0-4: nL(0-4) / (5*l0).

Масштабирование к целевому e0: mx' = mx*k, k бисекцией - монотонное
документированное упрощение вместо Ли-Картера (кросс-проверки - в тестах).
"""
from __future__ import annotations

from . import AGE_GROUPS, STEP


def _lx_Lx(mx: list[float]) -> tuple[list[float], list[float]]:
    n = len(mx)
    lx = [100000.0]
    for a in range(n):
        m = max(mx[a], 0.0)
        ax = 0.14 if a == 0 else 0.5
        qx = min(m / (1 + (1 - ax) * m), 1.0)
        lx.append(lx[-1] * (1 - qx))
    Lx = []
    for a in range(n):
        ax = 0.14 if a == 0 else 0.5
        Lx.append(lx[a + 1] + ax * (lx[a] - lx[a + 1]))
    return lx, Lx


def e0(mx: list[float]) -> float:
    _, Lx = _lx_Lx(mx)
    return sum(Lx) / 100000.0


def scale_to_e0(mx: list[float], target: float) -> list[float]:
    """mx * k, k бисекцией до |e0(mx*k) - target| < 0.001.

    Возвращается k, при котором e0 фактически попал в допуск (или последняя
    середина за 60 итераций). Важно НЕ пересчитывать k=(lo+hi)/2 после цикла:
    при раннем выходе это дало бы непроверенную середину суженного интервала,
    далёкую от сошедшегося k (баг: ошибка e0 до ~8 лет для отдельных таргетов).
    """
    lo, hi = 0.05, 5.0
    k = (lo + hi) / 2
    for _ in range(60):
        k = (lo + hi) / 2
        cur = e0([m * k for m in mx])
        if cur > target:
            lo = k
        else:
            hi = k
        if abs(cur - target) < 1e-3:
            break
    return [m * k for m in mx]


def survival_5y(mx: list[float]) -> dict:
    """5-летние коэффициенты передвижки для CCMPP."""
    _, Lx = _lx_Lx(mx)
    n_groups = len(AGE_GROUPS)              # 17 (0-4 ... 80+)
    nL = [sum(Lx[g * STEP:(g + 1) * STEP]) for g in range(n_groups - 1)]  # до 75-79
    T80 = sum(Lx[80:])
    T75 = nL[-1] + T80
    S = [nL[g + 1] / nL[g] for g in range(len(nL) - 1)]  # 15: 0-4->5-9 ... 70-74->75-79
    return {
        "S": S,
        "S_open": min(T80 / T75, 1.0) if T75 else 0.0,
        "L0_5l0": nL[0] / (STEP * 100000.0),
    }
