"""Тесты INF-09 `shocks`. Приёмка из TASK_SPEC: каждая карточка события
с ≥1 проверяемым источником; язык ≠ этничность (оговорка); чувствительные
темы фактологически."""
import csv
import hashlib
import json

import pytest

from etl.common import ROOT
from etl.shocks import build, SERIES_YEARS

RAW = ROOT / "data" / "raw" / "shocks"


@pytest.fixture(scope="session")
def result():
    return build()


@pytest.fixture(scope="session")
def published():
    return json.loads((ROOT / "web/public/data/shocks.json").read_text())


def test_registry_checksums():
    """sha256 сырья зафиксированы в реестре."""
    reg = {r["notes"]: r for r in csv.DictReader(open(RAW / "registry.csv"))}
    for f in RAW.glob("*.json"):
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        assert reg[f.name]["sha256"] == h, f.name


def test_series_wwii_break(result):
    """Национальный ряд: обрыв ВМВ (1940 > 1950, ≈ 1,3 млн)."""
    s = result["series"]
    assert s["1940"] > s["1950"]
    loss = s["1940"] - s["1950"]
    assert 1_200_000 < loss < 1_500_000, loss
    # довоенной численности достигли лишь в начале 1970-х (1970 ещё ниже)
    assert s["1959"] < s["1940"] and s["1970"] < s["1940"] <= s["1979"]


def test_events_sourced(result):
    """Каждое событие с ≥1 источником; годы упорядочены и в диапазоне."""
    events = result["events"]
    assert len(events) >= 7
    prev = 0
    for e in events:
        assert len(e.get("sources", [])) >= 1, e["title"]
        assert 1900 <= e["year"] <= 2000
        assert e["year"] >= prev
        prev = e["year"]
        if e.get("year_end"):
            assert e["year_end"] >= e["year"]


def test_census_1897_shares(result):
    """Доли евреев в [0,100], пересчитываются из языковых чисел;
    местечки (55-90%) присутствуют - Пинск/Слуцк/Слоним."""
    cities = result["census1897"]
    assert len(cities) >= 30
    for c in cities:
        assert 0 <= c["jewishShare"] <= 100
        assert abs(c["jewishShare"] - c["jewish"] / c["total"] * 100) < 0.1
    top = {c["ru"]: c["jewishShare"] for c in cities[:8]}
    assert any(v >= 70 for v in top.values())
    # отсортировано по убыванию доли
    shares = [c["jewishShare"] for c in cities]
    assert shares == sorted(shares, reverse=True)


def test_holocaust_composition(result):
    """Холокост: доля-1897 как мера утраченного; население из рядов
    проекта; сортировка по доле."""
    towns = result["holocaust"]
    assert len(towns) >= 15
    for t in towns:
        if t["jewishShare1897"] is not None:
            assert 0 <= t["jewishShare1897"] <= 100
        assert len(t.get("sources", [])) >= 1, t["ru"]
    # Пинск - местечко с высокой долей
    pinsk = next((t for t in towns if t["id"] == "c-pinsk"), None)
    assert pinsk and pinsk["jewishShare1897"] and pinsk["jewishShare1897"] >= 60
    # регрессия аудита: доля Холокост-города согласована с переписью
    # проекта (пересчёт идиш/всё), а не со скопированным % к иной базе
    census = {c["id"]: c["jewishShare"] for c in result["census1897"] if c["id"]}
    census.update({c["ru"]: c["jewishShare"] for c in result["census1897"]})
    for t in towns:
        cs = census.get(t["id"]) or census.get(t["ru"])
        if cs is not None:
            assert t["jewishShare1897"] == cs, (t["ru"], t["jewishShare1897"], cs)
            assert t["shareBasis"].startswith("перепись")
        else:
            assert t["shareBasis"] == "оценка источника"


def test_map_cities_have_coords(result):
    """Города-1897 с id проекта несут координаты для карты."""
    withcoord = [c for c in result["census1897"] if c["lat"] and c["lon"]]
    assert len(withcoord) >= 20


def test_published_consistency(result, published):
    assert published["version"]
    assert published["series"]["1940"] == result["series"]["1940"]
    assert len(published["events"]) == len(result["events"])
    assert len(published["census1897"]) == len(result["census1897"])
