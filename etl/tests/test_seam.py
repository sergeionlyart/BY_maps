"""INF-20 «Шов на карте»: инварианты таблицы ячеек и итогов (стандартная библиотека)."""
from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CELLS = ROOT / "data" / "raw" / "seam" / "cells.csv.gz"
SEAM = ROOT / "web" / "public" / "data" / "seam.json"
SEGS = ["PL", "LT", "LV", "RU", "UA"]

# Ключевые τ основной спецификации (h = 25 км), заморожены при выпуске v1.0.0.
FROZEN = {
    ("C_0319", "LT"): 13.369, ("C_0319", "LV"): 6.933, ("C_0319", "RU"): -5.139,
    ("C_0319", "PL"): 0.296, ("lvl_crop19", "RU"): -17.610, ("lvl_crop19", "UA"): -13.430,
    ("L_1924", "UA"): -0.268, ("B_9015", "LT"): 0.387,
}


def _seam():
    return json.loads(SEAM.read_text(encoding="utf-8"))


def test_cells_table_shape_and_signs():
    with gzip.open(CELLS, "rt", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        cols = rd.fieldnames
        n = mism = 0
        sides, segs = set(), set()
        for r in rd:
            n += 1
            sides.add(r["side"]); segs.add(r["seg"])
            if (r["side"] == "BY") != (float(r["d_km"]) < 0):
                mism += 1
    assert n == 234_491
    for c in ("d_km", "wsf_1990", "wsf_2015", "li_2019", "li_2024", "crop_2003", "crop_2019",
              "vnl_2019", "built_1975", "pop_2020", "subseg"):
        assert c in cols
    assert sides == {"BY", *SEGS}
    assert segs == set(SEGS)
    assert mism <= 5          # расхождения источников линии у самой границы (в бублике)


def test_every_main_estimate_present():
    d = _seam()
    main = {(e["outcome"], e["seg"]) for e in d["estimates"] if e["spec"] == "main" and e.get("tau") is not None}
    for y in d["meta"]["outcomes"]:
        for s in SEGS:
            assert (y, s) in main, (y, s)


def test_frozen_key_estimates():
    d = _seam()
    got = {(e["outcome"], e["seg"]): e["tau"] for e in d["estimates"] if e["spec"] == "main"}
    for k, v in FROZEN.items():
        assert abs(got[k] - v) < 0.002, (k, got[k], v)


def test_hypotheses_verdicts_frozen():
    h = _seam()["hypotheses"]
    assert h["H1"]["verdict"] == "не подтверждена"
    assert h["H2"]["verdict"] == "не подтверждена"
    assert h["H3"]["verdict"] == "не подтверждена"
    assert h["H4"]["verdict"] == "подтверждена"
    assert "H5" in h


def test_placebo_borders_near_zero_for_crop():
    """Ложные границы в 30 км для главного результата (пашня) — без значимого скачка."""
    d = _seam()
    for s in ("LT", "LV", "RU"):
        for spec in ("placebo_by", "placebo_nb"):
            e = next(x for x in d["estimates"] if x["outcome"] == "C_0319" and x["seg"] == s and x["spec"] == spec)
            assert e["p"] is None or e["p"] >= 0.05, (s, spec, e)
