"""Инварианты рилс-конвейера INF-15 (tools/render_reel_grid.py).

Требует numpy+Pillow (растровый стек) - skip в CI без них, как у
test_nightlights_reel.py (растровый стек не ставится в основном CI-шаге).
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCENE_PATH = ROOT / "tools" / "reel_grid_scene.json"
GRID_JSON = ROOT / "web" / "public" / "data" / "grid.json"
FRAMES_META = ROOT / "web" / "public" / "data" / "grid_frames" / "meta.json"

pytest.importorskip("numpy")
pytest.importorskip("PIL")

pytestmark = pytest.mark.skipif(
    not (GRID_JSON.exists() and FRAMES_META.exists()),
    reason="etl.grid_project/etl.grid_frames ещё не прогонялись")


def _load_module():
    sys.path.insert(0, str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location(
        "render_reel_grid", ROOT / "tools" / "render_reel_grid.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_scene_has_both_languages():
    scene = json.loads(SCENE_PATH.read_text())
    assert "ru" in scene["text"] and "be" in scene["text"]
    for lang in ("ru", "be"):
        for key in ("disclaimer_1", "disclaimer_3", "model_badge", "network_title"):
            assert scene["text"][lang].get(key), f"{lang}.{key} пусто"


def test_keyframes_cover_full_range():
    scene = json.loads(SCENE_PATH.read_text())
    years = [k["year"] for k in scene["keyframes"]]
    assert years[0] == 1975
    assert years[-1] == 2050
    assert 2020 in years and 2026 in years  # стык наблюдение/модель


@pytest.mark.parametrize("lang", ["ru", "be"])
def test_duration_within_35_45s(lang):
    mod = _load_module()
    reel = mod.Reel(lang)
    total = reel.total_frames()
    duration = total / mod.FPS
    assert 35.0 <= duration <= 45.0, f"{lang}: {duration:.1f} c вне диапазона 35-45"


def test_resolution_is_1080x1920():
    mod = _load_module()
    assert (mod.W, mod.H) == (1080, 1920)


@pytest.mark.parametrize("lang", ["ru", "be"])
def test_brand_and_disclaimer_frames_render(lang):
    mod = _load_module()
    reel = mod.Reel(lang)
    brand = reel.frame(0)
    assert brand.size == (1080, 1920)
    disclaimer = reel.frame(reel.total_frames() - 1)
    assert disclaimer.size == (1080, 1920)
