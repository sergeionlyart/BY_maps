#!/usr/bin/env python3
"""Инварианты данных пакета seam. Без внешних зависимостей: plain asserts.

Запуск: python3 checks/tests/test_invariants.py (из корня пакета или откуда
угодно - пути разрешаются от расположения файла). Совместим с pytest.
"""
import csv
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PKG / "code"))
import build  # noqa: E402

FINAL = PKG / "data" / "final"
SEGS = ["PL", "LT", "LV", "RU", "UA"]
ADDED = {"fe_subseg", "placebo_by", "placebo_nb", "donut10", "built_only"}   # после фиксации
PREREG = {"main", "h15", "h50", "uniform", "with_cities"}                     # по пререгистрации


def _rows(name):
    with open(FINAL / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _synthetic(jump, slope_l=0.02, slope_r=0.05):
    """Ячейки на линии с ТОЧНО линейным исходом и скачком jump (п.п.) в d = 0."""
    rows = []
    for i in range(-240, 241):
        d = i / 10.0
        if abs(d) < 2.0:
            continue
        y = 1.0 + slope_l * d if d < 0 else 1.0 + jump + slope_r * d
        rows.append({"d_km": d, "cl": str(math.floor(d / 5.0)), "subseg": "s",
                     "crop_2003": 0.0, "crop_2019": y / 100.0})
    return rows


def test_estimator_recovers_known_jump():
    """Эстиматор на точной линейной функции со скачком 3 п.п.: tau = 3 до машинной точности."""
    res = build.rd(_synthetic(3.0), "C_0319")
    assert res is not None
    assert abs(res["tau"] - 3.0) < 1e-9, res["tau"]
    assert res["se"] < 1e-6, res["se"]


def test_estimator_no_jump_on_continuous_line():
    res = build.rd(_synthetic(0.0, 0.03, 0.03), "C_0319")
    assert abs(res["tau"]) < 1e-9, res["tau"]


def test_sign_convention_neighbour_minus_belarus():
    """Скачок вверх на стороне соседа (d > 0) даёт tau > 0."""
    assert build.rd(_synthetic(-2.5), "C_0319")["tau"] < 0
    assert build.rd(_synthetic(+2.5), "C_0319")["tau"] > 0


def test_cells_source_matches_registry():
    reg = {r["id"]: r for r in csv.DictReader(open(PKG / "sources" / "registry.csv", encoding="utf-8"))}
    src = PKG / "sources" / "raw" / "cells.csv.gz"
    h = hashlib.sha256(src.read_bytes()).hexdigest()
    assert h == reg["bymaps_cells"]["sha256"], "cells.csv.gz не совпадает с реестром"
    with gzip.open(src, "rt", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        need = {"d_km", "seg", "subseg", "city_km", "chern_km", "x3035", "y3035",
                "wsf_1990", "wsf_2015", "built_1975", "built_1990", "built_2015",
                "li_1992", "li_2012", "li_2019", "li_2024", "vnl_2019", "crop_2003", "crop_2019", "pop_2020"}
        assert need <= set(rd.fieldnames), need - set(rd.fieldnames)
        n, segs, dmax = 0, set(), 0.0
        for r in rd:
            n += 1
            segs.add(r["seg"])
            dmax = max(dmax, abs(float(r["d_km"])))
    assert n == 234_491, n
    assert segs == set(SEGS), segs
    assert dmax <= 52.0 + 1e-9, dmax


def test_estimates_table_complete_and_sane():
    rows = _rows("estimates.csv")
    assert len(rows) == 660, len(rows)
    main = {(r["outcome"], r["seg"]): r for r in rows if r["spec"] == "main"}
    assert len(main) == len(build.OUTCOMES) * len(SEGS)
    for (o, s), r in main.items():
        assert r["tau"] != "", f"нет основной оценки {o}/{s}"
        assert int(r["n_by"]) >= 30 and int(r["n_nb"]) >= 30
    for r in rows:
        if r["tau"] == "":
            continue
        assert float(r["se"]) >= 0
        if r["p"] != "":
            assert 0.0 <= float(r["p"]) <= 1.0
        # пометка «добавлено после фиксации» - строго по списку
        assert r["added"] == ("1" if r["spec"] in ADDED else "0"), (r["spec"], r["added"])
        assert r["spec"] in ADDED | PREREG


def test_seam_json_matches_estimates_csv():
    sj = json.loads((FINAL / "seam.json").read_text(encoding="utf-8"))
    assert sj["meta"]["cells_total"] == 234_491
    assert sj["meta"]["h_main_km"] == 25.0 and sj["meta"]["donut_km"] == 2.0
    by_key = {(r["outcome"], r["seg"], r["spec"]): r for r in _rows("estimates.csv")}
    assert len(sj["estimates"]) == len(by_key)
    for e in sj["estimates"]:
        r = by_key[(e["outcome"], e["seg"], e["spec"])]
        if e.get("tau") is None:
            assert r["tau"] == ""
        else:
            assert abs(float(r["tau"]) - e["tau"]) < 1e-5


def test_verdicts_follow_preregistered_rules():
    """Независимый пересчёт вердиктов H1–H4 из estimates.csv по правилам PREREGISTRATION.md §4."""
    sj = json.loads((FINAL / "seam.json").read_text(encoding="utf-8"))
    m = {(r["outcome"], r["seg"], r["spec"]): r for r in _rows("estimates.csv")}

    def sig(o, s, spec="main", neg=False):
        r = m[(o, s, spec)]
        if r["tau"] == "" or r["p"] == "":
            return False
        return float(r["p"]) < 0.05 and (float(r["tau"]) < 0 if neg else True)

    h1_sig = [s for s in SEGS if sig("B_9015", s)]
    did_raw = sum(abs(float(m[("G_9015", s, "main")]["tau"])) > abs(float(m[("G_7590", s, "main")]["tau"]))
                  for s in ["LT", "LV", "RU", "UA"])
    h1 = ("подтверждена" if len(h1_sig) >= 3 and did_raw >= 3 else
          "частично" if len(h1_sig) >= 3 or did_raw >= 3 else "не подтверждена")
    h2_neg = [s for s in ["RU", "LT", "LV", "UA"] if sig("C_0319", s, neg=True)]
    pl = float(m[("C_0319", "PL", "main")]["tau"])
    h2 = ("подтверждена" if len(h2_neg) >= 3 and abs(pl) < 2 else
          "частично" if len(h2_neg) >= 2 else "не подтверждена")
    h3_neg = [s for s in SEGS if sig("I_2019", s, neg=True)]
    h3 = "подтверждена" if len(h3_neg) >= 4 else ("частично" if len(h3_neg) >= 2 else "не подтверждена")
    h4 = "подтверждена" if sig("L_1924", "UA", neg=True) else "не подтверждена"
    got = {k: sj["hypotheses"][k]["verdict"] for k in ("H1", "H2", "H3", "H4")}
    assert got == {"H1": h1, "H2": h2, "H3": h3, "H4": h4}, got


def test_h5_medians_and_rule_from_units():
    """H5 (описательно): медианы темпа пересчитываются из списка единиц seam.json,
    вердикт — по правилу пререгистрации (LT, LV, RU убывают быстрее, PL — медленнее)."""
    sj = json.loads((FINAL / "seam.json").read_text(encoding="utf-8"))
    ub = sj.get("units")
    assert (PKG / "sources" / "raw" / "units" / "units_population.csv").is_file()
    assert ub and ub["units"], "блок units пуст при вложенных таблицах единиц"

    def rate(u, w):
        s = {int(a): b for a, b in u["series"].items()}
        a, b = w
        if s.get(a, 0) > 0 and s.get(b, 0) > 0:
            return 100.0 * (math.log(s[b]) - math.log(s[a])) / (b - a)
        return None

    def median(v):
        v = sorted(v)
        n = len(v)
        return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2

    for sg in SEGS:
        c = ub["comparison"][sg]
        nb = [x for x in (rate(u, build.WIN_NB[sg]) for u in ub["units"] if u["country"] == sg and u["seg"] == sg) if x is not None]
        by = [x for x in (rate(u, build.WIN_BY[sg]) for u in ub["units"] if u["country"] == "BY" and u["seg"] == sg) if x is not None]
        assert (len(nb), len(by)) == (c["n_nb"], c["n_by"]), sg
        assert abs(median(nb) - c["nb_median"]) < 1e-3 and abs(median(by) - c["by_median"]) < 1e-3, sg
        assert all(abs(u["d_km"]) <= 50 for u in ub["units"])
    held = [(ub["comparison"][s]["nb_median"] < ub["comparison"][s]["by_median"]) for s in ("LT", "LV", "RU")]
    held.append(ub["comparison"]["PL"]["nb_median"] > ub["comparison"]["PL"]["by_median"])
    want = ("подтверждена (описательно)" if all(held) else
            "частично (описательно)" if sum(held) >= 2 else "не подтверждена (описательно)")
    assert sj["hypotheses"]["H5"]["verdict"] == want, (sj["hypotheses"]["H5"]["verdict"], want)


def test_computed_results_numbers_only():
    res = json.loads((FINAL / "computed_results.json").read_text(encoding="utf-8"))
    assert isinstance(res, list) and res
    names = [r["metric"] for r in res]
    assert len(names) == len(set(names)), "дубли метрик"
    for r in res:
        assert set(r) == {"metric", "value"}, r
        assert isinstance(r["value"], (int, float)) and not isinstance(r["value"], bool), r
        assert math.isfinite(r["value"]), r


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"Все {len(fns)} инвариантов выполнены.")
