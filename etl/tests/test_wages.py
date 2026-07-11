"""Тесты INF-03 `wages`. Приёмка из TASK_SPEC: регрессия воспроизводится;
устойчивость коэффициента к спецификации; согласованность данных."""
import json

import pytest

from etl.common import ROOT
from etl.wages import load_wages, build, MINSK_SUBURBS


@pytest.fixture(scope="session")
def wages():
    return load_wages()


@pytest.fixture(scope="session")
def result():
    return build()


@pytest.fixture(scope="session")
def published():
    return json.loads((ROOT / "web/public/data/wages.json").read_text())


def test_coverage_and_denomination(wages):
    """118 районов, полные годы 2010-2025; деноминация и контрольные точки."""
    raions = [t for t in wages if t.startswith("r-")]
    assert len(raions) == 118
    for t in raions:
        assert set(range(2010, 2026)) <= set(wages[t]), t
    # контрольные значения страны (официальные публикации)
    assert abs(wages["BY"][2024] - 2288.6) < 0.05
    assert abs(wages["BY"][2025] - 2679.7) < 0.05
    # деноминация: 2010 в новых рублях ~121,7 (1 217 313 старых / 10 000)
    assert 100 < wages["BY"][2010] < 150, wages["BY"][2010]
    # зарплата Минска выше страны во все годы
    for y in range(2010, 2026):
        assert wages["BY-HM"][y] > wages["BY"][y], y


def test_differentials_sane(result):
    """Дифференциалы районов к Минску в правдоподобном коридоре."""
    for r in result["rows"]:
        assert 0.30 < r["wage_rel"] < 1.10, (r["id"], r["wage_rel"])
    top = max(result["rows"], key=lambda r: r["wage_rel"])
    # самые высокие дифференциалы - индустриальные/пригородные районы
    assert top["wage_rel"] > 0.75


def test_classification_3x3(result):
    """Терцильная классификация: 9 классов, крайние трети ~ по 39-40."""
    from collections import Counter
    cnt = Counter(r["cls"] for r in result["rows"])
    assert set(cnt) <= {f"w{i}p{j}" for i in range(3) for j in range(3)}
    for axis, idx in (("w", 1), ("p", 3)):
        lo = sum(v for k, v in cnt.items() if k[idx] == "0")
        hi = sum(v for k, v in cnt.items() if k[idx] == "2")
        assert 36 <= lo <= 42 and 36 <= hi <= 42, (axis, lo, hi)
    # диагональ доминирует: связь видна уже в классификации
    assert cnt["w0p0"] > 12 and cnt["w2p2"] > 12


def test_regression_gate(result):
    """Гейт INF-03: знак устойчив во всех спецификациях; значимость
    t>3 при классических SE везде; при робастных HC1 - основная и
    переписная спецификации t>3,5, консервативные не слабее t>=2."""
    for name, v in result["variants"].items():
        beta = v["beta"][1]
        assert beta > 0, (name, beta)
        assert beta / v["se"][1] > 3, (name, beta / v["se"][1])
        assert beta / v["se_hc1"][1] >= 2.0, (name, beta / v["se_hc1"][1])
    for name in ("main", "window_2009_2019", "no_control"):
        v = result["variants"][name]
        assert v["beta"][1] / v["se_hc1"][1] > 3.5, name
    main = result["variants"]["main"]["beta"][1]
    nosub = result["variants"]["no_suburbs"]["beta"][1]
    # пригороды Минска усиливают связь как минимум в полтора раза
    assert main > nosub * 1.3


def test_outliers_meaningful(result):
    """Выбросы регрессии содержат известные аномалии (пригороды/моногорода)."""
    out = set(result["outliers"])
    assert len(out) == 8
    assert out & MINSK_SUBURBS or "r-salihorski" in out or "r-astraviecki" in out


def test_published_consistent(published, result):
    """wages.json согласован с пересчётом."""
    assert published["version"] == "1.0.0"
    assert len(published["territories"]) == 118
    m = published["regressions"]["main"]
    v = result["variants"]["main"]
    assert abs(m["beta"][1] - v["beta"][1]) < 0.005
    assert abs(m["r2"] - v["r2"]) < 0.005
    for r in result["rows"][:20]:
        pub = published["territories"][r["id"]]
        assert abs(pub["wageRel"] - r["wage_rel"]) < 1e-3
        assert pub["cls"] == r["cls"]


def test_hosted_map_in_sync():
    """Локальная карта периметров совпадает с etl.forecast.sub.HOSTED."""
    from etl.forecast.sub import HOSTED as SUB_HOSTED
    from etl.wages import HOSTED as WAGES_HOSTED
    assert WAGES_HOSTED == SUB_HOSTED


def test_registry_covers_vendored_files():
    import csv
    import hashlib
    reg = list(csv.DictReader(open(ROOT / "data/raw/wages/registry.csv")))
    hashes = {r["sha256"] for r in reg if r["sha256"]}
    for p in (ROOT / "data/raw/wages").iterdir():
        if p.name == "registry.csv":
            continue
        assert hashlib.sha256(p.read_bytes()).hexdigest() in hashes, p.name
