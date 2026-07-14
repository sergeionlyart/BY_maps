"""Тесты рилса Nightlights v3 (ТЗ §20): данные кейсов, субтитры,
видеофайлы, маркировка модельных кадров, визуальная регрессия.

Эталонные sha256 кадров: etl/tests/nightlights_reel_reference.json
(перегенерация: python etl/tests/test_nightlights_reel.py --regen).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
REEL = ROOT / "video" / "nightlights-reel"
NL = ROOT / "web" / "public" / "data" / "nightlights"
REF = Path(__file__).parent / "nightlights_reel_reference.json"

CAUSAL_RU = ["из-за", "вызвано", "вызвал", "привело", "привела",
             "потому что", "по причине", "доказывает, что",
             "объясняется тем"]

REG_FRAMES = [0, 270, 990, 1350, 1620, 1800, 1920]


def _load(p: Path):
    return json.loads(p.read_text())


# ---------- данные кейсов ----------

def test_candidates_gate_and_wording():
    cands = _load(NL / "research_candidates.json")["candidates"]
    assert len(cands) == 3
    for c in cands:
        assert isinstance(c["releaseApproved"], bool)
        assert c["status"] == "candidate"
        # уровень доказательности — явная оговорка, не причинный вывод
        assert isinstance(c["evidenceLevel"], str) and c["evidenceLevel"]
        assert "причина не установлена" in c["evidenceLevel"]
        text = json.dumps(c, ensure_ascii=False).lower()
        for w in CAUSAL_RU:
            assert w not in text, f"причинная формулировка «{w}» в {c['id']}"


def test_reel_shows_no_residual_numbers():
    """Гейт §10: в текстах рилса нет числовых резидуалов (процентов)."""
    story = _load(REEL / "data/reel_story.json")
    texts = json.dumps(story, ensure_ascii=False)
    assert not re.search(r"[+−-]\d+([.,]\d+)?\s*%", texts)
    cases = _load(REEL / "data/research_cases.json")
    assert not re.search(r"\d+([.,]\d+)?\s*%",
                         json.dumps(cases, ensure_ascii=False))


def test_case_zones_exist():
    zones = {r["id"] for r in _load(
        ROOT / "web/public/data/nightlights_v2.json")["rows"]}
    for c in _load(REEL / "data/research_cases.json")["cases"]:
        for z in c["zones"]:
            assert z in zones, f"зона {z} кейса {c['caseId']} не найдена"


def test_story_invariants():
    story = _load(REEL / "data/reel_story.json")
    scenes = story["scenes"]
    assert scenes[0]["start"] == 0.0
    assert scenes[-1]["end"] == story["format"]["durationSec"] == 65.0
    for a, b in zip(scenes, scenes[1:]):
        assert a["end"] == b["start"], f"разрыв сцен {a['id']}->{b['id']}"
    future = next(s for s in scenes if s["id"] == "future")
    assert any("УСИЛЕННАЯ ВИЗУАЛИЗАЦИЯ" in m for m in future["marking"])
    assert "не прогноз спутникового радианса" in " ".join(future["marking"])
    cta = scenes[-1]
    assert "синтетическим голосом OpenAI" in cta["disclosure"]
    assert set(story["spokenScenes"]) == {str(i) for i in range(1, 8)}


# ---------- субтитры ----------

@pytest.mark.parametrize("suffix", ["", "_condensed"])
def test_captions(suffix):
    srt = (REEL / "captions" /
           f"nightlights_reel_v3_ru{suffix}.srt").read_text("utf-8")
    blocks = [b for b in srt.strip().split("\n\n") if b]
    cues = _load(REEL / "data" / f"captions{suffix}_timing.json")
    assert len(blocks) == len(cues)
    for b in blocks:
        lines = b.split("\n")[2:]
        assert 1 <= len(lines) <= 2, f"больше 2 строк: {lines}"
        for ln in lines:
            assert len(ln) <= 46, f"строка длиннее 46: {ln!r}"
    assert max(c["end"] for c in cues) <= 65.3
    # числа в субтитрах — цифрами (нет прописью «тысячи», «двадцать»)
    assert "тысячи" not in srt and "двадцать" not in srt


def test_captions_condensed_match_voice_timing():
    tts = _load(REEL / "metadata/tts_generation.json")
    take = tts["takes"]["cedar_condensed"]
    assert take["fits_scene_windows"] is True
    cues = _load(REEL / "data/captions_condensed_timing.json")
    for sc in take["scenes"]:
        ks = [c for c in cues if c["spokenScene"] == sc["scene"]]
        assert ks, f"нет субтитров реплики {sc['scene']}"
        assert abs(ks[0]["start"] - sc["placed_start"]) < 0.05


# ---------- TTS-метаданные ----------

def test_tts_metadata():
    tts = _load(REEL / "metadata/tts_generation.json")
    assert tts["model"] == "gpt-4o-mini-tts"
    assert "синтетическим голосом OpenAI" in tts["disclosure"]
    for name in ("cedar_a", "cedar_b", "marin_control", "cedar_condensed"):
        t = tts["takes"][name]
        assert t["voice"] in ("cedar", "marin")
        assert len(t["scenes"]) == 7
        for sc in t["scenes"]:
            assert re.fullmatch(r"[0-9a-f]{64}", sc["text_sha256"])


# ---------- видеофайлы ----------

def _probe(p: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,width,height,r_frame_rate",
         "-of", "json", str(p)], capture_output=True, text=True)
    return json.loads(out.stdout)


@pytest.mark.parametrize("name,audio", [
    ("nightlights_reel_v3_ru_silent.mp4", True),
    ("nightlights_reel_v3_ru_voice.mp4", True),
])
def test_video_files(name, audio):
    p = REEL / "renders" / name
    if not p.exists():
        pytest.skip(f"{name} не отрендерен")
    j = _probe(p)
    assert abs(float(j["format"]["duration"]) - 65.0) < 0.3
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (1080, 1920)
    assert v["r_frame_rate"] == "30/1"
    assert audio == any(s["codec_type"] == "audio" for s in j["streams"])


def test_loudness_manifest():
    mp = REEL / "metadata/render_manifest.json"
    if not mp.exists():
        pytest.skip("render_manifest.json не построен")
    m = _load(mp)
    for name in ("nightlights_reel_v3_ru_silent.mp4",
                 "nightlights_reel_v3_ru_voice.mp4"):
        if name not in m["renders"]:
            continue
        l = m["renders"][name]["loudness"]
        assert abs(l["integrated_lufs"] + 14) <= 1.0, name
        assert l["true_peak_dbtp"] <= -1.0, name
    assert "синтетическим голосом OpenAI" in \
        m["voiceover"]["disclosure"]


# ---------- кадры: маркировка модели и регрессия ----------

@pytest.fixture(scope="module")
def renderer():
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(REEL))
    import render
    ctx = render.Ctx()
    return render, ctx, render.load_scenes(ctx)


def _amber_fraction(img, box) -> float:
    """Доля янтарных пикселей маркировки в регионе."""
    crop = img.crop(box)
    px = list(crop.convert("RGB").getdata())
    amber = sum(1 for r, g, b in px
                if r > 170 and g > 130 and b < 170 and r > b + 40)
    return amber / len(px)


def test_model_frames_marked(renderer):
    render, ctx, scenes = renderer
    # t=58 c (модельное будущее): плашка демо-маркировки видна
    img = render.compose(ctx, scenes, int(58 * 30))
    assert _amber_fraction(
        img, (360, render.MAP_Y + 8, 1068, render.MAP_Y + 128)) > 0.01
    # t=8 c (наблюдения): в том же регионе маркировки нет
    img2 = render.compose(ctx, scenes, int(8 * 30))
    assert _amber_fraction(
        img2, (360, render.MAP_Y + 8, 1068, render.MAP_Y + 128)) < 0.005


def test_visual_regression(renderer):
    import numpy as np
    render, ctx, scenes = renderer
    if not REF.exists():
        pytest.skip("нет эталона (перегенерация: --regen)")
    ref = _load(REF)
    for gi in REG_FRAMES:
        ctx.rng = np.random.default_rng(12345)  # незав. от порядка тестов
        img = render.compose(ctx, scenes, gi)
        h = hashlib.sha256(img.tobytes()).hexdigest()
        assert h == ref[str(gi)], f"кадр {gi} отличается от эталона"


if __name__ == "__main__" and "--regen" in sys.argv:
    import numpy as np
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(REEL))
    import render
    ctx = render.Ctx()
    scenes = render.load_scenes(ctx)
    ref = {}
    for gi in REG_FRAMES:
        ctx.rng = np.random.default_rng(12345)
        img = render.compose(ctx, scenes, gi)
        ref[str(gi)] = hashlib.sha256(img.tobytes()).hexdigest()
    REF.write_text(json.dumps(ref, indent=1))
    print(f"OK: эталон {REF} ({len(ref)} кадров)")
