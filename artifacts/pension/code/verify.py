#!/usr/bin/env python3
"""Сверка воспроизведённых показателей поддержки (SR/TDR/crossing_year/CG)
с заявленными (в допусках). Канонический источник чисел - свежепересчитанный
web/public/data/pension.json (тот же файл, что читает лендинг); показатель
G-1 (национальные доли на 01.01.2025) не хранится в pension.json подробно
(только пройдена/не пройдена в meta.validation), поэтому пересчитывается
напрямую через etl.pension.gate_g1() - чистая функция, не требующая
предварительного build()."""
import json
import statistics
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG))


def computed_metrics() -> dict:
    d = json.loads((PKG / "web" / "public" / "data" / "pension.json").read_text())
    years_national = d["years"]["national"]
    years_territory = d["years"]["territory"]
    terr = d["territories"]
    raions = sorted(k for k in terr if k.startswith("r-"))

    nat_sr = d["national"]["sr"]["as_is"]["base:official"]
    nat_crossing = d["national"]["crossing"]["as_is"]["base:official"]

    def sr_national(year: int) -> float | None:
        return nat_sr[years_national.index(year)]

    def sr_raion(raion: str, year: int) -> float | None:
        return terr[raion]["sr"]["as_is"]["base:official"][years_territory.index(year)]

    def below(year: int, thr: float = 1.5) -> int:
        return sum(1 for r in raions if (sr_raion(r, year) or 99) < thr)

    def cv(year: int) -> float:
        vals = [v for v in (sr_raion(r, year) for r in raions) if v is not None]
        return statistics.pstdev(vals) / statistics.mean(vals)

    def sd(year: int) -> float:
        vals = [v for v in (sr_raion(r, year) for r in raions) if v is not None]
        return statistics.pstdev(vals)

    kar = terr["r-karelicki"]

    from etl.pension import gate_g1  # чистая функция: только age_current.csv
    g1 = gate_g1()

    return {
        "national_sr_2009": sr_national(2009),
        "national_sr_2046": sr_national(2046),
        "national_sr_2056": sr_national(2056),
        "national_crossing_year_1_5": nat_crossing["1.5"],
        "national_crossing_year_2_0": nat_crossing["2.0"],
        "raions_below_1_5_2009": below(2009),
        "raions_below_1_5_2046": below(2046),
        "karelicki_sr_2009": sr_raion("r-karelicki", 2009),
        "karelicki_sr_2046": sr_raion("r-karelicki", 2046),
        "karelicki_cg_2046": kar["cg"]["base:official"]["2046"],
        "cg_suppressed_count": sum(1 for r in raions if terr[r]["cg_suppressed"]),
        "cv_sr_2026": round(cv(2026), 4),
        "cv_sr_2046": round(cv(2046), 4),
        "sd_sr_2026": round(sd(2026), 4),
        "sd_sr_2046": round(sd(2046), 4),
        "g1_share_above_model": g1["share_above_model"],
    }


def main() -> None:
    computed = computed_metrics()
    final_dir = PKG / "data" / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "computed_results.json").write_text(json.dumps(
        [{"metric": k, "value": v} for k, v in sorted(computed.items())],
        ensure_ascii=False, indent=1))

    expected = json.loads((PKG / "checks" / "expected_results.json").read_text())
    failures = []
    for er in expected:
        got = computed.get(er["metric"])
        if got is None:
            failures.append(f"{er['metric']}: не воспроизведена")
        elif abs(got - er["value"]) > er["tolerance"]:
            failures.append(f"{er['metric']}: получено {got}, заявлено {er['value']} "
                            f"(допуск ±{er['tolerance']})")
        else:
            print(f"  OK {er['metric']}: {got}")
    if failures:
        print("РАСХОЖДЕНИЯ:", file=sys.stderr)
        for x in failures:
            print("  " + x, file=sys.stderr)
        sys.exit(1)
    print(f"Все {len(expected)} контрольных метрик воспроизведены в допусках.")


if __name__ == "__main__":
    main()
