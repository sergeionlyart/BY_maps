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
    add("national_pw_density_1975", nat["population_weighted_density"]["1975"], 0.01,
        "плотность, взвешенная по населению, 1975")
    add("national_pw_density_2020", nat["population_weighted_density"]["2020"], 0.01,
        "плотность, взвешенная по населению, 2020")
    add("national_arith_density_1990", nat["arithmetic_density"]["1990"], 0.01,
        "арифметическая плотность страны, 1990 (пик наблюдаемого ряда)")
    add("national_arith_density_2020", nat["arithmetic_density"]["2020"], 0.01,
        "арифметическая плотность страны, 2020")

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

    net_path = SRC / "network_metrics.json"
    if net_path.exists():
        net = json.loads(net_path.read_text())
        add("g6_road_km_total", net["g6"]["osm_total_km"], 1.0,
            "суммарная длина дорожной сети OSM (motorway..tertiary), км")
        add("g6_delta_pct", net["g6"]["delta_pct"], 0.01,
            "отклонение суммы OSM от официальной статистики протяжённости дорог, %")
        add("g6_pass", 1 if net["g6"]["passed"] else 0, 0,
            "G-6 пройдена (1) или нет (0) - допуск ±15% к офиц. статистике")
        add("c3_spearman_rho", net["correlation_c3"]["spearman_rho"], 0.001,
            "корреляция Спирмена network_per_capita vs темп убыли района (C-3)")
        add("c3_p_value_log10", round(math.log10(net["correlation_c3"]["p_value"]), 1), 0.5,
            "log10(p-value) корреляции C-3 (значение очень мало - сравниваем в лог-масштабе)")

    (FINAL / "computed_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    print(f"OK: {len(results)} контрольных метрик -> data/final/computed_results.json")


if __name__ == "__main__":
    main()
