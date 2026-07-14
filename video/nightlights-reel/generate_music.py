#!/usr/bin/env python3
"""Музыка рилса v3: «Ночной радиосигнал» — программно созданный
минималистичный документальный эмбиент (права: произведение проекта,
сгенерировано кодом, CC BY 4.0 — music_license.json).

Характер (ТЗ §16): 80 BPM, мягкий низкочастотный пульс, редкие высокие
электронные точки, воздушная пад-текстура; без вокала, маршей,
трагических струнных и рекламных подъёмов. Драматургия по секциям
(§16.2): вопрос → пульс → расширение → упрощение под тезис → три
нейтральных сигнала кейсов → почти тишина на границе модели →
концентрация → открытая незавершённая гармония.

Детерминировано (seed). Запуск:
  python video/nightlights-reel/generate_music.py
    -> audio/music_master.wav (48 kHz stereo)
    -> metadata/music_license.json
"""
from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
SR = 48000
BPM = 80
DUR = 65.0
SEED = 20260714

# огибающая интенсивности по драматургии (t, пульс, пад, точки)
ENVELOPE = [
    (0.0, 0.05, 0.30, 0.0),
    (5.0, 0.35, 0.40, 0.15),
    (20.0, 0.45, 0.55, 0.25),
    (28.0, 0.25, 0.45, 0.10),
    (40.0, 0.30, 0.40, 0.35),
    (52.0, 0.04, 0.12, 0.0),
    (56.0, 0.30, 0.45, 0.10),
    (62.0, 0.20, 0.50, 0.15),
    (65.0, 0.15, 0.45, 0.0),
]


def env(t: np.ndarray, idx: int) -> np.ndarray:
    xs = [e[0] for e in ENVELOPE]
    ys = [e[idx] for e in ENVELOPE]
    return np.interp(t, xs, ys)


def main() -> None:
    rng = np.random.default_rng(SEED)
    n = int(SR * DUR)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))

    # 1) низкочастотный пульс: мягкий синусоидальный «удар» на каждую долю
    beat = 60.0 / BPM
    pulse = np.zeros(n)
    k = np.arange(int(SR * 0.5))
    kick = np.sin(2 * np.pi * 55 * k / SR * np.exp(-k / SR * 3)) \
        * np.exp(-k / SR * 7)
    for b in np.arange(0, DUR, beat):
        i = int(b * SR)
        j = min(i + len(kick), n)
        pulse[i:j] += kick[:j - i]
    pulse *= env(t, 1)
    out[:, 0] += pulse * 0.8
    out[:, 1] += pulse * 0.8

    # 2) пад: детюненные синусы (ре-минорная краска без терции в финале)
    def tone(freq, detune, pan, gain):
        lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * t + detune * 10)
        sig = (np.sin(2 * np.pi * freq * t)
               + 0.6 * np.sin(2 * np.pi * (freq * (1 + detune)) * t)) \
            * lfo * gain
        out[:, 0] += sig * (1 - pan)
        out[:, 1] += sig * pan

    pad_env = env(t, 2)
    for freq, det, pan in [(110.0, 0.003, 0.4), (146.83, 0.002, 0.6),
                           (220.0, 0.004, 0.5), (293.66, 0.0025, 0.45)]:
        tone(freq, det, pan, 0.10)
    out *= 1.0  # применим pad_env ниже к падовой части через микс
    # (проще: пад уже добавлен с постоянным гейном - промодулируем всё
    # падовой огибающей минус пульс невозможно; поэтому пад добавлен
    # умеренно, а общий баланс задан огибающими выше)
    out[:, 0] *= np.clip(pad_env + env(t, 1), 0.1, 1.2)
    out[:, 1] *= np.clip(pad_env + env(t, 1), 0.1, 1.2)

    # 3) редкие высокие точки (сеяно): пентатоника, короткие затухания
    notes = [880.0, 987.77, 1174.66, 1318.51, 1567.98]
    times = np.sort(rng.uniform(4, 63, 26))
    dot_env = env(t, 3)
    for tt in times:
        i = int(tt * SR)
        f = float(rng.choice(notes))
        L = int(SR * 0.9)
        j = min(i + L, n)
        kk = np.arange(j - i)
        sig = np.sin(2 * np.pi * f * kk / SR) * np.exp(-kk / SR * 5) * 0.10
        g = dot_env[i] if i < n else 0
        pan = float(rng.uniform(0.25, 0.75))
        out[i:j, 0] += sig * g * (1 - pan)
        out[i:j, 1] += sig * g * pan

    # 4) три нейтральных сигнала кейсов (40/44/48 c)
    for tt, f in [(40.5, 659.26), (44.5, 587.33), (48.5, 659.26)]:
        i = int(tt * SR)
        L = int(SR * 0.5)
        kk = np.arange(L)
        sig = np.sin(2 * np.pi * f * kk / SR) * np.exp(-kk / SR * 6) * 0.14
        out[i:i + L, 0] += sig
        out[i:i + L, 1] += sig

    # финал: открытая кварта (ре-соль) без разрешения
    i = int(62.2 * SR)
    kk = np.arange(n - i)
    for f, g in [(146.83, 0.10), (196.0, 0.08)]:
        sig = np.sin(2 * np.pi * f * kk / SR) * np.minimum(kk / SR / 0.8, 1) * g
        out[i:, 0] += sig
        out[i:, 1] += sig

    # мягкий лимит и нормировка с запасом (финальная громкость - в миксе)
    out = np.tanh(out * 1.2) * 0.5
    fade = np.minimum(t / 0.8, 1) * np.minimum((DUR - t) / 1.5, 1)
    out *= fade[:, None]

    pcm = (np.clip(out, -1, 1) * 32767).astype("<i2")
    dst = HERE / "audio" / "music_master.wav"
    with wave.open(str(dst), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())

    (HERE / "metadata" / "music_license.json").write_text(json.dumps({
        "music_title": "Night Radio Signal (Nightlights Reel v3)",
        "music_author": "BY Maps project (программная генерация, "
                        "generate_music.py, seed 20260714)",
        "license_type": "CC BY 4.0 (произведение проекта)",
        "license_file": "LICENSE.md (репозиторий)",
        "source": "video/nightlights-reel/generate_music.py",
        "date_acquired": "2026-07-14",
        "allowed_platforms": "все (включая коммерческие соцсети)",
    }, ensure_ascii=False, indent=1))
    print(f"OK: {dst} ({dst.stat().st_size / 1e6:.1f} МБ, {DUR} c)")


if __name__ == "__main__":
    main()
