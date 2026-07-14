"""Тесты INF-08 v2 «Беларусь из космоса, 1992-2075».

Приёмка ТЗ: стык DMSP/VIIRS R² >= 0,9 и разрыв <= 5%; 119 зон без
пропусков на всём ряду; сумма районов = страна в допуске; параметры
модели зафиксированы и воспроизводимы; кадры <= 150 КБ и всегда
маркируют будущее; спайк-обоснование отказа от «готового» продукта.
"""
import csv
import json
import math
import statistics
from collections import defaultdict

import pytest

from etl.common import ROOT
from etl import nightlights_harmonize as H
from etl import nightlights_model as M

RAW = ROOT / "data" / "raw" / "nightlights"
FRAMES = ROOT / "web" / "public" / "data" / "nl_frames"

DMSP_YEARS = list(range(1992, 2014))
VNL_YEARS = list(range(2012, 2025))


def _zonal(fname, col):
    zones, by = defaultdict(dict), {}
    for r in csv.DictReader(open(RAW / fname)):
        y, v = int(r["year"]), float(r[col])
        if r["zone_id"] == "BY":
            by[y] = v
        else:
            zones[r["zone_id"]][y] = v
    return zones, by


@pytest.fixture(scope="session")
def dmsp():
    return _zonal("zonal_dmsp.csv", "dn_sum")


@pytest.fixture(scope="session")
def vnl():
    return _zonal("zonal_vnl.csv", "radiance")


@pytest.fixture(scope="session")
def assump():
    return M.load_assumptions()


@pytest.fixture(scope="session")
def validation():
    return H.validation()


@pytest.fixture(scope="session")
def published():
    return json.loads(
        (ROOT / "web/public/data/nightlights_v2.json").read_text())


# ---------- T-1: реестр и вырезки ----------

def test_registry_v2_complete():
    reg = {r["id"]: r for r in csv.DictReader(open(RAW / "registry_v2.csv"))}
    for y in DMSP_YEARS:
        for key in (f"li_caldmsp_{y}", f"clip_dmsp_{y}"):
            assert key in reg and len(reg[key]["sha256"]) == 64, key
        assert (RAW / "rasters" / f"dmsp_{y}.tif").exists()
    for y in VNL_YEARS:
        for key in (f"vnl_avg_{y}", f"clip_vnl_{y}"):
            assert key in reg and len(reg[key]["sha256"]) == 64, key
        assert (RAW / "rasters" / f"vnl_{y}.tif").exists()
    for r in reg.values():
        assert r["license"], r["id"]


# ---------- T-3: зональный ряд ----------

def test_zonal_coverage_nonempty(dmsp, vnl):
    """119 зон x все годы сегмента, ни одного нулевого зоно-года."""
    for zones, years in [(dmsp[0], DMSP_YEARS), (vnl[0], VNL_YEARS)]:
        assert len(zones) == 119
        assert sum(1 for z in zones if z.startswith("r-")) == 118
        assert "BY-HM" in zones
        for z, ser in zones.items():
            assert set(ser) == set(years), z
            assert all(v > 0 for v in ser.values()), (z, ser)


def test_zone_sum_equals_country(dmsp, vnl):
    """Сумма 119 зон = страна (строка BY шире на приграничные пиксели
    маски all_touched; допуск 1%)."""
    for zones, by in [dmsp, vnl]:
        for y, tot in by.items():
            s = sum(zones[z][y] for z in zones)
            assert 0.99 <= s / tot <= 1.0 + 1e-9, (y, s / tot)


def test_minsk_two_brightest_vnl(vnl):
    for y in VNL_YEARS:
        top2 = sorted(vnl[0], key=lambda z: -vnl[0][z][y])[:2]
        assert set(top2) == {"BY-HM", "r-minski"}, (y, top2)


def test_units_monotone(vnl):
    """lit_km2 положительна и не превосходит площадь зоны (грубая
    верхняя граница - площадь страны)."""
    for r in csv.DictReader(open(RAW / "zonal_vnl.csv")):
        v = float(r["lit_km2"])
        assert 0 <= v < 208_000, r


# ---------- T-2: гармонизация ----------

def test_harmonization_gates(validation):
    """Гейты ТЗ: R² перекрытия продуктов >= 0,9; разрыв нац. суммы на
    стыке (out-of-sample, симметричные окна) <= 5%."""
    br = validation["bridge"]
    assert br["r2"] >= H.R2_GATE, br
    assert abs(validation["seam_gap"]) <= H.SEAM_GATE, \
        validation["seam_gap"]
    assert 0.5 < br["b"] < 2.5
    assert 0.3 < validation["f18"] < 0.8   # F18-эра ~2x ярче


def test_spike_justifies_own_splice(validation):
    """Обоснование отказа от «готового» simVIIRS: нулевые зоно-годы
    (нестабильность малых зон - урок v1) и волатильность долей выше,
    чем у фактического VNL."""
    sp = validation["spike"]
    assert sp["zero_zone_years_sim"] > 0
    assert sp["zero_zone_years_vnl"] == 0
    assert sp["vol_ratio"] > 1.0, sp


def test_harmonized_series_continuous(validation):
    """Гармонизированный нац. ряд непрерывен: есть все годы 1992-2024,
    все положительны."""
    nat = validation["nat_harmonized"]
    assert sorted(nat) == list(range(1992, 2025))
    assert all(v > 0 for v in nat.values())


# ---------- T-4: модель ----------

def test_floor_partition(vnl):
    """floor + bright = зональная радиансность 2024 (точное разбиение
    по порогу; допуск - округление CSV)."""
    fl = M.load_floor()
    assert len(fl) == 119
    for z, f in fl.items():
        tot = vnl[0][z][2024]
        assert abs(f["floor"] + f["bright"] - tot) <= 0.01 + tot * 1e-6, z


def test_beta_stored_matches_estimate(assump):
    """industrial/rural - межрайонная оценка (допуск округления);
    урбан-классы - принятая пропорциональность 1,0 (не идентифицируются,
    см. beta_comment)."""
    cross = M.estimate_beta_cross(assump)
    stored = assump["model"]["beta"]
    assert abs(stored["industrial"] - cross["industrial"]["beta"]) < 0.05
    assert abs(stored["rural"] - cross["rural"]["beta"]) < 0.05
    assert stored["minsk_agglo"] == 1.0
    assert stored["oblast_center"] == 1.0
    for c, v in stored.items():
        assert 0.0 <= v <= 3.0, (c, v)


def test_future_light_sane(assump):
    fut = M.future_light(assump)
    fl = M.load_floor()
    nodes = fut["nodes"]
    for j in M.JUMPOFFS:
        for s in M.SCENARIOS:
            for z, ser in fut["light"][j][s].items():
                for t, v in ser.items():
                    assert v >= fl[z]["floor"] - 1e-9, (j, s, z, t)
    # сценарная монотонность: население negative <= optimistic =>
    # модельный свет negative <= optimistic (beta >= 0)
    for z in fut["light"]["official"]["negative"]:
        neg = fut["light"]["official"]["negative"][z][nodes[-1]]
        opt = fut["light"]["official"]["optimistic"][z][nodes[-1]]
        assert neg <= opt + 1e-9, z


def test_adjusted_close_to_official(assump):
    """Анкер adjusted-ветки согласован (знаменатель pop2024 умножен на
    отношение adjusted/official на старте прогноза): национальный
    adjusted <= official на первом узле, по зонам расхождение только
    за счёт ДИНАМИКИ рядов (допуск 2%; систематического уровневого
    сдвига нет)."""
    fut = M.future_light(assump)
    t0, t1 = fut["nodes"][0], fut["nodes"][-1]
    nat_a = sum(v[t0] for v in fut["light"]["adjusted"]["base"].values())
    nat_o = sum(v[t0] for v in fut["light"]["official"]["base"].values())
    assert nat_a <= nat_o + 1e-6
    assert nat_o / nat_a - 1 < 0.02   # анкер: сдвиг уровня устранён
    for z in fut["light"]["official"]["base"]:
        for t in (t0, t1):
            a = fut["light"]["adjusted"]["base"][z][t]
            o = fut["light"]["official"]["base"][z][t]
            assert a <= o * 1.02 + 1e-9, (z, t, a, o)


# ---------- T-5/T-13: финальный набор и кадры ----------

def test_published_structure(published):
    assert published["version"].startswith("2.")
    assert published["yearsObs"] == list(range(1992, 2025))
    assert published["nodes"] == assumptions_nodes()
    assert len(published["rows"]) == 119
    for r in published["rows"]:
        for j in ("official", "adjusted"):
            for s in ("base", "negative", "optimistic"):
                assert len(r["model"][j][s]) == 10, (r["id"], j, s)


def assumptions_nodes():
    return M.load_assumptions()["model"]["nodes"]


def test_published_shares_sum_to_one(published):
    for y in (1992, 2011, 2012, 2024):
        s = sum(r["lshare"].get(str(y), 0) for r in published["rows"])
        assert abs(s - 1.0) < 2e-3, (y, s)


def test_frames_exist_and_light(published):
    """Кадры: 33 наблюдения + 60 модельных; <= 150 КБ (ТЗ T-5);
    у модельных - имена с сценарием и стартом (маркировка T-13
    впечатана рендером; наличие бейджа проверяется рендер-тестом
    пикселей ниже)."""
    meta = json.loads((FRAMES / "meta.json").read_text())
    assert meta["width"] > 0 and len(meta["bounds"]) == 4
    names = [f"y{y}.png" for y in range(1992, 2025)]
    names += [f"m{t}_{s}_{j}.png"
              for j in ("official", "adjusted")
              for s in ("base", "negative", "optimistic")
              for t in assumptions_nodes()]
    for n in names:
        p = FRAMES / n
        assert p.exists(), n
        assert p.stat().st_size <= 150 * 1024, (n, p.stat().st_size)


def test_model_frames_carry_badge():
    """T-13: модельный кадр отличается от «чистого» рендера поля -
    в правом верхнем углу впечатан бейдж (непустая плашка): проверяем,
    что в зоне бейджа есть непалитровые светлые пиксели."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow не установлен")
    p = FRAMES / "m2075_base_official.png"
    img = Image.open(p).convert("RGB")
    w = img.width
    box = img.crop((w - 360, 0, w, 90))
    px = [box.getpixel((x, y)) for y in range(0, box.height, 2)
          for x in range(0, box.width, 2)]
    bright = sum(1 for c in px if c[0] > 180 and c[1] > 140)
    assert bright > 12, "бейдж МОДЕЛЬ не найден в углу кадра"
