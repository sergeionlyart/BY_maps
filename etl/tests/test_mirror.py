"""Тесты WP-F3: зеркальная статистика и ряд adjusted.

Гейт приёмки TASK_SPEC: интервал не уже официально опубликованных
ориентиров (совокупный отток >= сток ВНЖ ЕС минус довоенный сток);
каждая компонента привязана к источнику (registry.csv)."""
import csv
import json

import pytest

from etl.common import ROOT
from etl.mirror import (eu_stocks, outflow_interval, territory_keys,
                        AGE_PROFILE, CNI_EU_SHARE, TIME_PROFILE)

CURATED = ROOT / "data" / "curated"


def test_eurostat_stocks_anchor():
    """Опорные значения Eurostat воспроизводятся из завендоренного сырья."""
    st = eu_stocks()
    assert st["EU27_2020"][2019] == 133_889
    assert st["EU27_2020"][2024] == 386_834
    assert st["PL"][2022] == 301_611
    assert st["LT"][2024] == 58_632


def test_interval_acceptance_gate():
    """Гейт WP-F3: интервал накрывает сток ЕС минус довоенный сток
    и официальный ориентир МВД (350 тыс.); low < mid < high."""
    iv = outflow_interval()
    st = eu_stocks()
    raw_gain = st["EU27_2020"][2024] - st["EU27_2020"][2019]
    assert iv["low"] < iv["mid"] < iv["high"]
    assert iv["low"] <= raw_gain <= iv["high"], (iv, raw_gain)
    assert iv["low"] <= 350_000 <= iv["high"]
    assert 150_000 < iv["low"] < 250_000
    assert 350_000 < iv["high"] < 500_000


def test_profiles_sum_to_one():
    assert abs(sum(AGE_PROFILE.values()) - 1.0) < 1e-9
    assert abs(sum(TIME_PROFILE.values()) - 1.0) < 1e-9
    assert abs(sum(territory_keys().values()) - 1.0) < 1e-9
    assert 0.7 < CNI_EU_SHARE < 0.85


def test_adjustment_csv_consistent():
    """adjustment.csv: страна = сумма территорий; 2026 = полный интервал."""
    rows = list(csv.DictReader(open(CURATED / "adjustment.csv")))
    iv = outflow_interval()
    by_year: dict = {}
    for r in rows:
        by_year.setdefault(int(r["year"]), {})[r["territory_id"]] = {
            k: int(r[k]) for k in ("low", "mid", "high")}
    for y, terrs in by_year.items():
        for k in ("low", "mid", "high"):
            s = sum(v[k] for t, v in terrs.items() if t != "BY")
            assert abs(s - terrs["BY"][k]) <= 5, (y, k)
    assert abs(by_year[2026]["BY"]["mid"] - iv["mid"]) <= 1
    assert by_year[2020]["BY"]["mid"] == 0  # на 01.01.2020 поправки нет


def test_forecast_adjusted_block():
    """forecast.json: ряд adjusted есть для уровней 0-1, старт = официальный
    минус mid-поправка; official-ряды не изменились."""
    fc = json.loads((ROOT / "web/public/data/forecast.json").read_text())
    assert fc["version"] == "v2026.3"
    assert fc["jumpoff"] == ["official", "adjusted"]
    assert "adjusted" in fc and "adjustedMeta" in fc
    iv = outflow_interval()
    for t in ["BY", "BY-HM", "BY-VI"]:
        off = fc["territories"][t]["base"]["pop"][0]
        adj = fc["adjusted"][t]["base"]["pop"][0]
        assert adj < off, t
    d_by = fc["territories"]["BY"]["base"]["pop"][0] - \
        fc["adjusted"]["BY"]["base"]["pop"][0]
    assert abs(d_by - iv["mid"]) < 100, (d_by, iv["mid"])
    # official-контрольные значения этапа 5 не тронуты
    e = fc["territories"]["BY"]["base"]
    assert dict(zip(e["years"], e["pop"]))[2051] == 7_528_557
    # у районов adjusted-ряда нет (поправка - до уровня областей)
    assert "r-minski" not in fc["adjusted"]
    # сценарии упорядочены и в adjusted
    for t in ["BY", "BY-HM"]:
        o = fc["adjusted"][t]["optimistic"]["pop"][-1]
        b = fc["adjusted"][t]["base"]["pop"][-1]
        n = fc["adjusted"][t]["negative"]["pop"][-1]
        assert o >= b >= n, t


def test_registry_covers_vendored_files():
    """Каждый завендоренный файл сырья упомянут в registry.csv c sha256."""
    import hashlib
    reg = list(csv.DictReader(open(ROOT / "data/raw/mirror/registry.csv")))
    hashes = {r["sha256"] for r in reg if r["sha256"]}
    for p in (ROOT / "data/raw/mirror").iterdir():
        if p.name == "registry.csv":
            continue
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        assert h in hashes, p.name
