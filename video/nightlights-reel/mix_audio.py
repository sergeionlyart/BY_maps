#!/usr/bin/env python3
"""Сведение рилса v3 (ТЗ §17) и упаковка результатов.

silent-версия: только музыка; voice-версия: голос + музыка с
автоматическим ducking 6–8 dB (sidechaincompress). Обе нормируются
двухпроходным loudnorm к −14 LUFS integrated / true peak ≤ −1 dBTP,
AAC 48 kHz, и мультиплексируются с видеомастером. Дополнительно —
обложка cover.webp и preview.gif.

Запуск: python video/nightlights-reel/mix_audio.py [--voice PATH]
  голос по умолчанию audio/approved_voiceover.wav (если файла нет —
  собирается только silent-версия; это не ошибка: TTS-дубли ждут
  утверждения).
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
MUSIC = HERE / "audio" / "music_master.wav"
VIDEO = HERE / "renders" / "nightlights_reel_v3_video.mp4"  # для silent
# voice-версия использует видео с субтитрами, совпадающими с озвучкой


def run(args: list[str]) -> str:
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"ffmpeg error:\n{r.stderr[-2000:]}")
    return r.stderr


def loudnorm_2pass(filter_pre: list[str], inputs: list[str],
                   out_label: str) -> str:
    """Первый проход: измерение. Возвращает loudnorm с measured_*."""
    probe_filter = ";".join(
        filter_pre + [f"[{out_label}]loudnorm=I=-14:TP=-1:LRA=11:"
                      "print_format=json[ln]"])
    err = run(["ffmpeg", "-hide_banner", "-nostats", *inputs,
               "-filter_complex", probe_filter, "-map", "[ln]",
               "-f", "null", "-"])
    j = json.loads(err[err.rfind("{"):err.rfind("}") + 1])
    return (f"loudnorm=I=-14:TP=-1.5:LRA=11:linear=true"
            f":measured_I={j['input_i']}:measured_TP={j['input_tp']}"
            f":measured_LRA={j['input_lra']}"
            f":measured_thresh={j['input_thresh']}"
            f":offset={j['target_offset']}")


def mux(audio_filter: str, inputs: list[str], dst: Path) -> None:
    run(["ffmpeg", "-y", "-i", str(VIDEO), *inputs,
         "-filter_complex", audio_filter, "-map", "0:v", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", str(dst)])
    print(f"OK: {dst.name} ({dst.stat().st_size / 1e6:.1f} МБ)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice",
                    default=str(HERE / "audio/approved_voiceover.wav"))
    ap.add_argument("--voice-video", default=str(
        HERE / "renders/nightlights_reel_v3_video_condensed.mp4"),
        help="видеомастер для voice-версии (субтитры = озвучка)")
    args = ap.parse_args()
    if not VIDEO.exists():
        raise SystemExit("нет видеомастера — сначала render.py")

    # silent: музыка -> loudnorm (2 прохода)
    ln = loudnorm_2pass(["[0:a]anull[m]"], ["-i", str(MUSIC)], "m")
    mux(f"[1:a]{ln},aresample=48000[a]", ["-i", str(MUSIC)],
        HERE / "renders" / "nightlights_reel_v3_ru_silent.mp4")

    voice = Path(args.voice)
    if voice.exists():
        # voice: музыка дакается голосом на 6-8 dB, затем микс и loudnorm
        duck = ("[m][vs]sidechaincompress=threshold=0.015:ratio=8:"
                "attack=90:release=500:makeup=1[md]")
        pre = ["[0:a]anull[m]", "[1:a]asplit=2[v][vs]",
               duck, "[md][v]amix=inputs=2:normalize=0[mx]"]
        inputs = ["-i", str(MUSIC), "-i", str(voice)]
        ln = loudnorm_2pass(pre, inputs, "mx")
        graph = ";".join([
            "[1:a]anull[m]", "[2:a]asplit=2[v][vs]",
            "[m][vs]sidechaincompress=threshold=0.015:ratio=8:"
            "attack=90:release=500:makeup=1[md]",
            f"[md][v]amix=inputs=2:normalize=0,{ln},aresample=48000[a]"])
        voice_video = Path(args.voice_video)
        if not voice_video.exists():
            voice_video = VIDEO
        mux_dst = HERE / "renders" / "nightlights_reel_v3_ru_voice.mp4"
        run(["ffmpeg", "-y", "-i", str(voice_video), *inputs,
             "-filter_complex", graph, "-map", "0:v", "-map", "[a]",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-ar", "48000", "-movflags", "+faststart", str(mux_dst)])
        # финальный микс отдельным WAV (структура §18)
        run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join([
            "[0:a]anull[m]", "[1:a]asplit=2[v][vs]",
            "[m][vs]sidechaincompress=threshold=0.015:ratio=8:"
            "attack=90:release=500:makeup=1[md]",
            f"[md][v]amix=inputs=2:normalize=0,{ln}[a]"]),
            "-map", "[a]", "-c:a", "pcm_s16le", "-ar", "48000",
            str(HERE / "audio" / "final_mix.wav")])
        print(f"OK: {mux_dst.name} "
              f"({mux_dst.stat().st_size / 1e6:.1f} МБ) + final_mix.wav")
    else:
        print(f"голос не найден ({voice.name}) — только silent-версия; "
              "после утверждения дубля: cp audio/takes/<take>.wav "
              "audio/approved_voiceover.wav && повторить")

    # обложка (сцена расхождения, t=33 c; webp через Pillow) и превью-GIF
    cov_png = HERE / "renders" / "_cover_tmp.png"
    run(["ffmpeg", "-y", "-ss", "33", "-i", str(VIDEO), "-frames:v", "1",
         str(cov_png)])
    from PIL import Image
    Image.open(cov_png).save(
        HERE / "renders" / "nightlights_reel_v3_cover.webp",
        quality=90, method=6)
    cov_png.unlink()
    run(["ffmpeg", "-y", "-i", str(VIDEO),
         "-vf", "fps=5,scale=270:-1:flags=lanczos", "-loop", "0",
         str(HERE / "renders" / "nightlights_reel_v3_preview.gif")])
    print("OK: cover.webp + preview.gif")


if __name__ == "__main__":
    main()
