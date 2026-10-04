"""INF-20: пакет by-maps-seam не расходится с etl/seam.py и с данными страницы.

Код пакета (artifacts/seam/code/build.py) — копия etl/seam.py с путями пакета.
Полный пересчёт занимает ~80 с, поэтому здесь быстрые проверки:
  1) логика совпадает с etl/seam.py (AST без докстрингов): правка etl/seam.py
     без переноса в пакет ловится сразу, ещё до появления новых данных;
  2) data/final пакета совпадает с файлами страницы побайтно;
  3) опубликованный zip собран из текущих исходников пакета.
"""
from __future__ import annotations

import ast
import zipfile

from etl.common import ROOT

ETL = ROOT / "etl" / "seam.py"
PKG = ROOT / "artifacts" / "seam"
BUILD = PKG / "code" / "build.py"
ZIP = ROOT / "web" / "public" / "artifacts" / "by-maps-seam-v1.0.0.zip"

SAME_FUNCS = ["_f", "ln1", "hav_km", "base_ok", "_solve", "_inv", "norm_p", "rnd", "pack",
              "_cell_index", "_locate", "_median", "units_block"]
SAME_CONSTS = ["SEGS", "SEG_RU", "SOVIET", "H_MAIN", "H_ALT", "DONUT", "DONUT_DMSP", "CITY_KM",
               "CHERN_KM", "FLARES", "FLARE_KM", "BLOCK_M", "PLACEBO_KM", "BIN_KM", "ALPHA",
               "OUTCOMES", "CONTROLS", "CONTROLS_ADDED", "WIN_NB", "WIN_BY", "CITY_LEVELS",
               "BY_PERIMETER_BREAK"]
FIX = "пакет отстал от etl/seam.py: перенесите правку в artifacts/seam/code/build.py и пересоберите пакет"


def _defs(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    funcs, consts = {}, {}
    for n in tree.body:
        if isinstance(n, ast.FunctionDef):
            funcs[n.name] = n
        elif isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
            consts[n.targets[0].id] = n.value
    return funcs, consts


def _body(fn, skip_defaults=False):
    """Тело функции без докстринга; skip_defaults — без строк вида `x = G if x is None else x`
    (в пакете h/donut/step читаются в момент вызова, чтобы работали флаги стресс-теста)."""
    body = list(fn.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
        body = body[1:]
    if skip_defaults:
        body = [s for s in body if not (isinstance(s, ast.Assign) and isinstance(s.value, ast.IfExp)
                                        and isinstance(s.value.test, ast.Compare)
                                        and isinstance(s.value.test.ops[0], ast.Is))]
    return [ast.dump(s) for s in body]


def _between(fn, first, last):
    """Операторы функции от присваивания `first` (не включая) до `last` (включая)."""
    body = _body(fn)
    names = [s for s in fn.body if not (isinstance(s, ast.Expr) and isinstance(getattr(s, "value", None), ast.Constant))]
    idx = {s.targets[0].id: i for i, s in enumerate(names)
           if isinstance(s, ast.Assign) and isinstance(s.targets[0], ast.Name)}
    return body[idx[first] + 1: idx[last] + 1]


def test_package_logic_matches_etl():
    ef, ec = _defs(ETL)
    pf, pc = _defs(BUILD)
    for name in SAME_FUNCS:
        if name in ef:
            assert name in pf, f"{name}: нет в пакете — {FIX}"
            assert _body(ef[name]) == _body(pf[name]), f"{name}: {FIX}"
    for name in SAME_CONSTS:
        if name in ec:
            assert name in pc, f"{name}: нет в пакете — {FIX}"
            assert ast.dump(ec[name]) == ast.dump(pc[name]), f"{name}: {FIX}"
    for name in ("rd", "profile"):
        assert _body(ef[name], True) == _body(pf[name], True), f"{name}: {FIX}"
    # спецификации, правила вердиктов, профили и meta: main() проекта == compute() пакета
    assert _between(ef["main"], "cells", "out") == _between(pf["compute"], "cells", "out"), f"main/compute: {FIX}"


def test_package_outputs_match_landing():
    pairs = [(PKG / "data" / "final" / "seam.json", ROOT / "web" / "public" / "data" / "seam.json"),
             (PKG / "data" / "final" / "seam_results.md", ROOT / "docs" / "notes" / "seam_results.md")]
    for pkg, site in pairs:
        assert pkg.read_bytes() == site.read_bytes(), (
            f"{pkg.relative_to(ROOT)} != {site.relative_to(ROOT)}: перезапустите python -m etl.seam "
            f"и пересчитайте пакет (python3 artifacts/seam/code/build.py --cells data/raw/seam/cells.csv.gz "
            f"--units-dir data/raw/seam/units), затем python -m etl.artifacts.build seam и "
            f"python -m etl.artifacts.catalog")


def test_published_zip_built_from_current_sources():
    root = "by-maps-seam-v1.0.0/"
    with zipfile.ZipFile(ZIP) as zf:
        for rel in ("code/build.py", "data/final/seam.json", "data/final/estimates.csv",
                    "data/final/computed_results.json", "AGENT.md", "LIMITATIONS.md"):
            assert zf.read(root + rel) == (PKG / rel).read_bytes(), (
                f"{rel} в zip расходится с artifacts/seam/: python -m etl.artifacts.build seam "
                f"(пакет ещё не опубликован в git) или поднимите версию")
        # вендоренные входы: таблица ячеек и таблицы официальных рядов (H5)
        raw = ROOT / "data" / "raw" / "seam"
        for rel, src in (("sources/raw/cells.csv.gz", raw / "cells.csv.gz"),
                         *((f"sources/raw/units/{n}", raw / "units" / n)
                           for n in ("units_population.csv", "units_geo.csv", "twins.csv", "checks.csv"))):
            assert zf.read(root + rel) == src.read_bytes(), (
                f"{rel} в zip расходится с {src.relative_to(ROOT)}: входные данные изменились после "
                f"сборки - пересчитайте пакет и пересоберите (см. test_package_outputs_match_landing)")
