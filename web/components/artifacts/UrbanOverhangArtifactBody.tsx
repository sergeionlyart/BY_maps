'use client';

import Link from 'next/link';
import { useT, useLang } from '@/lib/i18n';

const VERSIONS = [
  {
    version: '1.0.0',
    date: '2026-07-16',
    file: 'by-maps-urban-overhang-v1.0.0.zip',
    sizeKb: 743,
    tag: 'artifact-urban-overhang-v1.0.0',
    changes:
      'Первый релиз: панель 94 городов × 10 эпох GHSL 1975–2020, морфологические контуры в 9 сценариях границ, ядро/край, ночные огни 1992–2024, современный срез OSM (дороги, сервисы, админ-границы), типология, сопоставленные пары, 17 контрольных метрик.',
  },
];

export default function UrbanOverhangArtifactBody() {
  const t = useT();
  const be = useLang() === 'be';
  const p = (path: string) => (be ? '/be' + path : path);
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href={p('/artifacts')}>{t('Артефакты')}</Link> · INF-12
      </div>
      <h1>{t('Пакет: Цена пустеющей карты')}</h1>
      <p className="page-lead">
        {t('Проверяемый пакет исследования ')}
        <Link href={p('/research/urban-overhang')}>
          {t('«Цена пустеющей карты: материальный навес городов, 1975–2020»')}
        </Link>
        {t('. Спутниковый ряд застройки GHSL × ряды населения × ночные огни × срез OSM; весь итоговый расчёт — стандартная библиотека Python, воспроизведение за секунды; растровые шаги воспроизводимы отдельно (скрипты и контрольные суммы приложены).')}
      </p>

      <h2>{t('Версии')}</h2>
      {VERSIONS.map((v) => (
        <div className="card" key={v.version}>
          <div className="card-code">v{v.version} · {v.date} · {t('git-тег')} {v.tag}</div>
          <p>{t(v.changes)}</p>
          <div className="card-foot">
            <a href={`/artifacts/${v.file}`} download>
              ⬇ {v.file} ({v.sizeKb} КБ)
            </a>
          </div>
        </div>
      ))}

      <h2>{t('Состав')}</h2>
      <pre><code>{`by-maps-urban-overhang-v1.0.0/
├── README.md                    вопрос, вывод, как воспроизвести
├── REPORT.md                    основной лонгрид исследования
├── EXECUTIVE_BRIEF.md           краткий бриф
├── METHODS.md · LIMITATIONS.md · VALIDATION.md
├── DATA_DICTIONARY.md · PROVENANCE.md · PREREGISTRATION.md
├── AGENT.md                     12 заданий для LLM-аудитора и формат отчёта
├── claims.yaml                  реестр утверждений с типами и источниками
├── manifest.json · CHANGELOG.md · CITATION.cff · LICENSE.md
├── sources/registry.csv         реестр источников (URL, лицензии, sha256)
├── sources/raw/                 вендоренные агрегаты: морфология (9 сценариев),
│                                население 94 городов, свет, дороги, POI, админ-границы
├── code/run.sh                  единственная точка входа (stdlib, ~секунды)
├── code/build.py · verify.py · fetch.py
├── code/extract/                растровые шаги (GHSL → морфология → свет → OSM)
├── params/assumptions.yaml      все допущения с обоснованиями
├── data/final/                  метрики, интервалы, типология, story.json
└── checks/                      инварианты, ожидаемые результаты, контрольные суммы`}</code></pre>

      <h2>{t('Быстрая проверка')}</h2>
      <pre><code>{`unzip by-maps-urban-overhang-v1.0.0.zip && cd by-maps-urban-overhang-v1.0.0
bash code/run.sh
# == 1/3 Расчёт от sources/raw до data/final ==
# == 2/3 Инварианты данных ==
# == 3/3 Сверка с заявленными результатами ==
# Все 17 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        {t('Глобальные тайлы GHSL (~0,8 ГБ) и снимок OSM (~0,35 ГБ) не вкладываются: они фиксируются URL и sha256, скачиваются code/fetch.py, а их зональные агрегаты завендорены — быстрое воспроизведение не требует загрузок. Валидация в CI: каждый пуш пересобирает пакет и сверяет с опубликованным байт-в-байт.')}
      </p>
    </div>
  );
}
