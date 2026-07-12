"""Вероятностный слой прогноза (этап 3): гейты Монте-Карло-веера.

Приёмка: (1) 80% интервал страны совпадает с 80% PI WPP-2024 на 2050 и 2075
(калибровка, а не пропорциональный перенос); (2) веер монотонен и брекетит
детерминированную медиану; (3) симуляция воспроизводима при фиксированном
сиде; (4) области симулируются независимо (сумма медиан ≈ страна)."""
import pytest

from etl.forecast import TERRITORIES, probabilistic as prob
from etl.forecast.run import load_scenarios, run_scenario, EXPORT_YEARS


@pytest.fixture(scope="session")
def ens():
    return prob.ensemble()


@pytest.fixture(scope="session")
def fan(ens):
    return prob.quantile_fan(ens)


def _interp(pts, y):
    if y in pts:
        return pts[y]
    lo = max(x for x in pts if x <= y)
    hi = min(x for x in pts if x >= y)
    return pts[lo] + (y - lo) / (hi - lo) * (pts[hi] - pts[lo])


def test_wpp_calibration_gate(fan):
    """80% симуляции в 1,5 п.п. от 80% PI WPP на 2050 и 2075."""
    val = prob.wpp_validation(fan)
    for y in ("2051", "2075"):
        assert abs(val[y]["sim80"] - val[y]["wpp80"]) <= 0.015, (y, val[y])


def test_fan_monotone_and_brackets_base(fan):
    """q05<=q10<=q25<=q50<=q75<=q90<=q95; детерминированный base в [q10,q90]."""
    det = run_scenario(load_scenarios()["base"])
    qs = ["q05", "q10", "q25", "q50", "q75", "q90", "q95"]
    for t in TERRITORIES + ["BY"]:
        for i, y in enumerate(EXPORT_YEARS):
            row = [fan[t][q][i] for q in qs]
            assert row == sorted(row), (t, y, row)
            d = _interp(det[t], y)
            assert fan[t]["q10"][i] <= d <= fan[t]["q90"][i], (t, y)


def test_reproducible_seed():
    """Одинаковый сид -> идентичный ансамбль (байт-воспроизводимость пакета)."""
    a = prob.ensemble(n=60, seed=123)["BY"][2075]
    b = prob.ensemble(n=60, seed=123)["BY"][2075]
    assert a == b
    c = prob.ensemble(n=60, seed=124)["BY"][2075]
    assert a != c


def test_oblast_medians_sum_to_country(fan):
    """Области симулируются каждая (не пропорциональный перенос):
    сумма медиан областей ≈ медиана страны в 0,5%."""
    i = EXPORT_YEARS.index(2075)
    s = sum(fan[t]["q50"][i] for t in TERRITORIES)
    assert abs(s / fan["BY"]["q50"][i] - 1) < 0.005


def test_uncertainty_grows_with_horizon(fan):
    """Веер расширяется к горизонту (80% ширина 2075 > 2051 > 2031)."""
    def w(y):
        i = EXPORT_YEARS.index(y)
        return fan["BY"]["q90"][i] - fan["BY"]["q10"][i]
    assert w(2075) > w(2051) > w(2031) > 0
