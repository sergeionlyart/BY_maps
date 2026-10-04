"""Тесты рилса R-S1 «Карта, где не хватает мужчин» (INF-20): сцена,
хронометраж, шкалы = шкалам страницы, безопасная зона 4:5, числа в кадре —
из опубликованных данных, а не вписаны вручную."""
import importlib.util
import json
import re
import sys

import pytest
from PIL import Image, ImageChops

from etl.common import ROOT

pytest.importorskip("shapely")

SCENE = ROOT / "tools" / "reel_sexratio_scene.json"


@pytest.fixture(scope="module")
def mod():
    sys.path.insert(0, str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location(
        "render_reel_sexratio", ROOT / "tools" / "render_reel_sexratio.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def scene():
    return json.loads(SCENE.read_text())


@pytest.fixture(scope="module")
def data(mod):
    return mod.load_data()


@pytest.fixture(scope="module")
def geo(mod, data):
    return mod.prepare_geo(data)


def test_both_languages_have_same_keys(scene):
    ru, be = scene["texts"]["ru"], scene["texts"]["be"]
    assert set(ru) == set(be)
    for lang in ("ru", "be"):
        for k, v in scene["texts"][lang].items():
            assert v.strip(), f"{lang}.{k} пусто"


def test_placeholders_match_between_languages(scene):
    ph = lambda s: set(re.findall(r"\{(\w+)\}", s))  # noqa: E731
    for k in scene["texts"]["ru"]:
        assert ph(scene["texts"]["ru"][k]) == ph(scene["texts"]["be"][k]), k


def test_no_numbers_hardcoded_in_texts(scene):
    """Числа в кадре вычисляются из sexratio.json; в текстах сцены допустимы
    только неизменяемые: возрастные группы, 100, 118, годы переписей и
    прогноза, версия модели, адрес."""
    allowed = {"25", "39", "70", "100", "118", "2009", "2019", "2026", "2046",
               "1897", "2026", "4", "1", "2"}
    for lang in ("ru", "be"):
        for k, v in scene["texts"][lang].items():
            if k in ("ctaUrl", "source", "brandTag"):
                continue
            for num in re.findall(r"\d+", v):
                assert num in allowed, (lang, k, num)


def test_resolution_and_duration(scene, mod):
    assert (scene["format"]["width"], scene["format"]["height"]) == (1080, 1920)
    assert (mod.W, mod.H) == (1080, 1920)
    assert 30.0 <= scene["format"]["durationSec"] <= 45.0


def test_timeline_continuous_and_contains_refutation(scene):
    tl = scene["timeline"]
    assert tl[0]["t"][0] == 0.0
    assert tl[-1]["t"][1] == scene["format"]["durationSec"]
    for a, b in zip(tl, tl[1:]):
        assert a["t"][1] == b["t"][0], "разрыв или наложение в хронометраже"
    names = [s["scene"] for s in tl]
    # опровержение главной гипотезы — обязательная сцена, ролик его не обходит
    assert "refuted" in names
    assert {"intro", "map2539", "map70", "finale"} <= set(names)


def test_scales_match_page(mod):
    """Шкалы — буквальный перенос SexRatioView.tsx."""
    src = (ROOT / "web" / "components" / "SexRatioView.tsx").read_text()
    assert "const DIV_BREAKS = [92, 96, 99, 101, 104, 108, 115];" in src
    assert "const OLD_BREAKS = [34, 38, 42, 46, 50];" in src
    assert mod.DIV_BREAKS == [92, 96, 99, 101, 104, 108, 115]
    assert mod.OLD_BREAKS == [34, 38, 42, 46, 50]
    assert mod.color_2539(100.0) == mod.DIV_COLORS[3]      # паритет — нейтраль
    assert mod.color_2539(90.0) == mod.DIV_COLORS[0]
    assert mod.color_2539(130.0) == mod.DIV_COLORS[-1]
    assert mod.color_2539(None) == mod.NODATA


def test_map_values_at_census_nodes_equal_published(mod, data):
    t = data["territories"]["r-ivacevicki"]
    assert mod.value_at(t, "r2539", 2019) == t["summary"]["2019"]["r2539"]
    assert mod.value_at(t, "r2539", 2046) == \
        t["forecast_summary"]["base:official"]["2046"]["r2539"]


def test_counter_at_2019_equals_published(mod, data):
    assert mod.male_surplus_count(data, 2019) == \
        data["female_surplus_2019"]["n_male_surplus"]


def test_median_r70_at_2019_equals_published(mod, data):
    assert mod.median_r70(data, 2019) == pytest.approx(
        data["findings"]["H4"]["median_r70_2019"], abs=0.01)


def test_geo_covers_118(geo):
    feats, _ = geo
    assert sum(1 for f in feats if f["in_territories"]) == 118


@pytest.mark.parametrize("sec", [2.0, 6.5, 15.0, 27.5, 33.0, 40.0])
def test_frames_keep_content_inside_safe_zone(mod, data, scene, geo, sec):
    """Безопасная зона 4:5 (R-P1 v1.5): вне y 300..1600 допустимы только
    дублирующие логотип и адрес во внешних полях — строки около y 150 и 1716.
    Проверяем, что в полосах 215..285 и 1620..1690 нет пикселей контента."""
    feats, hatch = geo
    img = mod.render_frame(int(sec * 30), data, scene, feats, hatch, "ru")
    assert img.size == (1080, 1920)
    for y0, y1 in ((215, 285), (1620, 1690)):
        band = img.crop((0, y0, 1080, y1))
        diff = ImageChops.difference(band, Image.new("RGB", band.size, mod.BG))
        hit = diff.convert("L").point(lambda v: 255 if v > 24 else 0).getbbox()
        assert hit is None, (sec, y0, hit)
