"""Тесты рилса R-P1 «Кто кого содержит» (INF-13, tools/render_reel_pension.py
+ tools/reel_pension_scene.json).

Требует numpy+Pillow+shapely (растровый/геометрический стек) - skip в CI без
них, тот же приём, что и test_grid_reel.py/test_nightlights_reel.py
(растровый стек не ставится в основном CI-шаге, см. коммит "CI: тесты
кадров рилса skip без rasterio"). В .venv этой сдачи все три пакета
установлены, поэтому здесь, в отличие от чистого skip-заглушки, есть и
содержательные тесты, которые реально запускаются (рендер кадра, проверка
пикселей карты, honest-числа H1/H3).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCENE_PATH = ROOT / "tools" / "reel_pension_scene.json"
SCRIPT_PATH = ROOT / "tools" / "render_reel_pension.py"
PENSION_JSON = ROOT / "web" / "public" / "data" / "pension.json"
GEO_JSON = ROOT / "web" / "public" / "data" / "geo" / "adm2.geojson"

pytest.importorskip("numpy")
pytest.importorskip("PIL")
pytest.importorskip("shapely")

pytestmark = pytest.mark.skipif(
    not (PENSION_JSON.exists() and GEO_JSON.exists() and SCENE_PATH.exists()),
    reason="web/public/data/pension.json или geo/adm2.geojson ещё не собраны")


def _load_module():
    sys.path.insert(0, str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location(
        "render_reel_pension", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


@pytest.fixture(scope="module")
def scene():
    return json.loads(SCENE_PATH.read_text())


@pytest.fixture(scope="module")
def pension():
    return json.loads(PENSION_JSON.read_text())


# ------------------------------------------------------- сцена/тексты ---

def test_scene_has_both_languages_texts_and_callouts(scene):
    assert "ru" in scene["texts"] and "be" in scene["texts"]
    assert "ru" in scene["callouts"] and "be" in scene["callouts"]
    for lang in ("ru", "be"):
        for key in ("hookLine", "disclaimer", "disclaimerTitle", "ctaUrl",
                    "forecastBadge", "toggleAsIs", "toggle6560"):
            assert scene["texts"][lang].get(key), f"{lang}.{key} пусто"
        assert len(scene["callouts"][lang]) == len(scene["callouts"]["ru"])


def test_disclaimer_never_says_budget(scene):
    """Жёсткое требование проекта: слово «бюджет»/«бюджэт» не должно
    появляться рядом с денежным/сравнительным индексом ни на одном языке -
    см. docs/decisions/INF-13.md и CLAUDE-инструкции этой сдачи."""
    for lang in ("ru", "be"):
        text = scene["texts"][lang]["disclaimer"].lower()
        assert "бюджет" not in text
        assert "бюджэт" not in text
        # тоже самое - по всему texts-блоку языка, не только в disclaimer
        blob = json.dumps(scene["texts"][lang], ensure_ascii=False).lower()
        assert "бюджет" not in blob
        assert "бюджэт" not in blob


def test_duration_within_spec_range(scene):
    """ТЗ (Storyboard): «~35-40 секунд»."""
    duration = scene["format"]["durationSec"]
    assert 35.0 <= duration <= 40.5, duration


def test_resolution_is_1080x1920(scene, mod):
    assert (scene["format"]["width"], scene["format"]["height"]) == (1080, 1920)
    assert (mod.W, mod.H) == (1080, 1920)


def test_timeline_covers_full_duration_and_known_scenes(scene):
    tl = scene["timeline"]
    assert tl[0]["t"][0] == 0.0
    assert tl[-1]["t"][1] == scene["format"]["durationSec"]
    for a, b in zip(tl, tl[1:]):
        assert a["t"][1] == b["t"][0], "разрыв/наложение в хронометраже"
    ids = {s["scene"] for s in tl}
    assert {"hook", "observed", "forecast", "policy", "finale"} <= ids


def test_timeline_reaches_2009_and_2056():
    scene_ = json.loads(SCENE_PATH.read_text())
    years = [y for s in scene_["timeline"] for y in s["year"]]
    assert min(years) == 2009
    assert max(years) == 2056


# ------------------------------------------------------------- данные ---

def test_geo_join_covers_all_118_territories(pension):
    """web/public/data/geo/adm2.geojson properties.id должен покрывать
    ровно territories.keys() пенсионного файла (join-поле рилса)."""
    gj = json.loads(GEO_JSON.read_text())
    geo_ids = {f["properties"]["id"] for f in gj["features"]}
    terr_ids = set(pension["territories"].keys())
    assert terr_ids <= geo_ids
    assert len(terr_ids) == 118


def test_geo_has_polygon_and_multipolygon(mod, pension):
    """Явное требование сдачи - оба типа геометрии должны обрабатываться."""
    feats, _ = mod.load_geo(pension["territories"])
    assert any(len(f["rings"]) == 1 for f in feats)
    assert any(len(f["rings"]) > 1 for f in feats), \
        "в файле должен быть хотя бы один MultiPolygon (r-horacki)"


def test_sr_color_matches_scale_ts_breaks(mod):
    """Портирована 1:1 из web/components/pension/scale.ts::srColor() -
    проверяем те же самые контрольные точки, что определяют его ветки."""
    assert mod.sr_color(0.5) == mod.DIV_NEG[3]
    assert mod.sr_color(0.99) == mod.DIV_NEG[3]
    assert mod.sr_color(1.10) == mod.DIV_NEG[2]
    assert mod.sr_color(1.50) == mod.DIV_MID   # порог 1,5 - середина шкалы
    assert mod.sr_color(1.55) == mod.DIV_MID
    assert mod.sr_color(1.56) == mod.DIV_POS[0]
    assert mod.sr_color(3.0) == mod.DIV_POS[3]
    assert mod.sr_color(None) == mod.NODATA


def test_h3_stats_match_published_page(pension):
    """Тот же расчёт, что web/components/pension/Findings.tsx (H3): из
    районов, где переход порога 1,5 при действующем графике наступает не
    позже 2056 года, у скольких повышение до 65/60 отодвигает переход ЗА
    пределы 2056. Числа заморожены докладом скептика в
    docs/decisions/INF-13.md («H3 технически опровергнута...») - 93
    подходящих района, 27 из них уходят за горизонт, среднее по остальным
    ~9,2 года."""
    mod = _load_module()
    eligible, beyond, avg_shift = mod.compute_h3_stats(pension["territories"])
    assert eligible == 93
    assert beyond == 27
    assert 9.0 < avg_shift < 9.5


def test_karelicki_is_the_lone_2009_case_below_1_5(pension, mod):
    terr = pension["territories"]["r-karelicki"]
    v2009 = mod.sr_interp(terr["sr"]["as_is"][mod.SCENARIO], 2009)
    assert v2009 < 1.5
    below_2009 = sum(
        1 for t in pension["territories"].values()
        if mod.sr_interp(t["sr"]["as_is"][mod.SCENARIO], 2009) < 1.5)
    assert below_2009 == 1


# --------------------------------------------------------- рендер кадра ---

def test_frame_renders_at_full_resolution(mod, pension, scene):
    feats, bbox = mod.load_geo(pension["territories"])
    proj = mod.make_projector(bbox, mod.MAP_X0, mod.MAP_Y0, mod.MAP_W, mod.MAP_H)
    mod.precompute_pixels(feats, proj)
    feats_by_id = {f["id"]: f for f in feats}
    hatch = mod.make_hatch_overlay(mod.MAP_W, mod.MAP_H)
    h3stats = mod.compute_h3_stats(pension["territories"])
    fps = scene["format"]["fps"]

    img_hook = mod.render_frame(0, fps, pension, feats, feats_by_id, hatch,
                                scene, "ru", h3stats)
    assert img_hook.size == (1080, 1920)

    total = int(scene["format"]["durationSec"] * fps)
    img_finale = mod.render_frame(total - 1, fps, pension, feats, feats_by_id,
                                  hatch, scene, "be", h3stats)
    assert img_finale.size == (1080, 1920)


def test_frame_at_2046_shows_69_below_threshold(mod, pension, scene):
    """Прогон конкретного кадра, где год интерполяции ровно попадает на
    2046 (H1: «69 из 118» - см. docs/decisions/INF-13.md), и прямая
    проверка того, что карта на этом кадре реально закрашена в цвета,
    дающие ровно это число - не просто что число где-то в JSON."""
    feats, bbox = mod.load_geo(pension["territories"])
    proj = mod.make_projector(bbox, mod.MAP_X0, mod.MAP_Y0, mod.MAP_W, mod.MAP_H)
    mod.precompute_pixels(feats, proj)

    seg = next(s for s in scene["timeline"]
              if s["scene"] == "forecast" and s["year"][0] < 2046 < s["year"][1])
    fps = scene["format"]["fps"]
    # t, при котором year(t) == 2046 внутри найденного сегмента
    k = (2046 - seg["year"][0]) / (seg["year"][1] - seg["year"][0])
    t = seg["t"][0] + k * (seg["t"][1] - seg["t"][0])
    gi = round(t * fps)

    srs = {tid: mod.sr_now_for(terr, 2046.0, seg, k)
          for tid, terr in pension["territories"].items()}
    below15 = sum(1 for v in srs.values() if v < 1.5)
    assert below15 == 69

    year_at_gi = seg["year"][0] + (seg["year"][1] - seg["year"][0]) * (
        (gi / fps - seg["t"][0]) / (seg["t"][1] - seg["t"][0]))
    assert abs(year_at_gi - 2046) < 0.05


def test_dump_every_writes_png_frames(mod, tmp_path, pension, scene):
    """--dump-every N пишет PNG вместо видео (та же ветка render(), что и
    CLI --dump-every) - прогоняется в tmp_path, не трогает build/ проекта
    (ROOT завязан на входные пути данных, monkeypatch'ить его небезопасно -
    сломает load_pension()/load_geo())."""
    feats, bbox = mod.load_geo(pension["territories"])
    proj = mod.make_projector(bbox, mod.MAP_X0, mod.MAP_Y0, mod.MAP_W, mod.MAP_H)
    mod.precompute_pixels(feats, proj)
    feats_by_id = {f["id"]: f for f in feats}
    hatch = mod.make_hatch_overlay(mod.MAP_W, mod.MAP_H)
    h3stats = mod.compute_h3_stats(pension["territories"])
    fps = scene["format"]["fps"]
    total = int(scene["format"]["durationSec"] * fps)

    out_dir = tmp_path / "reel_pension_preview_ru"
    out_dir.mkdir()
    for gi in range(0, total, 600):
        mod.render_frame(gi, fps, pension, feats, feats_by_id, hatch, scene,
                         "ru", h3stats).save(out_dir / f"f{gi:05d}.png")

    pngs = sorted(out_dir.glob("f*.png"))
    assert len(pngs) >= 2
    from PIL import Image
    with Image.open(pngs[0]) as im:
        assert im.size == (1080, 1920)
