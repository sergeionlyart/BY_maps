# Население Беларуси, 1897–2026

Интерактивный исследовательский веб-сервис: изменение численности, плотности и
концентрации населения Беларуси за 120 лет — страна, области, 118 районов,
220+ городов и городских посёлков. Переписи 1897–2019, официальные оценки до
2026 года.

**Гипотеза исследования:** долговременное сокращение населения сельских
территорий и малых районов и его концентрация в Минске, областных центрах и
крупнейших городах. Сервис позволяет проверить её визуально (карта изменения
к любому базовому году, фильтр «район без городского центра») и количественно
(панель урбанизации: доля городского населения 9,7% в 1897 → ~78% сейчас, доля
Минска 1,4% → ~22%).

## Структура

```
etl/            воспроизводимый ETL-пайплайн (Python, без внешних зависимостей,
                кроме shapely; тесты - pytest)
data/raw/       завендоренные сырые источники (HTML/GeoJSON/JSON) + curated CSV
web/            Next.js 15 + TypeScript + MapLibre GL (статический экспорт)
web/public/data/  результаты ETL: data.json + geo/*.geojson
docs/           SOURCES.md (источники), METHODOLOGY.md (методика)
```

## Воспроизведение

```bash
# 1. ETL (данные уже завендорены; --force перезагрузит из сети)
python3 -m venv .venv && .venv/bin/pip install shapely pytest
.venv/bin/python -m etl.fetch          # проверка/загрузка сырых данных
.venv/bin/python -m etl.build          # сборка web/public/data
.venv/bin/python -m pytest etl/tests/  # инварианты данных

# 2. Веб-приложение
cd web && npm install
npm run test      # vitest
npm run lint      # tsc --noEmit
npm run dev       # http://localhost:3000
npm run build     # статический экспорт в web/out
```

## Деплой

Статический сайт (Next.js `output: 'export'`), деплой на Vercel:

```bash
cd web && vercel deploy --prod
```

CI (GitHub Actions, `.github/workflows/ci.yml`): pytest → vitest → tsc →
next build на каждый push.

## Исследования и проверяемые артефакты

Помимо карты, проект публикует исследования (`/research`) — каждое с
методологическим блоком (8 обязательных полей, шаблон в
[docs/templates/method-block.md](docs/templates/method-block.md)) и
**проверяемым пакетом артефактов** по стандарту
[docs/ARTIFACT_STANDARD.md](docs/ARTIFACT_STANDARD.md): данные + код +
допущения + инструкции для LLM-агента. Раздел `/artifacts` объясняет, как
скачать пакет, воспроизвести расчёт одной командой и оспорить допущения.

```bash
# сборка и валидация пакетов
.venv/bin/python -m etl.zipf                       # расчёт INF-01 -> zipf.json
.venv/bin/python -m etl.artifacts.build zipf       # пакет -> web/public/artifacts/
.venv/bin/python -m etl.artifacts.build --all --check  # байт-воспроизводимость (CI-гейт)
.venv/bin/python -m etl.artifacts.validate --all   # полный прогон run.sh + сверка допусков
```

Первый пилот конвейера — INF-01 «Иерархия городов и закон Ципфа»
(`/research/zipf`, пакет `by-maps-zipf-v1.0.0.zip`). План работ —
[docs/TASK_SPEC.md](docs/TASK_SPEC.md), дорожная карта прогноза 2026–2075 —
[docs/ROADMAP_FORECAST.md](docs/ROADMAP_FORECAST.md).

## Данные и методика

- [docs/SOURCES.md](docs/SOURCES.md) — все источники с URL и лицензиями;
- [docs/METHODOLOGY.md](docs/METHODOLOGY.md) — гармонизация границ и названий,
  уровни достоверности (перепись / оценка / ретроспектива / вычислено /
  интерполяция), известные ограничения.

Каждое значение в `data.json` несёт тип достоверности; интерфейс показывает
его в тултипах и карточках.
