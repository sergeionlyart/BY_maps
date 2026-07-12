"""Тесты ML-challenger (этап 8): диагностика ошибок CCR градиентным бустингом.

Приёмка: (1) панель полна и без утечки будущего; (2) бустинг детерминирован
и байт-воспроизводим; (3) на ПЕРЕМЕШАННОЙ мишени OOF-скилл падает в нуль-
полосу (пайплайн не выдумывает сигнал); (4) на реальной мишени сигнал есть
и гейтится перестановочным нулём; (5) аддитивные вклады суммируются в
(pred-base); (6) опубликованный mlchallenger.json согласован."""
import json
import math
import random

import pytest

from etl.common import ROOT
from etl import challenger as ch


@pytest.fixture(scope="session")
def panel():
    return ch.build_panel()


@pytest.fixture(scope="session")
def published():
    return json.loads((ROOT / "web/public/data/mlchallenger.json").read_text())


def test_panel_complete(panel):
    """118 районов, 12 признаков, все конечны; мишень — ln(факт/CCR)."""
    assert len(panel["ids"]) == 118
    assert panel["ids"] == sorted(panel["ids"])
    assert ch.FEATURES == ch.EXO + ch.CTRL and len(ch.FEATURES) == 12
    for row in panel["X"]:
        assert len(row) == 12
        assert all(math.isfinite(v) for v in row)
    for i, t in enumerate(panel["ids"]):
        assert abs(panel["y"][i] - math.log(panel["fact"][t] / panel["ccr"][t])) < 1e-9
    # мишень мала и центрирована (внутриобластная ошибка распределения)
    m = sum(panel["y"]) / len(panel["y"])
    assert abs(m) < 0.05


def test_folds_leave_one_oblast_out(panel):
    """6 областных фолдов; район никогда не в своём train."""
    folds = ch._folds(panel["ids"], panel["oblast"])
    assert len(folds) == 6                       # Минск-город не район
    seen = set()
    for o, tr, te in folds:
        assert te, o
        seen |= set(te)
        for i in te:
            assert panel["oblast"][panel["ids"][i]] == o
        for i in tr:
            assert panel["oblast"][panel["ids"][i]] != o
    assert seen == set(range(len(panel["ids"])))  # каждый район ровно в одном тесте


def test_deterministic(panel):
    """Одинаковый сид -> идентичные OOF (байт-воспроизводимость пакета)."""
    a = ch.cv_oof(panel["X"], panel["y"], panel["ids"], panel["oblast"], ch.GB)
    b = ch.cv_oof(panel["X"], panel["y"], panel["ids"], panel["oblast"], ch.GB)
    assert a[0] == b[0] and a[1] == b[1]


def test_no_false_signal_on_shuffled_target(panel):
    """КЛЮЧЕВОЙ гейт честности: на перемешанной мишени OOF R2 (против чистого
    CCR) не превышает малый порог — пайплайн не фабрикует сигнал из шума."""
    y = panel["y"]
    _, best_m, _ = ch.cv_oof(panel["X"], y, panel["ids"], panel["oblast"], ch.GB)
    rng = random.Random(123)
    r2s = []
    for _ in range(8):
        order = list(range(len(y)))
        rng.shuffle(order)
        yp = [y[k] for k in order]
        oof = ch._cv_oof_at(panel["X"], yp, panel["ids"], panel["oblast"], ch.GB, best_m)
        r2s.append(ch._r2(yp, oof))
    # на шуме OOF R2 около нуля/отрицателен (нуль-полоса), заведомо < реального 0.33
    assert max(r2s) < 0.20, r2s
    assert sum(r2s) / len(r2s) < 0.05, r2s


def test_real_signal_exists(panel):
    """На реальной мишени экзогенные признаки дают положительный OOF-скилл
    заметно выше нуля (иначе вердикт был бы нулевым — тоже валиден, но здесь
    проверяем воспроизводимость обнаруженного сигнала)."""
    oof, best_m, _ = ch.cv_oof(panel["X"], panel["y"], panel["ids"], panel["oblast"], ch.GB)
    r2 = ch._r2(panel["y"], oof)
    assert 0.15 < r2 < 0.6, r2      # диапазон вокруг наблюдённого 0.33
    assert 10 <= best_m <= 250, best_m


def test_contributions_sum_to_pred(panel):
    """Аддитивное разложение суммируется в (pred - base)."""
    m = ch.GBoost(**{**ch.GB, "n_estimators": 40}).fit(panel["X"], panel["y"])
    for i in (0, 40, 80, 117):
        x = panel["X"][i]
        contrib = ch.contributions(m, x)
        # вклады округлены до 5 знаков в выдаче -> бюджет округления 12*5e-6
        assert abs(sum(contrib.values()) - (m.predict(x) - m.base)) < 1e-4


def test_published_consistency(published):
    p = published
    assert p["version"] == "1.0.0"
    assert p["n"] == 118 and len(p["districts"]) == 118
    assert isinstance(p["signalDetected"], bool)
    assert p["permutationNull"]["p"] <= 1.0
    # вердикт согласован с гейтом
    assert (p["permutationNull"]["p"] < 0.05) == p["signalDetected"]
    # веер квантилей прогноза сюда не подмешан — только диагностика
    assert p["window"].startswith("2019")
    # каждый район несёт знаковую ошибку CCR и OOF-предсказание
    for d in p["districts"][:20]:
        assert set(d) >= {"id", "oblast", "ccrResid", "oofPred", "topDrivers"}
    # гонка MAPE присутствует и понижена (CCR+ML не хуже наивной)
    h = p["mapeHorserace"]
    assert h["naive"] > h["ccr"]
