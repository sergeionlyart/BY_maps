"""Тесты INF-08 v3: визуальный слой, delta, события, адаптивная скорость.

Критерии распоряжения: непрерывность лет; корректный источник каждого
года; единая сетка и отсутствие по-годовой нормализации (эталонные
sha256); корректность delta; исключение методологических переходов из
обычного скоринга; соответствие идентификаторов районов; события -
только из аналитического слоя; воспроизводимость генерации.
"""
import hashlib
import json

import pytest

from etl.common import ROOT

NL = ROOT / "web" / "public" / "data" / "nightlights"


@pytest.fixture(scope="session")
def manifest():
    return json.loads((NL / "nightlights_manifest.json").read_text())


@pytest.fixture(scope="session")
def events():
    return json.loads((NL / "nightlights_events.json").read_text())


@pytest.fixture(scope="session")
def annotations():
    return json.loads((NL / "nightlights_annotations.json").read_text())


@pytest.fixture(scope="session")
def night():
    return json.loads(
        (ROOT / "web/public/data/nightlights_v2.json").read_text())


# ---------- визуальный слой и манифест ----------

def test_manifest_years_continuous(manifest, night):
    """Непрерывность лет: 1992-2024 + все узлы модели x 6 комбинаций."""
    obs = sorted(f["year"] for f in manifest["frames"]
                 if f["sourceType"] != "modeled_forecast")
    assert obs == list(range(1992, 2025))
    model = [f for f in manifest["frames"]
             if f["sourceType"] == "modeled_forecast"]
    assert len(model) == len(night["nodes"]) * 6
    for f in model:
        assert f["scenario"] in night["scenarios"]
        assert f["jumpoff"] in night["jumpoffs"]


def test_manifest_source_types(manifest):
    """Тип источника каждого года: реконструкция до 2011, наблюдения
    2012-2024, модель дальше; обязательные поля провенанса."""
    for f in manifest["frames"]:
        y = f["year"]
        want = ("reconstructed_viirs_like" if y <= 2011
                else "observed_viirs" if y <= 2024
                else "modeled_forecast")
        assert f["sourceType"] == want, f
    for s in manifest["sources"]:
        for key in ("title", "url", "version", "license", "accessed",
                    "resolution", "files", "checksums"):
            assert s.get(key), (s["id"], key)


def test_manifest_assets_exist_and_match(manifest):
    """Файлы кадров существуют, sha256 совпадают с манифестом
    (детерминизм генерации / отсутствие ручных правок)."""
    for f in manifest["frames"]:
        p = NL / f["asset"].removeprefix("/data/nightlights/")
        assert p.exists(), f["asset"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == f["sha256"], \
            f["asset"]


def test_comparability_flags(manifest):
    """2011->2012 - смена источника: 2012 несопоставим с предыдущим;
    1992 - первый год; у остальных наблюдаемых лет referenceYear = y-1."""
    by_year = {f["year"]: f for f in manifest["frames"]
               if f["sourceType"] != "modeled_forecast"}
    assert by_year[1992]["comparableToPrevious"] is False
    assert by_year[2012]["comparableToPrevious"] is False
    assert "vnl_processing_step" in by_year[2021]["qualityFlags"]
    for y in range(1993, 2012):
        assert by_year[y]["comparableToPrevious"] is True
        assert by_year[y]["referenceYear"] == y - 1
    for f in manifest["frames"]:
        if f["sourceType"] == "reconstructed_viirs_like":
            assert "reconstruction" in f["qualityFlags"]


def test_unified_grid_and_no_per_year_normalization(manifest):
    """Единая сетка (равные размеры PNG) и фиксированная шкала:
    эталонные sha256 ключевых кадров (1992/2011/2012/2021/2024,
    модельные 2050/2075, сценарные дельты) - любое изменение рендера
    ловится, включая случайную по-годовую нормализацию."""
    refs = json.loads(
        (ROOT / "etl/tests/nightlights_v3_reference.json").read_text())
    for rel, want in refs.items():
        got = hashlib.sha256((NL / rel).read_bytes()).hexdigest()
        assert got == want, rel
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow не установлен")
    sizes = set()
    for rel in ["visual/reconstructed/1992.png", "visual/observed/2024.png",
                "visual/modeled/2075_base_official.png"]:
        with Image.open(NL / rel) as im:
            sizes.add(im.size)
    assert len(sizes) == 1, sizes
    g = manifest["grid"]
    assert (g["width"], g["height"]) in sizes


# ---------- delta ----------

def test_delta_index_assets(manifest):
    items = manifest["deltas"]["items"]
    assert len(items) > 300
    for i in items:
        p = NL / i["asset"].removeprefix("/data/nightlights/")
        assert p.exists(), i["asset"]
    # 2012 исключён из previous_year (смена источника), 1992 без базы
    prev_years = {i["year"] for i in items if i["kind"] == "previous_year"}
    assert 2012 not in prev_years and 1992 not in prev_years
    # кросс-источниковые пары помечены
    for i in items:
        if i["kind"] == "analysis_base":
            want = (i["year"] < 2012) != (i["refYear"] < 2012)
            assert i.get("crossSource") == want, i
        if i["kind"] == "base_2024":
            assert i.get("crossSource") is True


def test_delta_visual_regression():
    refs = json.loads(
        (ROOT / "etl/tests/nightlights_v3_reference.json").read_text())
    for rel, want in refs.items():
        if rel.startswith("delta/"):
            got = hashlib.sha256((NL / rel).read_bytes()).hexdigest()
            assert got == want, rel


# ---------- события ----------

def test_events_structure(events, night, annotations):
    kinds = {e["kind"] for e in events["events"]}
    assert "source_transition" in kinds
    assert "forecast_boundary" in kinds
    ids = {r["id"] for r in night["rows"]}
    for e in events["events"]:
        for r in e["regions"]:
            assert r["id"] in ids, r
            assert r["direction"] in ("rise", "fall")
        if e.get("annotationKey"):
            assert e["annotationKey"] in annotations
        for r in e["regions"]:
            if r.get("annotationKey"):
                assert r["annotationKey"] in annotations


def test_method_transitions_not_scored(events):
    """Методологические переходы и аномалии продукта не являются
    обычными событиями: 2012/2021/первый узел модели не имеют
    regional/national-событий."""
    for e in events["events"]:
        if e["year"] in (2012, 2021, 2030):
            assert e["kind"] in ("source_transition", "quality_note",
                                 "forecast_boundary"), e


def test_durations_cover_all_stops(events, night):
    stops = list(range(1992, 2025)) + night["nodes"]
    for y in stops:
        d = events["durationsMs"].get(str(y))
        assert d is not None and 300 <= d <= 1600, (y, d)


def test_events_reproducible(events, night):
    """Скоринг воспроизводим из аналитического слоя (детерминизм)."""
    from etl.nightlights_events import build
    fresh = build(night)
    assert fresh["events"] == events["events"]
    assert fresh["durationsMs"] == events["durationsMs"]


def test_no_generated_causes(events, annotations):
    """Причины не генерируются: у события либо нет annotationKey, либо
    он ссылается на ручную аннотацию с источником."""
    for e in events["events"]:
        keys = [e.get("annotationKey")] + \
            [r.get("annotationKey") for r in e["regions"]]
        for k in keys:
            if k:
                ann = annotations[k]
                assert ann.get("source") and ann.get("ru") and ann.get("be")
