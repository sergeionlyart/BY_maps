'use client';

import Link from 'next/link';
import { useT, useLang } from '@/lib/i18n';

const VERSIONS = [
  {
    version: '1.0.0',
    date: '2026-07-11',
    file: 'by-maps-zipf-v1.0.0.zip',
    sizeKb: 66,
    tag: 'artifact-zipf-v1.0.0',
    changes:
      'Первый релиз: 12 срезов 1897–2026, наклоны Габэ–Ибрагимова по топ-20/30/50, примация, 8 контрольных метрик с допуском ±0,001.',
  },
];

export default function ZipfArtifactBody() {
  const t = useT();
  const be = useLang() === 'be';
  const p = (path: string) => (be ? '/be' + path : path);
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href={p('/artifacts')}>{t('Артефакты')}</Link> · INF-01
      </div>
      <h1>{t('Пакет: Иерархия городов и закон Ципфа')}</h1>
      <p className="page-lead">
        {t('Проверяемый пакет исследования ')}
        <Link href={p('/research/zipf')}>{t('«Иерархия городов и закон Ципфа, 1897–2026»')}</Link>
        {t('. Один источник (222 города, переписи 1897–2019 + оценки), весь расчёт — стандартная библиотека Python, воспроизведение ~10 секунд.')}
      </p>

      <h2>{t('Версии')}</h2>
      {VERSIONS.map((v) => (
        <div className="card" key={v.version}>
          <div className="card-code">v{v.version} · {v.date} · {t('git-тег')} {v.tag}</div>
          <p>{t(v.changes)}</p>
          <div className="card-foot">
            <a href={`/artifacts/${v.file}`} download>⬇ {v.file} ({v.sizeKb} КБ)</a>
          </div>
        </div>
      ))}

      <h2>{t('Состав')}</h2>
      <pre><code>{`by-maps-zipf-v1.0.0/
├── README.md                    вопрос, вывод, как воспроизвести
├── manifest.json                машиночитаемое описание (файлы, sha256, допуски)
├── AGENT.md                     задачи для LLM-агента и формат отчёта
├── LIMITATIONS.md               7 известных ограничений
├── PROVENANCE.md                цепочка источник → преобразование → результат
├── CITATION.cff · LICENSE.md
├── sources/registry.csv         реестр источников (URL, лицензия, дата, sha256)
├── sources/raw/ps_cities.html   завендоренный сырой источник
├── code/run.sh                  единственная точка входа
├── code/build.py                весь расчёт (стандартная библиотека)
├── code/fetch.py · verify.py · requirements.lock
├── params/assumptions.yaml      6 допущений с обоснованиями
├── data/final/                  ранжировки, наклоны, примация, контрольные метрики
└── checks/                      инварианты, ожидаемые результаты, контрольные суммы`}</code></pre>

      <h2>{t('Быстрая проверка')}</h2>
      <pre><code>{`unzip by-maps-zipf-v1.0.0.zip && cd by-maps-zipf-v1.0.0
bash code/run.sh
# == 1/3 Расчёт от sources/raw до data/final ==
# == 2/3 Инварианты данных ==
# == 3/3 Сверка с заявленными результатами ==
# Все 8 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        {t('Валидация в CI: каждый пуш пересобирает пакет и сверяет с опубликованным байт-в-байт; полный прогон run.sh — часть пайплайна.')}
      </p>
    </div>
  );
}
