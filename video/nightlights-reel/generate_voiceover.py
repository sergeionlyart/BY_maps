#!/usr/bin/env python3
"""TTS-дубли рилса v3 (ТЗ §14): OpenAI gpt-4o-mini-tts.

Дубли: cedar_a (основной), cedar_b (чуть спокойнее темп),
marin_control (контрольный голос) — дословный текст §8
(script/voiceover_ru_tts.txt); cedar_condensed — сокращённая версия
(voiceover_ru_tts_condensed.txt), укладывающаяся в тайминги §7.
Текст режется на 7 реплик по пустым строкам (= spokenScenes 1–7).
Каждая реплика — отдельный WAV; мастер дубля для прослушивания —
последовательная склейка с паузами 0,8 c. Если все реплики помещаются
в свои сценарные окна, дополнительно собирается выровненный мастер
<take>_aligned.wav длиной 65 c (реплики на start своих сцен) — именно
такой файл пригоден как approved_voiceover.wav для сведения.

Важно: дословный текст §8 (~177 слов) НЕ помещается в 65 c при
спокойном темпе — дословные дубли остаются материалом для
прослушивания/утверждения, а выровненный мастер получается только у
сокращённой версии (см. отчёт в PR).

Безопасность (§14.4): ключ OPENAI_API_KEY читается из окружения или
локального .env в корне репозитория (файл в .gitignore). Скрипт
запускается вручную после утверждения текста — НЕ из браузера и НЕ
при деплое; готовые WAV фиксируются как versioned assets.

Запуск:  python video/nightlights-reel/generate_voiceover.py
         [--takes cedar_a cedar_b marin_control]
Выход:   audio/takes/<take>/scene_{1..7}.wav, audio/takes/<take>.wav,
         metadata/tts_generation.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent

MODEL = "gpt-4o-mini-tts"
SR = 48000

INSTRUCTIONS = """Speak in Russian.

Deliver a calm, intelligent documentary narration with restrained
curiosity. Sound like a researcher inviting the audience to examine
evidence, not like a news anchor, political commentator, advertiser,
or dramatic movie trailer.

Maintain a natural pace of approximately 150–155 words per minute.
Use clear articulation and short natural pauses between paragraphs.

Place restrained emphasis on these ideas:
“не ответ, а независимый след активности”,
“главный сигнал для дополнительного исследования”,
“здесь что-то не сходится”,
“расхождение не доказывает проблему”,
“после 2024 года — модель”,
“проверьте гипотезы вместе с нами”.

The future scenario must sound exploratory rather than catastrophic.
Do not use theatrical sadness, alarm, moral judgment, whispering,
excessive excitement, or ominous intonation.

Pronounce Belarusian and Russian geographic names carefully.
Do not imitate any real person."""

BRISK = INSTRUCTIONS.replace(
    "approximately 150–155 words per minute",
    "brisk but calm — approximately 165 words per minute, with only "
    "very short pauses")

# take: (голос, инструкция, файл текста)
TAKES = {
    "cedar_a": ("cedar", INSTRUCTIONS, "voiceover_ru_tts.txt"),
    "cedar_b": ("cedar", INSTRUCTIONS.replace(
        "approximately 150–155 words per minute",
        "approximately 145–150 words per minute, slightly more "
        "measured and unhurried"), "voiceover_ru_tts.txt"),
    "marin_control": ("marin", INSTRUCTIONS, "voiceover_ru_tts.txt"),
    "cedar_condensed": ("cedar", BRISK, "voiceover_ru_tts_condensed.txt"),
}


def load_env_key() -> str | None:
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def segments(fname: str) -> list[str]:
    txt = (HERE / "script" / fname).read_text("utf-8")
    segs = [s.strip() for s in txt.split("\n\n") if s.strip()]
    assert len(segs) == 7, f"ожидалось 7 реплик, найдено {len(segs)}"
    return segs


def synth(client, voice: str, instructions: str, text: str,
          dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with client.audio.speech.with_streaming_response.create(
        model=MODEL, voice=voice, input=text,
        instructions=instructions, response_format="wav",
    ) as response:
        response.stream_to_file(dst)


def wav_dur(p: Path) -> float:
    """Реальная длительность: заголовок стримингового WAV фиктивен."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(out.stdout.strip())


def assemble_sequential(take: str) -> Path:
    """Мастер для прослушивания: реплики подряд с паузами 0,8 c."""
    d = HERE / "audio" / "takes" / take
    parts, filt = [], []
    for i in range(7):
        parts += ["-i", str(d / f"scene_{i + 1}.wav")]
        filt.append(f"[{i}:a]aresample={SR},"
                    f"aformat=channel_layouts=mono,apad=pad_dur=0.8[s{i}]")
    filt.append("".join(f"[s{i}]" for i in range(7))
                + "concat=n=7:v=0:a=1[out]")
    dst = HERE / "audio" / "takes" / f"{take}.wav"
    subprocess.run(
        ["ffmpeg", "-y", *parts, "-filter_complex", ";".join(filt),
         "-map", "[out]", "-c:a", "pcm_s16le", "-ar", str(SR), str(dst)],
        check=True, capture_output=True)
    return dst


def place(starts: list[float], durs: list[float],
          total: float) -> list[float] | None:
    """Каскадная укладка: реплика не раньше start сцены и не раньше
    конца предыдущей (+0,25 c); последняя дополнительно прижимается,
    чтобы закончиться до конца ролика. None — если укладка требует
    сдвига > 2,5 c от сценарного старта или выходит за хронометраж."""
    placed, prev_end = [], 0.0
    for i, (st, du) in enumerate(zip(starts, durs)):
        t = max(st, prev_end + 0.2)
        if i == len(starts) - 1:
            t = max(min(t, total - du), prev_end + 0.2)
        # +0.3 к хронометражу: atrim подрежет только хвост затухания
        if abs(t - st) > 2.5 or t + du > total + 0.3:
            return None
        placed.append(round(t, 2))
        prev_end = t + du
    return placed


def assemble_aligned(take: str, placed: list[float], total: float) -> Path:
    """Выровненный мастер 65 c: реплики на уложенных стартах."""
    d = HERE / "audio" / "takes" / take
    parts, filt = [], []
    for i in range(7):
        parts += ["-i", str(d / f"scene_{i + 1}.wav")]
        ms = int(placed[i] * 1000)
        filt.append(f"[{i}:a]aresample={SR},aformat=channel_layouts=mono,"
                    f"adelay={ms}:all=1[s{i}]")
    filt.append("".join(f"[s{i}]" for i in range(7))
                + f"amix=inputs=7:normalize=0,apad,atrim=0:{total}[out]")
    dst = HERE / "audio" / "takes" / f"{take}_aligned.wav"
    subprocess.run(
        ["ffmpeg", "-y", *parts, "-filter_complex", ";".join(filt),
         "-map", "[out]", "-c:a", "pcm_s16le", "-ar", str(SR), str(dst)],
        check=True, capture_output=True)
    return dst


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--takes", nargs="+", default=list(TAKES))
    ap.add_argument("--reassemble", action="store_true",
                    help="не синтезировать заново: пересобрать мастера и "
                         "метаданные из существующих scene_*.wav")
    args = ap.parse_args()

    client = openai = None
    if not args.reassemble:
        key = load_env_key()
        if not key:
            sys.exit("OPENAI_API_KEY не найден (окружение или .env в корне "
                     "репозитория). Ключ — только в secret-хранилище/.env, "
                     "никогда в Git.")
        os.environ["OPENAI_API_KEY"] = key
        try:
            import openai
            from openai import OpenAI
        except ImportError:
            sys.exit("нужен пакет openai: .venv/bin/pip install openai")

    story = json.loads((HERE / "data" / "reel_story.json").read_text())
    starts = [story["spokenScenes"][str(k)]["start"] for k in range(1, 8)]
    total = story["format"]["durationSec"]
    if not args.reassemble:
        client = OpenAI()

    # метаданные объединяются с прежними: частичный прогон (--takes X)
    # не должен терять записи других дублей
    meta_path = HERE / "metadata" / "tts_generation.json"
    meta = (json.loads(meta_path.read_text()) if meta_path.exists()
            else {"takes": {}})
    meta.update({
        "model": MODEL,
        "date_generated": dt.date.today().isoformat(),
        "instructions_sha256": hashlib.sha256(
            INSTRUCTIONS.encode()).hexdigest(),
        "disclosure": "Озвучка создана синтетическим голосом OpenAI",
    })
    if openai is not None:
        meta["sdk_version"] = openai.__version__
    for take in args.takes:
        voice, instr, script_file = TAKES[take]
        segs = segments(script_file)
        scene_meta, durs = [], []
        for i, text in enumerate(segs, 1):
            dst = HERE / "audio" / "takes" / take / f"scene_{i}.wav"
            if args.reassemble:
                if not dst.exists():
                    sys.exit(f"--reassemble: нет {dst}")
            else:
                print(f"  {take}/scene_{i} ({voice}, {len(text)} симв)…")
                synth(client, voice, instr, text, dst)
            dur = wav_dur(dst)
            durs.append(dur)
            win_end = total if i == 7 else starts[i]
            if starts[i - 1] + dur > win_end + 1.5:
                print(f"    ! реплика {i} длиннее окна: {dur:.1f} c "
                      f"(окно {win_end - starts[i - 1]:.1f} c)")
            scene_meta.append({
                "scene": i, "start": starts[i - 1],
                "duration_sec": round(dur, 2),
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            })
        master = assemble_sequential(take)
        placed = place(starts, durs, total)
        rec = {
            "voice": voice, "script_file": f"script/{script_file}",
            "instructions_sha256": hashlib.sha256(
                instr.encode()).hexdigest(),
            "master_sequential": str(master.relative_to(HERE)),
            "fits_scene_windows": placed is not None,
            "scenes": scene_meta,
        }
        if placed:
            for sm, t in zip(scene_meta, placed):
                sm["placed_start"] = t
            aligned = assemble_aligned(take, placed, total)
            rec["master_aligned"] = str(aligned.relative_to(HERE))
            print(f"OK: {master} + выровненный {aligned.name}")
        else:
            print(f"OK: {master} (в окна 65 c не помещается — только "
                  "последовательный мастер)")
        meta["takes"][take] = rec

    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print("OK: metadata/tts_generation.json")


if __name__ == "__main__":
    main()
