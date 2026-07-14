#!/usr/bin/env python3
"""Метаданные рилса v3: metadata/data_manifest.json (хэши входных
данных) и metadata/render_manifest.json (версии, commit, хэши
результатов, громкость). Запускать после render.py и mix_audio.py.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
NL = ROOT / "web" / "public" / "data" / "nightlights"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def probe(p: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,codec_name,width,height,"
         "r_frame_rate,sample_rate", "-of", "json", str(p)],
        capture_output=True, text=True)
    j = json.loads(out.stdout)
    return {"duration_sec": round(float(j["format"]["duration"]), 2),
            "streams": [{k: v for k, v in s.items()} for s in j["streams"]]}


def loudness(p: Path) -> dict:
    err = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(p),
         "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json",
         "-f", "null", "-"], capture_output=True, text=True).stderr
    j = json.loads(err[err.rfind("{"):err.rfind("}") + 1])
    return {"integrated_lufs": float(j["input_i"]),
            "true_peak_dbtp": float(j["input_tp"])}


def main() -> None:
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
    story = json.loads((HERE / "data/reel_story.json").read_text())

    data_files = [
        HERE / "data/reel_story.json",
        HERE / "data/reel_sources.json",
        HERE / "data/research_cases.json",
        HERE / "data/captions_timing.json",
        HERE / "data/captions_condensed_timing.json",
        HERE / "script/voiceover_ru_tts.txt",
        HERE / "script/voiceover_ru_tts_condensed.txt",
        NL / "research_candidates.json",
        NL / "nightlights_manifest.json",
        ROOT / "web/public/data/nightlights_v2.json",
        ROOT / "web/public/data/forecast.json",
        ROOT / "artifacts/nightlights/params/assumptions.json",
    ]
    (HERE / "metadata/data_manifest.json").write_text(json.dumps({
        "note": "Входные данные рилса v3 и их sha256 (байт-в-байт).",
        "commit": commit,
        "files": {str(p.relative_to(ROOT)): sha(p) for p in data_files
                  if p.exists()},
    }, ensure_ascii=False, indent=1))

    renders = {}
    for name in ("nightlights_reel_v3_video.mp4",
                 "nightlights_reel_v3_video_condensed.mp4",
                 "nightlights_reel_v3_ru_silent.mp4",
                 "nightlights_reel_v3_ru_voice.mp4",
                 "nightlights_reel_v3_cover.webp",
                 "nightlights_reel_v3_preview.gif"):
        p = HERE / "renders" / name
        if not p.exists():
            continue
        rec = {"sha256": sha(p), "size_bytes": p.stat().st_size}
        if p.suffix == ".mp4":
            rec.update(probe(p))
            if "silent" in name or "voice" in name:
                rec["loudness"] = loudness(p)
        renders[name] = rec

    voice_wav = HERE / "audio/takes/cedar_condensed_aligned.wav"
    approved = HERE / "audio/approved_voiceover.wav"
    (HERE / "metadata/render_manifest.json").write_text(json.dumps({
        "reel_version": story["version"],
        "data_version": "nightlights v2.1.1 + divergence v1",
        "site_version": "v2.1.1",
        "commit": commit,
        "format": story["format"],
        "voiceover": {
            "approved": approved.exists(),
            "proposal_take": "cedar_condensed (сокращённый текст — "
                             "дословный §8 не помещается в 65 c; "
                             "см. tts_generation.json)",
            "voice_wav_sha256": sha(approved) if approved.exists()
            else (sha(voice_wav) if voice_wav.exists() else None),
            "disclosure": "Озвучка создана синтетическим голосом OpenAI",
        },
        "renders": renders,
    }, ensure_ascii=False, indent=1))
    print("OK: data_manifest.json + render_manifest.json "
          f"({len(renders)} рендеров)")


if __name__ == "__main__":
    main()
