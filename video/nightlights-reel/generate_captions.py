#!/usr/bin/env python3
"""Субтитры рилса v3: единая разбивка для SRT, VTT и вшитых субтитров.

Источник — reel_story.json (spokenScenes). Дисплей-текст субтитров
(цифры цифрами) режется по предложениям на блоки <= 2 строк
(~46 символов/строка), тайминг равномерно распределяется по окну
сцены пропорционально длине блока. Файлы и вшитые субтитры рендера
используют ОДНУ функцию — расхождение исключено.

Запуск: python video/nightlights-reel/generate_captions.py
  -> captions/nightlights_reel_v3_ru.srt / .vtt
  -> data/captions_timing.json (для рендера)

Вариант --variant condensed: субтитры voice-версии — сокращённый
дисплей-текст (voiceover_ru_display_condensed.txt), окна реплик =
фактические placed_start/duration дубля cedar_condensed из
metadata/tts_generation.json (совпадение с озвучкой, не с равномерной
раскладкой).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
MAX_LINE = 46


def wrap2(text: str) -> list[str]:
    """<= 2 строки по MAX_LINE символов (по словам)."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if len(trial) <= MAX_LINE or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def chunks_for(text: str) -> list[str]:
    """Разбивка по смыслу: предложения, длинные — по точке с запятой
    и двоеточию; каждый чанк помещается в 2 строки."""
    parts = re.split(r"(?<=[.?!])\s+", text.strip())
    out: list[str] = []
    for p in parts:
        subs = [p]
        if len(p) > MAX_LINE * 2:
            subs = re.split(r"(?<=[;:])\s+", p)
        for s in subs:
            if len(s) > MAX_LINE * 2:
                # крайний случай: по запятой ближе к середине
                mid = len(s) // 2
                cut = s.rfind(",", 0, mid + 20)
                if cut > 10:
                    out += [s[:cut + 1].strip(), s[cut + 1:].strip()]
                else:
                    out.append(s)
            else:
                out.append(s)
    return [c for c in out if c]


def windows_story() -> list[tuple[float, float, str]]:
    """Окна реплик из reel_story (равномерная раскладка)."""
    story = json.loads((HERE / "data" / "reel_story.json").read_text())
    scenes_by_spoken: dict[str, tuple[float, float]] = {}
    for sc in story["scenes"]:
        k = str(sc["spokenScene"])
        s0, s1 = scenes_by_spoken.get(k, (sc["start"], sc["end"]))
        scenes_by_spoken[k] = (min(s0, sc["start"]), max(s1, sc["end"]))
    return [(story["spokenScenes"][str(k)]["start"],
             scenes_by_spoken[str(k)][1] - 0.2,
             story["spokenScenes"][str(k)]["text"]) for k in range(1, 8)]


def windows_condensed(take: str = "cedar_condensed") \
        -> list[tuple[float, float, str]]:
    """Окна реплик = фактические тайминги TTS-дубля."""
    tts = json.loads(
        (HERE / "metadata" / "tts_generation.json").read_text())
    scenes = tts["takes"][take]["scenes"]
    texts = [t.strip() for t in
             (HERE / "script" / "voiceover_ru_display_condensed.txt")
             .read_text("utf-8").split("\n\n") if t.strip()]
    assert len(texts) == len(scenes) == 7
    return [(sc["placed_start"], sc["placed_start"] + sc["duration_sec"],
             txt) for sc, txt in zip(scenes, texts)]


def build(variant: str = "story") -> list[dict]:
    wins = windows_story() if variant == "story" else windows_condensed()
    cues = []
    for k, (w0, w1, text) in enumerate(wins, 1):
        cks = chunks_for(text)
        weights = [len(c) for c in cks]
        total = sum(weights)
        t = w0
        for c, w in zip(cks, weights):
            dur = max(1.2, (w1 - w0) * w / total)
            end = min(t + dur, w1)
            cues.append({"start": round(t, 2), "end": round(end, 2),
                         "lines": wrap2(c), "spokenScene": k})
            t = end
    return cues


def fmt_ts(t: float, sep: str) -> str:
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["story", "condensed"],
                    default="story")
    args = ap.parse_args()
    suffix = "" if args.variant == "story" else "_condensed"
    cues = build(args.variant)
    (HERE / "data" / f"captions{suffix}_timing.json").write_text(
        json.dumps(cues, ensure_ascii=False, indent=1))
    srt = []
    for i, c in enumerate(cues, 1):
        srt += [str(i), f"{fmt_ts(c['start'], ',')} --> {fmt_ts(c['end'], ',')}",
                *c["lines"], ""]
    (HERE / "captions" / f"nightlights_reel_v3_ru{suffix}.srt").write_text(
        "\n".join(srt), encoding="utf-8")
    vtt = ["WEBVTT", ""]
    for c in cues:
        vtt += [f"{fmt_ts(c['start'], '.')} --> {fmt_ts(c['end'], '.')}",
                *c["lines"], ""]
    (HERE / "captions" / f"nightlights_reel_v3_ru{suffix}.vtt").write_text(
        "\n".join(vtt), encoding="utf-8")
    last = max(c["end"] for c in cues)
    dur = json.loads((HERE / "data" / "reel_story.json").read_text())[
        "format"]["durationSec"]
    assert last <= dur + 0.3, f"субтитры за длительностью: {last}>{dur}"
    print(f"OK[{args.variant}]: {len(cues)} субтитров, "
          f"последний до {last:.1f} c (<= {dur})")


if __name__ == "__main__":
    main()
