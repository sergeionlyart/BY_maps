"""Тесты INF-21 (sexratio): гейты S-1…S-6, формулы, периметры, форма экспорта.

Пререгистрация: docs/preregistration/sexratio-v0.1.md (с тремя датированными
поправками от 2026-10-04 к гейтам S-2, S-4, S-6 — тесты проверяют именно
исправленные формулировки и то, что поправки в файле присутствуют).
"""
import json

import pytest

from etl.common import ROOT
from etl.sexratio import (AGE_GROUPS, CORE_SCENARIO, FERTILE, HOSTED, OLD,
                          _group_survival, _load_survival, _median, _ranks,
                          _ratio, _spearman, build)

OUT = ROOT / "web" / "public" / "data"
CURATED = ROOT / "data" / "curated"
PREREG = ROOT / "docs" / "preregistration" / "sexratio-v0.1.md"


@pytest.fixture(scope="module")
def res():
    return build()


@pytest.fixture(scope="module")
def exported():
    return json.loads((OUT / "sexratio.json").read_text())


# ------------------------------------------------------------ юнит-тесты

def test_ratio_formula():
    assert _ratio(100, 100) == 100.0
    assert _ratio(110, 100) == 110.0
    assert _ratio(0, 100) == 0.0
    assert _ratio(100, 0) is None, "деление на ноль не допускается"


def test_median_even_and_odd():
    assert _median([1, 2, 3]) == 2
    assert _median([1, 2, 3, 4]) == 2.5


def test_ranks_handle_ties():
    # две равные величины получают средний ранг - иначе Спирмен смещён
    assert _ranks([10, 20, 20, 30]) == [1.0, 2.5, 2.5, 4.0]


def test_spearman_perfect_monotone():
    rho, p = _spearman([1, 2, 3, 4, 5, 6, 7, 8], [2, 4, 6, 8, 10, 12, 14, 16])
    assert rho == pytest.approx(1.0)
    assert p < 0.05
    rho_rev, _ = _spearman([1, 2, 3, 4, 5, 6, 7, 8], [16, 14, 12, 10, 8, 6, 4, 2])
    assert rho_rev == pytest.approx(-1.0)


def test_survival_is_probability_and_male_mortality_is_higher():
    surv = _load_survival()
    for (sex, age), p in surv.items():
        assert 0.0 <= p <= 1.0, (sex, age, p)
    # сверхсмертность мужчин - основа H4; проверяем на рабочих возрастах
    for age in (20, 30, 40, 50, 60):
        assert surv[("m", age)] < surv[("f", age)], age


def test_group_survival_within_single_age_bounds():
    surv = _load_survival()
    for sex in ("m", "f"):
        for g in ("15-19", "25-29", "40-44"):
            start = int(g.split("-")[0])
            singles = [surv[(sex, start + k)] for k in range(5)]
            got = _group_survival(surv, sex, g)
            assert min(singles) <= got <= max(singles)


def test_age_group_sets_are_consistent():
    assert set(FERTILE) <= set(AGE_GROUPS)
    assert set(OLD) <= set(AGE_GROUPS)
    assert len(AGE_GROUPS) == 17


# ------------------------------------------------------- гейты публикации

def test_gate_s1_perimeter_matches_data_json(res):
    assert res["gates"]["S-1"]["pass"], res["gates"]["S-1"]["fails"][:5]


def test_gate_s2_country_sex_ratio(res):
    g = res["gates"]["S-2"]
    # поправка 1: диапазон 85-88 (официальный итог переписи 2019 - 85,9)
    assert g["range"] == [85.0, 88.0]
    assert g["pass"], g


def test_gate_s3_partition_is_closed(res):
    g = res["gates"]["S-3"]
    assert g["pass"], g
    # 118 районов + 12 городов = 6 областей; + Минск = страна
    for year, exp_country in (("2009", None), ("2019", 9_413_446)):
        row = g[year]
        assert row["raions_plus_cities"] == row["oblasts"]
        if exp_country:
            assert row["country"] == exp_country


def test_gate_s4_median_level_not_per_raion(res):
    """Поправка 2: соотношение 0-4 проверяется медианой по районам.

    Заодно фиксируем ПРИЧИНУ поправки: по отдельным районам условие
    102-108 не выполняется и в самой переписи - это малые числа, а не
    ошибка модели."""
    g = res["gates"]["S-4"]
    assert g["pass"], g
    assert g["census_2019"]["in_band"]
    assert g["census_2019"]["outside_pct"] > 15.0, (
        "если перепись внезапно уложилась в диапазон по районам, поправка 2 "
        "потеряла основание и её нужно пересмотреть")
    for row in g["forecast"]:
        assert row["in_band"], row
        assert abs(row["drift_from_census"]) <= 2.0, row
        assert row["excess_noise_pp"] <= 15.0, row


def test_gate_s5_decomposition_identity(res):
    assert res["gates"]["S-5"]["pass"], res["gates"]["S-5"]


def test_gate_s6_residual_size_and_age_profile(res):
    """Поправка 3: внутренние проверки вместо сверки с внешним сальдо."""
    g = res["gates"]["S-6"]
    assert g["pass"], g
    assert abs(g["net_residual_pct_of_covered"]) <= 5.0
    # остаток обязан концентрироваться в молодых возрастах, иначе это
    # не миграция, а ошибка таблиц смертности
    assert g["abs_residual_share_young_20_39_pct"] > \
        g["abs_residual_share_old_60plus_pct"]


# --------------------------------------------------------- содержательное

def test_hypotheses_have_explicit_verdicts(res):
    for h in ("H1", "H2", "H3", "H4"):
        assert res["findings"][h]["verdict"] in ("confirmed", "refuted")


def test_h1_is_refuted_with_opposite_sign(res):
    """H1 опровергнута: предсказывался положительный знак корреляции
    (дальше от Минска - сильнее мужской перевес), наблюдается
    отрицательный. Тест закрепляет сам факт опровержения, чтобы оно не
    исчезло из публикации при будущих правках."""
    h1 = res["findings"]["H1"]
    assert h1["verdict"] == "refuted"
    assert h1["spearman_rho"] < 0, "знак корреляции обратен предсказанному"
    assert h1["spearman_p"] < 0.05, "и при этом значим"


def test_h4_men_are_missing_everywhere_at_70plus(res):
    h4 = res["findings"]["H4"]
    assert h4["none_above_60"]
    assert h4["median_r70_2019"] < 50.0
    assert h4["median_rises"]


def test_posthoc_is_labelled_and_replicates_on_census_perimeter(res):
    """Пост-хок обязан быть помечен как пост-хок и не подменять H1."""
    ph = res["posthoc"]
    assert "пост-хок" in ph["disclaimer"].lower()
    cp = ph["census_perimeter_h1"]
    assert cp["n"] == 118, "Минский район не должен выпадать (min_minsk = 0)"
    assert cp["same_sign_as_forecast_perimeter"], (
        "обратный знак H1 не создан выбором периметра")
    # немонотонность: максимум не в самом дальнем поясе
    belts = ph["belts_median_r2539"]
    assert max(belts, key=lambda b: b["median"])["belt"] != "120-"


def test_every_raion_present_and_has_both_census_years(res):
    t = res["territories"]
    assert len(t) == 118
    for rid, row in t.items():
        for y in ("2009", "2019"):
            assert row["summary"][y]["r2539"] is not None, (rid, y)
        assert row["forecast_summary"][CORE_SCENARIO], rid
        assert row["be"] and row["ru"], rid


def test_hosted_copy_matches_wages():
    """Локальная копия карты районов-хостов обязана совпадать с etl.wages.

    Пакет sexratio автономен и зарплатный модуль не тянет, поэтому карта
    скопирована — расхождение копий молча сломало бы периметры."""
    from etl.wages import HOSTED as WAGES_HOSTED
    assert HOSTED == WAGES_HOSTED


def test_hosted_perimeter_rule_is_applied(res):
    """Правило сведения периметров: район-хост включает город.

    Контроль - население района в периметре прогноза должно совпадать с
    data.json, что уже проверяет S-1; здесь фиксируем, что карта HOSTED
    непуста и все её районы присутствуют в выгрузке."""
    assert HOSTED
    for rid in HOSTED:
        assert rid in res["territories"], rid


def test_export_shape(exported):
    for key in ("version", "code", "territories", "findings", "gates",
                "posthoc", "age_groups", "node_years", "core_scenario"):
        assert key in exported, key
    assert exported["code"] == "INF-21"
    assert exported["age_groups"] == AGE_GROUPS


def test_curated_csv_covers_all_raions():
    import csv
    with open(CURATED / "sexratio.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    ids = {r["territory_id"] for r in rows}
    assert len(ids) == 118
    kinds = {r["kind"] for r in rows}
    assert kinds == {"census", "forecast"}


def test_preregistration_amendments_are_dated_and_present():
    """Регламент: замороженная пререгистрация правится только датированными
    поправками. Три поправки к гейтам обязаны быть в файле."""
    text = PREREG.read_text(encoding="utf-8")
    assert "## Поправки" in text
    for n in ("поправка 1", "поправка 2", "поправка 3"):
        assert n in text, n
    assert text.count("2026-10-04, поправка") == 3
    assert "(пусто — поправок нет)" not in text
