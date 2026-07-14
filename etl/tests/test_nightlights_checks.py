"""Тесты внешней проверки H1-H3 (R4): структура, вердикты, источники."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
NL = ROOT / "web" / "public" / "data" / "nightlights"
CHECKS_RAW = ROOT / "data" / "raw" / "nightlights" / "checks"

CAUSAL_RU = ["из-за", "вызвано", "привело", "потому что", "по причине"]


def _data():
    return json.loads((NL / "external_checks.json").read_text())


def test_structure():
    d = _data()
    assert len(d["cases"]) == 3
    ids = {c["caseId"] for c in d["cases"]}
    assert ids == {"minsk-agglomeration", "smolevichi-zhodino", "astravets"}
    for c in d["cases"]:
        assert len(c["checks"]) >= 3
        for ch in c["checks"]:
            assert ch["verdict"] in ("consistent", "inconsistent", "context")
            assert ch["source"].startswith("Белстат")
            assert "unit" in ch


def test_verdict_rules_present_and_no_causal_wording():
    d = _data()
    txt = json.dumps(d, ensure_ascii=False).lower()
    for w in CAUSAL_RU:
        assert w not in txt, f"причинная формулировка «{w}»"
    for c in d["cases"]:
        for ch in c["checks"]:
            if ch["verdict"] != "context":
                assert ch.get("rule"), f"вердикт без правила: {ch['metric']}"


def test_electricity_is_context_not_overclaim():
    """Ряд генерации обрывается до выхода АЭС на мощность - вердикт
    обязан быть контекстным, не «согласуется»."""
    d = _data()
    h3 = next(c for c in d["cases"] if c["caseId"] == "astravets")
    el = [ch for ch in h3["checks"]
          if ch["metric"] == "electricity_production_oblast"]
    assert el and el[0]["verdict"] == "context"


def test_periods_match_candidates():
    d = _data()
    cands = {c["id"]: c for c in json.loads(
        (NL / "research_candidates.json").read_text())["candidates"]}
    for c in d["cases"]:
        assert c["period"] == cands[c["caseId"]]["period"]
        assert c["lightResidualPct"] == \
            cands[c["caseId"]]["metrics"]["lightResidualPct"]


def test_registry_covers_raw_files():
    with open(CHECKS_RAW / "registry.csv") as f:
        reg = {r["file"]: r["sha256"] for r in csv.DictReader(f)}
    for p in CHECKS_RAW.glob("*.json"):
        assert p.name in reg, f"{p.name} нет в registry.csv"
        assert hashlib.sha256(p.read_bytes()).hexdigest() == reg[p.name], \
            f"sha256 не совпадает: {p.name}"


def test_reproducible():
    """Повторный расчёт даёт тот же JSON (детерминированность)."""
    import subprocess
    import sys
    before = (NL / "external_checks.json").read_bytes()
    subprocess.run([sys.executable, "-m", "etl.nightlights_checks"],
                   cwd=ROOT, check=True, capture_output=True)
    assert (NL / "external_checks.json").read_bytes() == before
