#!/usr/bin/env python3
"""Инварианты пакета ML-challenger. Без pytest: plain asserts.
Проверяют структуру и — главное — ЧЕСТНОСТЬ: на перемешанной мишени
пайплайн не должен выдумывать сигнал (OOF R2 в нуль-полосе)."""
import json
import math
import random
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PKG))

from etl import challenger as ch  # noqa: E402


def test_panel_and_target():
    p = ch.build_panel()
    assert len(p["ids"]) == 118 and p["ids"] == sorted(p["ids"])
    assert len(ch.FEATURES) == 12 and ch.FEATURES == ch.EXO + ch.CTRL
    for row in p["X"]:
        assert all(math.isfinite(v) for v in row)
    # мишень = ln(факт/CCR), внутриобластная, малая и центрированная
    for i, t in enumerate(p["ids"]):
        assert abs(p["y"][i] - math.log(p["fact"][t] / p["ccr"][t])) < 1e-9
    assert abs(sum(p["y"]) / len(p["y"])) < 0.05


def test_leave_one_oblast_out():
    p = ch.build_panel()
    folds = ch._folds(p["ids"], p["oblast"])
    assert len(folds) == 6
    seen = set()
    for o, tr, te in folds:
        seen |= set(te)
        assert all(p["oblast"][p["ids"][i]] == o for i in te)
        assert all(p["oblast"][p["ids"][i]] != o for i in tr)
    assert seen == set(range(118))


def test_no_false_signal_on_shuffle():
    """Перемешали мишень -> OOF R2 падает в нуль-полосу (не фабрикуем сигнал)."""
    p = ch.build_panel()
    _, best_m, _ = ch.cv_oof(p["X"], p["y"], p["ids"], p["oblast"], ch.GB)
    rng = random.Random(7)
    worst = -9.9
    for _ in range(6):
        order = list(range(118))
        rng.shuffle(order)
        yp = [p["y"][k] for k in order]
        oof = ch._cv_oof_at(p["X"], yp, p["ids"], p["oblast"], ch.GB, best_m)
        worst = max(worst, ch._r2(yp, oof))
    assert worst < 0.20, worst


def test_deterministic():
    p = ch.build_panel()
    a = ch.cv_oof(p["X"], p["y"], p["ids"], p["oblast"], ch.GB)
    b = ch.cv_oof(p["X"], p["y"], p["ids"], p["oblast"], ch.GB)
    assert a[0] == b[0] and a[1] == b[1]


def test_contributions_additive():
    p = ch.build_panel()
    m = ch.GBoost(**{**ch.GB, "n_estimators": 40}).fit(p["X"], p["y"])
    for i in (0, 60, 117):
        c = ch.contributions(m, p["X"][i])
        assert abs(sum(c.values()) - (m.predict(p["X"][i]) - m.base)) < 1e-4


def test_published_json():
    d = json.loads((PKG / "web/public/data/mlchallenger.json").read_text())
    assert d["n"] == 118 and len(d["districts"]) == 118
    assert (d["permutationNull"]["p"] < 0.05) == d["signalDetected"]
    assert d["mapeHorserace"]["naive"] > d["mapeHorserace"]["ccr"]
    assert d["window"].startswith("2019")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"Все {len(fns)} инвариантов выполнены.")
