"""Тесты INF-08 `nightlights`. Приёмка из TASK_SPEC: растровая обработка
воспроизводится скриптом (версии композитов + chksum); методблок
перечисляет причины ложных расхождений; свет — только индикатор
расхождения, не оценка численности."""
import csv
import hashlib
import json
import math
import statistics

import pytest

from etl.common import ROOT
from etl.nightlights import build, load_zonal, TREND_YEARS, SHOCK_YEARS, YEARS

RAW = ROOT / "data" / "raw" / "nightlights"


@pytest.fixture(scope="session")
def result():
    return build()


@pytest.fixture(scope="session")
def published():
    return json.loads((ROOT / "web/public/data/nightlights.json").read_text())


def test_registry_and_checksum():
    """Приёмка: версии композитов (URL+sha256) и sha256 зональной
    суммы зафиксированы в реестре."""
    reg = {r["id"]: r for r in csv.DictReader(open(RAW / "registry.csv"))}
    for y in YEARS:
        key = f"worldpop_viirs_fvf_{y}"
        assert key in reg, key
        assert reg[key]["url"].startswith("https://data.worldpop.org")
        assert len(reg[key]["sha256"]) == 64
    zc = hashlib.sha256((RAW / "zonal_light.csv").read_bytes()).hexdigest()
    assert reg["zonal_light"]["sha256"] == zc


def test_coverage_no_zero_years():
    """119 зон (118 районов + Минск) x 9 лет без пропусков и нулевых
    лет — в отличие от отвергнутого смоделированного продукта."""
    light = load_zonal()
    assert len(light) == 119
    raions = [z for z in light if z.startswith("r-")]
    assert len(raions) == 118 and "BY-HM" in light
    for z, ser in light.items():
        assert set(ser) == set(YEARS), z
        assert all(v > 0 for v in ser.values()), z


def test_minsk_brightest():
    """Минск и Минский район - два ярчайших источника (столица и её
    промышленное кольцо периодически меняются местами)."""
    light = load_zonal()
    for y in YEARS:
        top2 = sorted(light, key=lambda z: -light[z][y])[:2]
        assert set(top2) == {"BY-HM", "r-minski"}, (y, top2)


def test_share_stability():
    """Доли зон устойчивы год к году (гашение версионных скачков);
    CV доли Минска мал (< 0,15) — сигнал, а не шум продукта."""
    light = load_zonal()
    nat = {y: sum(light[z][y] for z in light) for y in YEARS}
    msh = [light["BY-HM"][y] / nat[y] for y in YEARS]
    cv = statistics.pstdev(msh) / statistics.mean(msh)
    assert cv < 0.15, cv


def test_divergence_index(result):
    """Индекс = ln(доля света_ф/тренд) - ln(доля насел._ф/тренд);
    воспроизводим; крупные районы осмысленны."""
    rows = {r["id"]: r for r in result["rows"]}
    withdiv = [r for r in result["rows"] if r["div"] is not None]
    assert len(withdiv) >= 115
    for r in withdiv:
        rec = math.log(r["lightRatio"]) - math.log(r["popRatio"])
        assert abs(rec - r["div"]) < 1e-3, r["id"]
    # Минск почти не расходится (свет столицы держится вровень с людьми)
    assert abs(rows["BY-HM"]["div"]) < 0.15
    # индустриальные районы гаснут сильнее населения (свет < 1, div < 0)
    for z in ("r-smalavicki", "r-barysauski", "r-homielski"):
        assert rows[z]["div"] < -0.1, z
        assert rows[z]["lightRatio"] < 1.0, z


def test_reliable_less_noisy(result):
    """Малые сельские районы шумнее крупных (обоснование фокуса на
    надёжных): медиана |индекса| у малых выше, чем у крупных."""
    withdiv = [r for r in result["rows"] if r["div"] is not None]
    def size(r):
        return statistics.mean(r["light"][str(y)] for y in TREND_YEARS)
    med = statistics.median(size(r) for r in withdiv)
    small = [abs(r["div"]) for r in withdiv if size(r) < med]
    large = [abs(r["div"]) for r in withdiv if size(r) >= med]
    assert statistics.median(small) > statistics.median(large)


def test_windows_disjoint_and_pre_shock():
    """Окна тренда (2015-2019) и шока (2022-2023) не пересекаются;
    версионный скачок VNL 2021 вне обоих."""
    assert set(TREND_YEARS).isdisjoint(SHOCK_YEARS)
    assert max(TREND_YEARS) < min(SHOCK_YEARS)
    assert 2021 not in TREND_YEARS and 2021 not in SHOCK_YEARS


def test_published_consistency(result, published):
    assert published["version"]
    assert published["trendYears"] == [TREND_YEARS[0], TREND_YEARS[-1]]
    assert published["shockYears"] == SHOCK_YEARS
    pub = {r["id"]: r for r in published["rows"]}
    for r in result["rows"]:
        if r["div"] is not None:
            assert abs(pub[r["id"]]["div"] - r["div"]) < 1e-9, r["id"]
