# Рилс Nightlights v3 — воспроизводимый видеоконвейер

65-секундный вертикальный ролик (1080×1920, 30 fps) «Где данные
расходятся — там начинается исследование». Аналог Remotion на
Python/PIL/ffmpeg: структура целиком в `data/reel_story.json`,
сцены — модули `scenes/*.py`, кадры детерминированы.

## Порядок сборки

```bash
python generate_captions.py                      # SRT/VTT + тайминги
python generate_captions.py --variant condensed  # субтитры voice-версии
python generate_music.py                         # музыка 65 c (сеяно)
python generate_voiceover.py                     # TTS-дубли (нужен OPENAI_API_KEY в .env)
python render.py                                 # видеомастер (субтитры = дословный текст)
python render.py --captions data/captions_condensed_timing.json \
                 --out renders/nightlights_reel_v3_video_condensed.mp4
python mix_audio.py --voice audio/takes/cedar_condensed_aligned.wav
python build_manifests.py                        # data/render manifest
```

Проверки: `pytest etl/tests/test_nightlights_reel.py` (гейт чисел,
субтитры, LUFS/true peak, маркировка модельных кадров, визуальная
регрессия по sha256).

## Озвучка: дословный текст и сокращённая версия

Утверждённый текст §8 ТЗ (~177 слов) при спокойном документальном
темпе занимает ~110 c и не помещается в хронометраж 55–65 c ни при
каком приемлемом темпе (сцене 4 понадобилось бы ~220 слов/мин).
Поэтому:

- дословные дубли `cedar_a`, `cedar_b`, `marin_control` генерируются
  и остаются материалом для прослушивания/утверждения;
- в ролик идёт `cedar_condensed` — сокращённая версия
  (`script/voiceover_ru_tts_condensed.txt`), сохраняющая все шесть
  обязательных акцентов §14.2 дословно; её субтитры совпадают с
  озвучкой по факту (placed-тайминги из `metadata/tts_generation.json`).

Утверждение дубля: `cp audio/takes/<take>_aligned.wav
audio/approved_voiceover.wav && python mix_audio.py`.

## Медиа и версионирование

`renders/*.mp4|webp|gif` и `audio/*.wav` в git не хранятся (см.
.gitignore) — публикуются ассетами GitHub-релиза; их sha256 и
громкость фиксирует `metadata/render_manifest.json`. Ключ
`OPENAI_API_KEY` — только в локальном `.env` (вне git) или
secret-хранилище CI; TTS не вызывается из браузера и не запускается
при деплое.
