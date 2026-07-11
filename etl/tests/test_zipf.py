"""Тесты INF-01 zipf: эстиматор, известные значения, эквивалентность
автономного кода пакета и модуля etl.zipf, свежесть zipf.json."""
import json
import math
import subprocess
import sys

import pytest

from etl.common import RAW, OUT, ROOT
from etl.zipf import gi_fit, compute


@pytest.fixture(scope="session")
def zipf():
    return compute()


def test_gi_estimator_exact_on_gi_synthetic():
    """На P_r = C/(r-1/2) регрессия log(rank-1/2)~log(pop) линейна точно."""
    pops = [1_000_000 / (r - 0.5) for r in range(1, 31)]
    fit = gi_fit(pops)
    assert abs(fit["b"] + 1.0) < 1e-9
    assert abs(fit["se"] - math.sqrt(2 / 30)) < 1e-9


def test_known_slopes_and_primacy(zipf):
    py = zipf["perYear"]
    assert py["2019"]["slopes"]["30"]["b"] == pytest.approx(-0.9651, abs=1e-4)
    assert py["1897"]["slopes"]["30"]["b"] == pytest.approx(-1.1324, abs=1e-4)
    assert py["2026"]["primacy"] == pytest.approx(3.991, abs=1e-3)
    assert len(zipf["years"]) == 12
    # в 1897 нет N=50 (только 43 города)
    assert "50" not in py["1897"]["slopes"]
    # послевоенный перелом примации
    assert py["1939"]["primacy"] < 2 < py["1959"]["primacy"]


def test_top_lists_sorted(zipf):
    for y, d in zipf["perYear"].items():
        pops = [p for _, p in d["top"]]
        assert all(a >= b for a, b in zip(pops, pops[1:])), y
        assert d["top"][0][0] == "c-minsk", y


def test_published_zipf_json_is_fresh(zipf):
    """web/public/data/zipf.json обязан соответствовать пересчёту из raw."""
    published = json.loads((OUT / "zipf.json").read_text())
    assert published == json.loads(json.dumps(zipf)), (
        "zipf.json устарел: запустите python -m etl.zipf")


def test_package_code_equivalent_to_etl(tmp_path, zipf):
    """Автономный build.py пакета воспроизводит те же наклоны, что etl.zipf."""
    subprocess.run(
        [sys.executable, str(ROOT / "artifacts/zipf/code/build.py"),
         "--source", str(RAW / "ps_cities.html"), "--out", str(tmp_path)],
        check=True, capture_output=True)
    import csv
    with open(tmp_path / "zipf_slopes.csv") as f:
        pkg = {(r["year"], r["top_n"]): float(r["slope"]) for r in csv.DictReader(f)}
    for y, d in zipf["perYear"].items():
        for n, s in d["slopes"].items():
            assert pkg[(y, n)] == pytest.approx(s["b"], abs=1e-4), (y, n)
