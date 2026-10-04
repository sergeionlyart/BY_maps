"""Тесты INF-21 (sensors): гейты V-1…V-5, формулы, окна, вердикты.

Пререгистрация: docs/preregistration/sensors-v0.1.md (с поправкой 1 от
2026-10-04: окна O/G 1990-2020 — без Дрибинского района).
"""
import json
import math

import pytest

from etl.common import ROOT
from etl.sensors import (LIGHT_SEAMS, WIN_L_DMSP, WIN_L_POST, WIN_L_PRE, WIN_OG,
                         build, crosses_seam, dlog, median, shares, spearman)

OUT = ROOT / "web" / "public" / "data"
CURATED = ROOT / "data" / "curated"
PREREG = ROOT / "docs" / "preregistration" / "sensors-v0.1.md"


@pytest.fixture(scope="module")
def res():
    return build()


# ------------------------------------------------------------ юнит-тесты

def test_shares_sum_to_one():
    s = shares({"a": 1.0, "b": 3.0})
    assert s == {"a": 0.25, "b": 0.75}


def test_dlog_sign():
    assert dlog(0.1, 0.2) == pytest.approx(math.log(2))
    assert dlog(0.2, 0.1) < 0


def test_spearman_ties_and_perfect():
    assert spearman([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])[0] == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4, 5], [5, 4, 3, 2, 1])[0] == pytest.approx(-1.0)


def test_median():
    assert median([3, 1, 2]) == 2 and median([4, 1, 3, 2]) == 2.5


def test_seam_rule():
    """Окно огней не может пересекать стыки сенсоров (пререгистрация, п.5)."""
    assert crosses_seam((2010, 2013))          # DMSP/VIIRS
    assert crosses_seam((2019, 2022))          # смена обработки VNL
    for w in (WIN_L_PRE, WIN_L_POST, WIN_L_DMSP):
        assert not crosses_seam(w), w
    assert LIGHT_SEAMS == [(2011, 2012), (2020, 2021)]


# ------------------------------------------------------- гейты публикации

@pytest.mark.parametrize("gate", ["V-1", "V-2", "V-3", "V-4", "V-5"])
def test_gates_pass(res, gate):
    assert res["gates"][gate]["pass"], res["gates"][gate]


def test_v5_only_dribin_missing_from_og_window(res):
    """Поправка 1: из окна 1990-2020 выпадает только Дрибинский район
    (восстановлен в 1989, официальный ряд с 1991)."""
    g = res["gates"]["V-5"]
    assert g["og_1990_2020_missing"] == ["r-drybinski"]
    assert g["og_2000_2020_missing"] == []
    t = res["territories"]["r-drybinski"]
    assert t["dO_9020"] is None and t["d_9020"] is None
    assert t["dO_0020"] is not None and t["dL_1319"] is not None


# --------------------------------------------------------- содержательное

def test_verdicts_are_locked(res):
    """Вердикты закреплены: H1 подтверждена, H2-H4 опровергнуты. Тест
    падает, если опровержения исчезнут из публикации при будущих правках."""
    f = res["findings"]
    assert f["H1"]["verdict"] == "confirmed" and f["H1"]["n"] == 117
    assert f["H1"]["rho"] >= 0.60
    for h in ("H2", "H3", "H4"):
        assert f[h]["verdict"] == "refuted", h
    assert f["H2"]["rho"] < 0.40


def test_h2_refutation_is_not_harmonization_artifact(res):
    """Доли INF-08 (lshare) и сырые радиансы VIIRS отличаются не более чем
    на 2 % — опровержение H2 не создано гармонизацией INF-08."""
    for y, dev in res["summary"]["vnl_raw_vs_lshare_max_pct"].items():
        assert dev < 2.0, (y, dev)


def test_posthoc_labelled_and_levels_agree(res):
    ph = res["posthoc"]
    assert "пост-хок" in ph["disclaimer"].lower()
    # свет хорошо показывает, ГДЕ живут люди (уровни)…
    for y, r in ph["level_rho_light_vs_pop"].items():
        assert r >= 0.80, (y, r)
    # …но не КУДА они уходят (изменения): в медианном районе разный знак
    assert ph["median_dO_1319"] < 0 < ph["median_dL_1319"]


def test_windows_frozen(res):
    assert res["windows"]["OG"] == list(WIN_OG) == [1990, 2020]
    assert res["windows"]["L_pre"] == [2013, 2019]
    assert res["windows"]["L_post"] == [2021, 2024]


def test_export_and_csv(res):
    exported = json.loads((OUT / "sensors.json").read_text())
    for k in ("version", "code", "territories", "findings", "gates", "posthoc",
              "summary", "windows"):
        assert k in exported, k
    assert exported["code"] == "INF-21"
    assert len(exported["territories"]) == 118
    import csv
    with open(CURATED / "sensors.csv", encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == 118


def test_preregistration_amendment_present():
    text = PREREG.read_text(encoding="utf-8")
    assert "2026-10-04, поправка 1" in text
    assert "(пусто — поправок нет)" not in text
