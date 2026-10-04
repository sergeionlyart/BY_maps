"""Тесты рилса R-V1 «Второй сенсор» (INF-22): сцена, хронометраж, шкала
карты = шкале страницы, безопасная зона 4:5, числа в кадре — из
опубликованных данных, а не вписаны вручную."""
import importlib.util
import json
import re
import sys

import pytest
from PIL import Image, ImageChops

from etl.common import ROOT

pytest.importorskip("shapely")

SCENE = ROOT / "tools" / "reel_sensors_scene.json"


@pytest.fixture(scope="module")
def mod():
    sys.path.insert(0, str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location(
        "render_reel_sensors", ROOT / "tools" / "render_reel_sensors.py")
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
    """Числа в кадре вычисляются из sensors.json; в текстах сцены допустимы
    только неизменяемые: окна пререгистрации, 118 районов, адрес."""
    allowed = {"1990", "2020", "2013", "2019", "118", "1897", "2026"}
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


def test_timeline_continuous_and_contains_refutation(scene, mod):
    tl = scene["timeline"]
    assert tl[0]["t"][0] == 0.0
    assert tl[-1]["t"][1] == scene["format"]["durationSec"]
    for a, b in zip(tl, tl[1:]):
        assert a["t"][1] == b["t"][0], "разрыв или наложение в хронометраже"
    names = [s["scene"] for s in tl]
    # опровержение H2 — обязательная сцена, ролик его не обходит
    assert "refuted" in names
    assert set(names) <= set(mod.SCENES)


def test_scale_matches_page(mod):
    """Шкала карты — буквальный перенос SensorsView.tsx."""
    src = (ROOT / "web" / "components" / "SensorsView.tsx").read_text()
    assert "const BREAKS = [-0.3, -0.15, -0.05, 0.05, 0.15, 0.3];" in src
    assert ("const COLORS = [DIV_NEG[3], DIV_NEG[2], DIV_NEG[0], DIV_MID, "
            "DIV_POS[0], DIV_POS[2], DIV_POS[3]];") in src
    assert mod.BREAKS == [-0.3, -0.15, -0.05, 0.05, 0.15, 0.3]
    assert mod.color_lo(0.0) == mod.COLORS[3]           # согласие — нейтраль
    assert mod.color_lo(-1.0) == mod.COLORS[0]
    assert mod.color_lo(1.0) == mod.COLORS[-1]
    assert mod.color_lo(None) == mod.NODATA


def test_counters_equal_published(mod, data):
    assert mod.light_up_pop_down(data) == data["posthoc"]["light_up_pop_down_1319"]
    assert mod.sign_agree_og(data) == data["summary"]["sign_agree_OG"]


def test_geo_covers_118(geo):
    feats, _ = geo
    assert sum(1 for f in feats if f["in_territories"]) == 118


@pytest.mark.parametrize("sec", [2.0, 7.0, 15.0, 24.0, 31.0, 38.0])
def test_frames_keep_content_inside_safe_zone(mod, data, scene, geo, sec):
    """Безопасная зона 4:5 (R-P1 v1.5): в полосах 215..285 и 1620..1690 нет
    пикселей контента."""
    feats, hatch = geo
    for lang in ("ru", "be"):
        img = mod.render_frame(int(sec * 30), data, scene, feats, hatch, lang)
        assert img.size == (1080, 1920)
        for y0, y1 in ((215, 285), (1620, 1690)):
            band = img.crop((0, y0, 1080, y1))
            diff = ImageChops.difference(band, Image.new("RGB", band.size, mod.BG))
            hit = diff.convert("L").point(lambda v: 255 if v > 24 else 0).getbbox()
            assert hit is None, (lang, sec, y0, hit)
