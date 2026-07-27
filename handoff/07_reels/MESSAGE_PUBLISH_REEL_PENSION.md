# Группе разработки: опубликовать рилс R-P1 «Кто кого содержит» (INF-13)

Коллеги, распоряжение на публикацию видеоверсии исследования `/research/pension`.
Ролик доведён до канонической версии **v1.4.0** и принят автором. Работа
исследовательская закончена — от вас нужны коммит, тег, релиз и деплой.

**Материалы (использовать именно их):**

| Файл | Назначение |
|---|---|
| `handoff/07_reels/publish_reel_pension_v1.4.0.patch` | **основной артефакт**: весь патч целиком, включая mp4 и постеры (8,1 МБ) |
| `handoff/07_reels/RELEASE_NOTES_REEL_PENSION.md` | готовые release notes для GitHub-релиза, править не нужно |
| `tools/render_reel_pension.py`, `tools/reel_pension_scene.json` | конвейер и сцена 1.4.0 — из патча |
| `etl/tests/test_pension_reel.py` | 14 тестов конвейера — из патча |

Патч проверен на чистом клоне `origin/master` (`e1ac44a`): применяется без
конфликтов, `git apply --check` зелёный. sha256 патча
`c439d80162625c187e4194c0c4e8fb34d3d4663ce2f60afbdcfd49bf59ac880e`.

## Что в патче

**Конвейер.** `tools/render_reel_pension.py` и сцена `1.4.0`: бренд-интро с
контуром страны и логотипом, графический хук (пиктограммы «работающих на одного
пожилого» + лента 118 районов), панель районов, наполняющаяся во время пролёта
карты по годам, сцена «хроника» на десять районов, зеркальный бренд-финал.
Хронометраж 53,0 с, 1080×1920, 30 fps, RU и BE. Все числа, названия районов и
годы перехода вычисляются из `web/public/data/pension.json` в момент рендера —
захардкоженных цифр в сцене нет.

**Сайт.** Новый компонент `web/components/pension/ReelBlock.tsx`, вставка блока
в `PensionView.tsx` сразу после лида (до «Как читать эту карту»), стили
`.pen-reel` / `.pen-reel-block` в `globals.css`, ключи `reel.title` и
`reel.caption` во всех четырёх контент-файлах (`simple`/`pro` × RU/BE).
Медиа — `web/public/video/`: `reel_pension_ru.mp4` (3 320 940 байт),
`reel_pension_be.mp4` (3 322 667 байт), два постера webp по ~63 КБ.

**Тест.** Верхняя граница хронометража в `test_pension_reel.py` поднята с 45,0
до 53,5 с — см. п. 5, это осознанное расхождение с ТЗ, а не подгонка.

## Что уже проверено до передачи

На чистом клоне `origin/master` с применённым патчем: `npm run lint` (tsc) без
ошибок, `npm run test` — 30 passed, `npm run build` — статический экспорт
собирается, `out/video/` содержит все четыре файла. Собранный экспорт открыт в
Chromium: на `/research/pension` элемент `video.pen-reel` с
`src=/video/reel_pension_ru.mp4`, на `/be/research/pension` — с
`/video/reel_pension_be.mp4`, заголовки блока подтягиваются из контент-файлов
на обоих языках. `pytest etl/tests/test_pension_reel.py` — 14 passed.

Перепроверьте у себя, но красного быть не должно.

## Порядок работ

**1. Применить патч и закоммитить.**

```bash
git checkout master && git pull --rebase origin master
git apply handoff/07_reels/publish_reel_pension_v1.4.0.patch
npm --prefix web ci && npm --prefix web run lint && npm --prefix web run test && npm --prefix web run build
.venv/bin/python -m pytest etl/tests/test_pension_reel.py -q
git add -A
git commit -m "INF-13: рилс R-P1 v1.4.0 (53 с, RU/BE) + видеоблок на /research/pension"
git push origin master
```

**2. Собрать канонические файлы и выложить релизом.** В git они не
версионируются (`build/` в `.gitignore`) — на сайте лежит перекодировка CRF 18,
каноническая CBR-версия идёт ассетом релиза, как у INF-08 и INF-11.

```bash
.venv/bin/pip install shapely pillow numpy
.venv/bin/python tools/render_reel_pension.py --lang all   # ~2 мин на язык
#   build/reel_pension_ru.mp4  79 224 163 байта
#   build/reel_pension_be.mp4  79 224 162 байта

git tag artifact-pension-reel-v1.4.0
git push origin artifact-pension-reel-v1.4.0
gh release create artifact-pension-reel-v1.4.0 \
   build/reel_pension_ru.mp4 build/reel_pension_be.mp4 \
   web/public/video/reel_pension_ru.webp \
   --title "INF-13 «Кто кого содержит»: рилс R-P1 v1.4.0" \
   --notes-file handoff/07_reels/RELEASE_NOTES_REEL_PENSION.md
```

Контрольные суммы эталонной сборки (ffmpeg 6.1.1, Ubuntu):
`reel_pension_ru.mp4` — `442521e3c091efcc3696e76f1d77a88723445a17f5ba9b96bcade584a2752d5e`,
`reel_pension_be.mp4` — `43df392920f12d4c3bdc338c2b346c0ab4b262a70fe5d3e415d00f26953c99b4`.
Байтовое совпадение гарантировано только на той же сборке ffmpeg: кадры
детерминированы, контейнер и энкодер зависят от версии. Если суммы разошлись —
сверяйте кадры (`--dump-every 300`), а не файл целиком, и это не повод
останавливать публикацию.

**3. Задеплоить и снять смоук.**

```bash
cd web && vercel deploy --prod        # проект by-population-maps
```

```bash
curl -sI https://by-population-maps.vercel.app/video/reel_pension_ru.mp4 | head -3
curl -sI https://by-population-maps.vercel.app/video/reel_pension_be.mp4 | head -3
curl -s  https://by-population-maps.vercel.app/research/pension | grep -c pen-reel
cd web && npx playwright test e2e/pension.spec.ts
```

Глазами на телефоне: `/research/pension` и `/be/research/pension` — постер
виден без проигрывания, ролик стартует по тапу, колонку не растягивает.
Звука в ролике нет и не должно быть: все реплики титрами.

## Отдельные условия приёмки

1. **Ролик не тянется без действия пользователя.** У `<video>` стоит
   `preload="none"`, постер — 63 КБ. Страница и без него тяжёлая (geojson +
   pension.json), проверьте, что в Network при загрузке страницы mp4 не
   запрашивается.
2. **RU/BE паритет.** Белорусская страница обязана отдавать белорусский ролик
   и белорусский заголовок блока. Это разные файлы, не один с субтитрами.
3. **Числа в ролике и на странице должны совпадать.** Они совпадают по
   построению, но если после публикации пересобирается `pension.json` —
   ролик надо перерендерить и перевыложить, иначе кадры разойдутся со
   страницей. Это единственная зависимость, за которой нужно следить.

## Что осталось на решение автора, а не на вас

**Хронометраж вышел за производственное требование проекта.** В
`handoff/07_reels/REELS_SCENARIOS.md`, «Общие производственные требования»,
п. 1 записано «1080×1920, **30–45 с**». Ролик идёт 53,0 с — сознательное
решение автора от 27.07.2026 при постановке задачи на сцену «хроника».
Граница в тесте поднята до 53,5 с, в докстринге теста причина записана, но
**текст требования в REELS_SCENARIOS.md не изменён**. Требование либо
обновляется автором отдельно, либо ролик возвращается в 45 с. Сами не правьте.

**У INF-13 нет релиза и тега для пакета исследования.** В `git tag` есть
`artifact-pyramid-v1.0.0`, `artifact-nightlights-*`, `artifact-zipf-v1.0.0`,
но `artifact-pension-v1.0.0` отсутствует, хотя итоговый отчёт INF-13
(раздел 6) публикацию декларирует. Пакет `by-maps-pension-v1.0.0.zip`
(4 383 088 байт, sha256 `073182a3…`) лежит в `web/public/artifacts/` и на
проде отдаётся, то есть скачать его можно, но внешне проверяемого тега и
релиза у него нет. Раз всё равно делаете релиз для ролика — закройте этим же
заходом, это пять минут и снимает дыру в главном тезисе проекта.

**`web/public/artifacts/catalog.json` не содержит записей для `pension` и
`grid`** — общесайтовый машиночитаемый индекс пакетов не обновляется при
добавлении новых исследований. Замечено ещё в отчётах INF-13 и INF-15 обеими
группами независимо, до сих пор открыто.
