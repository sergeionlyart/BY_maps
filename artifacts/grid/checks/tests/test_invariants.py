#!/usr/bin/env python3
"""Инварианты данных пакета INF-15 (автономно, stdlib, без pytest)."""
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[2]
RAW = PKG / "sources" / "raw"

EPOCHS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020]

failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        failures.append(msg)


observed = json.loads((RAW / "metrics_observed.json").read_text())
forecast = json.loads((RAW / "metrics_forecast.json").read_text())
g3 = json.loads((RAW / "g3_nightlights_crosscheck.json").read_text())

check(observed["epochs"] == EPOCHS, "эпохи наблюдений не совпадают с 1975-2020")
check(len(observed["territories"]) == 119, "территорий не 119 (118 районов + Минск)")

below5 = observed["national"]["area_share_below"]["5"]
vals = [below5[str(e)] for e in EPOCHS]
for i in range(1, len(vals)):
    check(vals[i] >= vals[i - 1] - 0.005,
          f"area_share_below(5) упало между {EPOCHS[i-1]} и {EPOCHS[i]}")

pw = observed["national"]["population_weighted_density"]
arith = observed["national"]["arithmetic_density"]
check(pw["2020"] > pw["1990"], "population_weighted_density не растёт 1990->2020")
check(arith["2020"] < arith["1990"], "arithmetic_density не падает 1990->2020")

summary = observed["reconciliation_summary"]
check(summary["n_failed_raions_ever"] > 15,
      "G-1: раздел 13 ТЗ применяется только если провалилось >15 районов")
check(summary["drop_raw_raion_numbers"] is True,
      "сырые районные числа должны быть помечены как не публикуемые напрямую")

g4 = observed["validation"]["g4_polesye_chernobyl"]
check(g4["still_monotonic_nondecreasing"] is True,
      "G-4: рост area_share_below(5) не выдержал исключения Полесья/Чернобыля")
check(g4["growth_1975_2020"] > 0, "G-4: рост исчез после исключения")

g5 = observed["validation"]["g5_centroid_sensitivity"]
check(g5["pass"] is True, "G-5: сдвиг центра масс превысил допуск 15 км")

g2 = forecast["g2_report_summary"]
check(g2["max_pct_diff"] <= 0.1, "G-2: отклонение прогноза клеток от прогноза района >0.1%")

check(g3["pass"] is False,
      "G-3 задокументирована как провалившаяся (D-007) - если тест теперь "
      "показывает pass=True, это регресс данных без обновления decisions/INF-15.md")
check(g3["pct_agree"] < 70, "G-3: согласие знака должно быть <70% (задокументированный факт)")

net_path = RAW / "network_metrics.json"
if net_path.exists():
    net = json.loads(net_path.read_text())
    check("g6" in net and "correlation_c3" in net,
          "network_metrics.json: отсутствуют обязательные разделы g6/correlation_c3")

if failures:
    print(f"ПРОВАЛЕНО ({len(failures)}):", file=sys.stderr)
    for f in failures[:25]:
        print("  " + f, file=sys.stderr)
    sys.exit(1)
print("Все инварианты данных выполнены.")
