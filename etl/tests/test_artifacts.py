"""Тесты конвейера пакетов: сборка-валидация, ловля подделок, гейты."""
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from etl.common import ROOT
from etl.artifacts.build import all_slugs, load_spec, stage, ARTIFACTS_OUT
from etl.artifacts.validate import (ValidationError, validate_tree,
                                    run_reproduction, validate_zip)


@pytest.fixture(scope="module")
def staged(tmp_path_factory):
    """Собранное дерево пакета zipf во временной директории."""
    dest = tmp_path_factory.mktemp("pkg") / "by-maps-zipf"
    dest.mkdir()
    stage("zipf", load_spec("zipf"), dest)
    return dest


def test_all_published_zips_validate_structurally():
    zips = sorted(ARTIFACTS_OUT.glob("by-maps-*.zip"))
    assert zips, "нет опубликованных пакетов"
    for z in zips:
        validate_zip(z, run=False)


def test_staged_tree_validates_and_reproduces(staged):
    m = validate_tree(staged)
    run_reproduction(staged, m)


def test_tampered_data_is_caught(staged, tmp_path):
    box = tmp_path / "t1"
    shutil.copytree(staged, box)
    target = box / "data" / "final" / "zipf_slopes.csv"
    target.write_text(target.read_text().replace("-0.9651", "-0.5000"))
    with pytest.raises(ValidationError, match="sha256|сумма"):
        validate_tree(box)


def test_extra_undeclared_file_is_caught(staged, tmp_path):
    box = tmp_path / "t2"
    shutil.copytree(staged, box)
    (box / "malware.py").write_text("print('hi')")
    with pytest.raises(ValidationError, match="не описан"):
        validate_tree(box)


def test_out_of_tolerance_result_is_caught(staged, tmp_path):
    box = tmp_path / "t3"
    shutil.copytree(staged, box)
    m = validate_tree(box)
    m["expected_results"][0]["value"] += 1.0  # заведомо ложное ожидание
    with pytest.raises(ValidationError, match="допуск"):
        run_reproduction(box, m)


def test_method_blocks_exist_for_published_slugs():
    """Гейт Р3: инфографика без методблока не публикуется."""
    methods = ROOT / "web" / "public" / "content" / "methods"
    for slug in all_slugs():
        f = methods / f"{slug}.md"
        assert f.is_file() and len(f.read_text()) > 500, (
            f"нет методологического блока для '{slug}': {f}")
    # ретро-методблок главной карты (TASK_SPEC Р3, этап 0)
    assert (methods / "map.md").is_file()


def test_zip_matches_staged_content(staged):
    """Опубликованный zip соответствует текущим исходникам пакета."""
    zip_path = ARTIFACTS_OUT / "by-maps-zipf-v1.0.0.zip"
    with zipfile.ZipFile(zip_path) as zf:
        zipped = {n.split("/", 1)[1]: zf.read(n) for n in zf.namelist()}
    for p in staged.rglob("*"):
        if p.is_file():
            rel = p.relative_to(staged).as_posix()
            assert rel in zipped, f"{rel} нет в опубликованном zip"
            assert zipped[rel] == p.read_bytes(), (
                f"{rel} расходится с опубликованным zip: пересоберите пакет "
                f"(python -m etl.artifacts.build zipf) или поднимите версию")
