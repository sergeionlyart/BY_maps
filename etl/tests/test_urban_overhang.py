"""Инварианты INF-12 «urban-overhang» (пререгистрация v0.1, §19 ТЗ)."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "urban"
CURATED = ROOT / "data" / "curated" / "urban"
FINAL = RAW / "final"
STORY = ROOT / "web" / "public" / "data" / "urban_overhang.json"

EPOCHS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020]
SCENARIOS = [f"t{t:02d}_c{c}" for t in (5, 10, 20) for c in (0, 1, 2)]

pytestmark = pytest.mark.skipif(
    not STORY.exists(), reason="конвейер INF-12 ещё не прогонялся")


def _csv(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def registry():
    return _csv(CURATED / "city_registry.csv")


@pytest.fixture(scope="module")
def story():
    return json.loads(STORY.read_text())


def test_registry_valid(registry):
    ids = [r["city_id"] for r in registry]
    assert len(ids) == len(set(ids)), "city_id уникальны"
    assert len(ids) >= 90
    for r in registry:
        lat, lon = float(r["lat"]), float(r["lon"])
        assert 51.0 < lat < 56.5 and 23.0 < lon < 33.0, r["city_id"]


def test_exclusions_have_reason():
    for r in _csv(CURATED / "exclusions.csv"):
        assert r["reason"], r["city_id"]
        assert r["date"]


def test_morph_coverage(registry):
    rows = _csv(RAW / "morph_city_epoch.csv")
    assert len(rows) == len(SCENARIOS) * len(EPOCHS) * len(registry)
    scen = {r["scenario"] for r in rows}
    assert scen == set(SCENARIOS)
    epochs = {int(r["epoch"]) for r in rows}
    assert epochs == set(EPOCHS), "эпохи 1975-2020; 2025/2030 GHSL не наблюдения"


def test_fixed_core_edge_additive():
    """built_fixed = ядро + край + буфер (зоны покрывают рамку без пересечений)."""
    for r in _csv(RAW / "morph_fixed.csv"):
        total = float(r["built_fixed_m2"])
        parts = (float(r["built_core_m2"]) + float(r["built_edge_m2"])
                 + float(r["built_buffer_m2"]))
        assert abs(total - parts) <= max(1.0, 1e-6 * total), \
            (r["city_id"], r["epoch"], r["scenario"])


def test_flows_nonnegative():
    for r in _csv(RAW / "morph_flows.csv"):
        assert float(r["infill_m2"]) >= 0
        assert float(r["edge_m2"]) >= 0


def test_negative_controls():
    """Вода/лес/болото не дают заметного «роста фонда» (< 1% бокса 9 км²)."""
    for r in _csv(RAW / "morph_qa.csv"):
        assert float(r["built_m2_3km_box"]) < 90_000, r


def test_metric_formulas(story):
    """BPC=B/P и MOR=BGR-PGR пересчитываются из публикуемых величин."""
    checked = 0
    for cid, c in story["cities"].items():
        m = c.get("main")
        if not m:
            continue
        # MOR = BGR - PGR (поля округлены до 5 знаков независимо)
        assert abs(m["mor"] - (m["bgr"] - m["pgr"])) < 1.5e-5, cid
        # BPC на концах интервала
        assert abs(m["bpc1990"] - m["b1990"] * 1e6 / m["p1990"]) < 0.6, cid
        assert abs(m["bpc2020"] - m["b2020"] * 1e6 / m["p2020"]) < 0.6, cid
        # интервал неопределённости содержит точечную оценку
        assert m["morLo"] - 1e-9 <= m["mor"] <= m["morHi"] + 1e-9, cid
        # лог-темпы согласованы с уровнями
        pgr = (math.log(m["p2020"]) - math.log(m["p1990"])) / 30
        assert abs(pgr - m["pgr"]) < 1e-4, cid
        checked += 1
    assert checked >= 80


def test_interval_shares(story):
    for cid, c in story["cities"].items():
        m = c.get("main")
        if not m or m.get("ees") is None:
            continue
        assert -1e-9 <= m["ees"] <= 1 + 1e-9, cid


def test_typology_codes():
    valid = {"T1", "T2", "T3", "T4", "T5", "T6", "TX"}
    rows = _csv(FINAL / "city_typology.csv")
    assert rows
    for r in rows:
        assert r["primary_type"] in valid, r
        assert r["quality_class"] in {"A", "B", "C", "X"}, r
        assert 0.0 <= float(r["agreement_score"]) <= 1.0


def test_no_financial_fields():
    """MVP не содержит денежных полей (§14.4 ТЗ)."""
    for path in [FINAL / "city_metrics.csv",
                 FINAL / "city_interval_metrics.csv",
                 FINAL / "city_typology.csv"]:
        header = path.read_text().splitlines()[0].lower()
        for bad in ("cost", "byn", "usd", "budget", "рубл"):
            assert bad not in header, (path.name, bad)


def test_story_consistency(story):
    nat = story["national"]
    cities = story["cities"]
    # национальная панель = города с метриками И классом A/B (C - карточка)
    assert nat["n_cities"] == sum(
        1 for c in cities.values()
        if c.get("main") and c["quality"] in ("A", "B"))
    assert story["epochs"] == EPOCHS
    # качество только A/B/C (X - в exclusions, не в story)
    assert all(c["quality"] in ("A", "B", "C") for c in cities.values())
    # выбранные кейсы существуют и содержат контрпример
    roles = {c["role"] for c in story["cases"]}
    assert "counterexample" in roles, "обязательный контрпример (§14.2 ТЗ)"
    for case in story["cases"]:
        assert case["city_id"] in cities
    # у сокращающихся с навесом MOR>0
    n_decl = nat["n_declining"]
    assert 0 < n_decl <= nat["n_cities"]
    assert 0 <= nat["n_overhang_robust"] <= n_decl


def test_computed_results_match_story(story):
    comp = {r["metric"]: r["value"] for r in
            json.loads((FINAL / "computed_results.json").read_text())}
    nat = story["national"]
    assert comp["n_cities"] == nat["n_cities"]
    assert comp["n_declining"] == nat["n_declining"]
    assert comp["n_overhang_robust"] == nat["n_overhang_robust"]
    for t, n in nat["type_counts"].items():
        assert comp[f"type_counts.{t}"] == n, t


def test_light_series_window():
    """Свет: DMSP только 1992-2013, VNL только 2012-2024."""
    rows = _csv(RAW / "city_light.csv")
    for r in rows:
        y = int(r["year"])
        if r["sensor"] == "dmsp":
            assert 1992 <= y <= 2013
        else:
            assert 2012 <= y <= 2024


def test_roads_current_slice_only():
    """Дорожный срез - современный: нет исторических годов в таблице."""
    path = RAW / "city_roads.csv"
    if not path.exists():
        pytest.skip("city_roads.csv ещё не создан")
    header = path.read_text().splitlines()[0]
    assert "year" not in header.lower()
    for r in _csv(path):
        assert float(r["length_km"]) >= 0
