#!/usr/bin/env python3
"""Быстрый режим воспроизведения INF-15 «Полотно»: пересчитывает итоговые
контрольные числа из ЗАВЕНДОРЕННЫХ промежуточных агрегатов (sources/raw/*),
без rasterio/scipy/Pillow. Полное пересоздание клеток из тайлов GHS-POP -
отдельный, тяжёлый режим (см. README.md, требует code/requirements.lock
"полный режим").

Только стандартная библиотека (csv, json, pathlib) - тот же принцип, что и
у пакета urban-overhang (etl/urban.py).
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
SRC = PKG / "sources" / "raw"
FINAL = PKG / "data" / "final"

EPOCHS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020]


def load_json(name: str) -> dict:
    return json.loads((SRC / name).read_text())


def load_csv(name: str) -> list[dict]:
    with (SRC / name).open() as f:
        return list(csv.DictReader(f))


def main() -> None:
    FINAL.mkdir(parents=True, exist_ok=True)
    observed = load_json("metrics_observed.json")
    forecast = load_json("metrics_forecast.json")
    g3 = load_json("g3_nightlights_crosscheck.json")
    recon = load_csv("reconciliation.csv")

    results = []

    def add(metric, value, tolerance, description):
        results.append({"metric": metric, "value": value, "tolerance": tolerance,
                        "description": description})

    nat = observed["national"]
    add("national_below5_1975", nat["area_share_below"]["5"]["1975"], 0.0001,
        "доля площади страны с плотностью <5 чел/км², 1975 (constrained)")
    add("national_below5_2020", nat["area_share_below"]["5"]["2020"], 0.0001,
        "доля площади страны с плотностью <5 чел/км², 2020 (constrained)")
    add("national_below1_2020", nat["area_share_below"]["1"]["2020"], 0.0001,
        "доля площади страны с плотностью <1 чел/км², 2020 (доработка v1.1.0, B-8)")
    add("national_pw_density_1975", nat["population_weighted_density"]["1975"], 0.01,
        "плотность, взвешенная по населению, 1975")
    add("national_pw_density_2020", nat["population_weighted_density"]["2020"], 0.01,
        "плотность, взвешенная по населению, 2020")
    add("national_arith_density_1975", nat["arithmetic_density"]["1975"], 0.01,
        "арифметическая плотность страны, 1975 (доработка v1.1.0, находка на странице)")
    add("national_arith_density_1990", nat["arithmetic_density"]["1990"], 0.01,
        "арифметическая плотность страны, 1990 (пик наблюдаемого ряда)")
    add("national_arith_density_2020", nat["arithmetic_density"]["2020"], 0.01,
        "арифметическая плотность страны, 2020")

    nat_f = forecast["national"]
    add("national_below5_2050_base_A", nat_f["area_share_below"]["5"]["2050:base:A"], 0.0001,
        "доля площади страны с плотностью <5 чел/км², 2050 базовый/A (доработка v1.1.0, находка на странице)")
    add("national_pw_density_2050_base_A", nat_f["population_weighted_density"]["2050:base:A"], 0.01,
        "плотность, взвешенная по населению, 2050 базовый/A (доработка v1.1.0, находка на странице)")

    summary = observed["reconciliation_summary"]
    add("g1_n_failed_raions_ever", summary["n_failed_raions_ever"], 0,
        "районов, вышедших за допуск ±3% хотя бы в одной эпохе (сырой продукт, до калибровки)")
    max_raw_pct = max(abs(float(r["pct_diff"])) for r in recon if r["pct_diff"])
    add("g1_raw_max_abs_pct_diff", round(max_raw_pct, 2), 0.5,
        "максимальное |отклонение| сырого grid_sum от офиц. ряда района по всем эпохам")

    g2 = forecast["g2_report_summary"]
    add("g2_max_pct_diff", g2["max_pct_diff"], 0.1,
        "макс. отклонение суммы клеток района от прогноза района (все сценарии/варианты)")

    add("g3_pct_agree", g3["pct_agree"], 0.1,
        "согласие знака изменения население/огни 2012-2020, % районов")
    add("g3_n_raions", g3["n_raions"], 0,
        "районов, включённых в проверку G-3")

    g4 = observed["validation"]["g4_polesye_chernobyl"]
    add("g4_growth_1975_2020_excl_polesye_chernobyl", g4["growth_1975_2020"], 0.001,
        "рост area_share_below(5) 1975->2020 без Полесья и Чернобыля (36 районов)")

    g5 = observed["validation"]["g5_centroid_sensitivity"]
    add("g5_max_shift_km", g5["max_shift_km"], 0.1,
        "макс. сдвиг центра масс при альтернативных весах/пороге, км")

    sc2020 = nat["settlement_components"]["2020"]
    add("settlement_components_n_2020", sc2020["n_components"], 0,
        "число связных компонент расселения (порог 1 чел/км², 8-связность), 2020")
    add("settlement_components_largest_share_2020",
        round(sc2020["largest_share_of_pop"], 4), 0.001,
        "доля населения в крупнейшей компоненте, 2020")
    add("settlement_components_largest_area_share_2020",
        round(sc2020["largest_share_of_area"], 5), 0.001,
        "доля площади страны в крупнейшей компоненте расселения, 2020 (доработка v1.1.0, находка на странице)")

    net_path = SRC / "network_metrics.json"
    if net_path.exists():
        net = json.loads(net_path.read_text())
        add("g6_road_km_total", net["g6"]["osm_total_km"], 1.0,
            "суммарная длина дорожной сети OSM (motorway..tertiary), км")
        add("g6_road_km_official", net["g6"]["official_total_km"], 1.0,
            "официальная длина дорожной сети (РУП «Белдорцентр»), км (доработка v1.1.0)")
        add("g6_delta_pct", net["g6"]["delta_pct"], 0.01,
            "отклонение суммы OSM от официальной статистики протяжённости дорог, %")
        add("g6_pass", 1 if net["g6"]["passed"] else 0, 0,
            "G-6 пройдена (1) или нет (0) - допуск ±15% к офиц. статистике")
        add("c3_spearman_rho", net["correlation_c3"]["spearman_rho"], 0.001,
            "корреляция Спирмена network_per_capita vs темп убыли района (C-3)")
        add("c3_p_value_log10", round(math.log10(net["correlation_c3"]["p_value"]), 1), 0.5,
            "log10(p-value) корреляции C-3 (значение очень мало - сравниваем в лог-масштабе)")

    story_path = SRC / "story_metrics.json"
    if story_path.exists():
        story = json.loads(story_path.read_text())

        c004 = story["c004_density_bands"]["bands"]
        band_names = ["1_5", "5_25", "25_100", "100_500", "500_2000", "2000plus"]
        for name, b in zip(band_names, c004):
            add(f"c004_band{name}_change_pct", b["change_pct"], 0.05,
                f"C-004: изменение населения в клетках {b['lo']}-{b['hi'] or '2000+'} чел/км², "
                "1975->2020, %")

        c005 = story["c005_highway_distance"]["bands"]
        hw_names = ["0_2", "2_5", "5_10", "10_20", "20plus"]
        for name, b in zip(hw_names, c005):
            add(f"c005_band{name}_change_pct", b["change_pct"], 0.05,
                f"C-005: изменение населения в клетках {b['lo']}-{b['hi'] or '20+'} км "
                "от магистрали, 1975->2020, %")

        half = story["half_population_area_km2"]
        add("half_population_area_km2_1975", half["1975"], 0,
            "площадь, вмещающая половину населения страны, 1975, км²")
        add("half_population_area_km2_2020", half["2020"], 0,
            "площадь, вмещающая половину населения страны, 2020, км²")
        add("half_population_area_km2_2050_base_A", half["2050:base:A"], 0,
            "площадь, вмещающая половину населения страны, 2050 базовый/A, км²")

        raions = story["raions"]
        deepest = min(raions["shrunk_most"], key=lambda r: r["change_pct"])
        top_growth = max(raions["grew_most"], key=lambda r: r["change_pct"])
        add("raion_deepest_decline_change_pct", deepest["change_pct"], 0.05,
            f"{deepest['name_ru']}, изменение населения 1975->2020, % (глубочайший спад)")
        add("raion_top_growth_change_pct", top_growth["change_pct"], 0.05,
            f"{top_growth['name_ru']}, изменение населения 1975->2020, % (наибольший рост)")
        add("n_raions_shrunk", raions["n_raions_shrunk"], 0,
            "районов (из 118) с сокращением населения 1975->2020")
        add("n_raions_shrunk_40pct_or_more", raions["n_raions_shrunk_40pct_or_more"], 0,
            "районов с сокращением населения на 40% и более")

    g9_path = SRC / "g9_concentration_check.json"
    if g9_path.exists():
        g9 = json.loads(g9_path.read_text())
        by_year = g9["national_mean_top5_share_by_year"]
        add("g9_top5_share_1975", by_year["1975"], 0.0005,
            "G-9: средняя по стране доля населения района в топ-5 самых плотных клетках, 1975")
        add("g9_top5_share_2020", by_year["2020"], 0.0005,
            "G-9: то же, 2020 (почти не изменилось за 45 лет)")
        add("g9_top5_share_2050_base_A", g9["national_mean_top5_share_2050_base_a"], 0.0005,
            "G-9: то же, 2050 базовый/A - модель прогнозирует резкий скачок (см. D-013)")
        add("g9_n_raions_violated", g9["n_raions_violated"], 0,
            "G-9: районов, где прогнозный темп концентрации превышает исторический максимум "
            "в 3+ раза")
        add("g9_pct_raions_violated", g9["pct_raions_violated"], 0.1,
            "G-9: доля районов-нарушителей, %")
        add("g9_max_ratio_to_historical", g9["max_ratio_to_historical"], 0.05,
            "G-9: максимальное отношение прогнозного темпа к историческому по районам")
        add("g9_pass", 1 if g9["pass"] else 0, 0,
            "G-9 пройдена (1) или нет (0) - честно, по конструкции, не пройдена (см. D-013)")

    (FINAL / "computed_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    print(f"OK: {len(results)} контрольных метрик -> data/final/computed_results.json")


if __name__ == "__main__":
    main()
