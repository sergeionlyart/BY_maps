'use client';

import Link from 'next/link';
import { useT, useLang } from '@/lib/i18n';

const VERSIONS = [
  {
    version: '1.0.0',
    date: '2026-10-04',
    file: 'by-maps-sensors-v1.0.0.zip',
    sizeKb: 308,
    tag: 'artifact-sensors-v1.0.0',
    changes:
      'Первый релиз: сверка официальной численности 118 районов со спутниковой раскладкой GHS-POP (1990–2020) и ночными огнями DMSP + VIIRS (1992–2024) по долям в национальном итоге каждого датчика, вердикты четырёх заранее заданных гипотез (H1 подтверждена, H2–H4 опровергнуты), помеченный пост-хок, пять вычислимых гейтов пройдены, одна датированная поправка к пререгистрации до расчёта, 30 контрольных метрик.',
  },
];

export default function SensorsArtifactBody() {
  const t = useT();
  const be = useLang() === 'be';
  const p = (path: string) => (be ? '/be' + path : path);
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href={p('/artifacts')}>{t('Артефакты')}</Link> · INF-22
      </div>
      <h1>{t('Пакет: Второй сенсор')}</h1>
      <p className="page-lead">
        {t('Проверяемый пакет исследования ')}
        <Link href={p('/research/sensors')}>
          {t('«Второй сенсор: сверка официальной численности районов с GHS-POP и ночными огнями»')}
        </Link>
        {t('. Весь расчёт — стандартная библиотека Python на уже завендоренных данных, без сети; воспроизведение за секунды.')}
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
      <pre><code>{`by-maps-sensors-v1.0.0/
├── README.md                    вопрос, вывод, как воспроизвести
├── METHODS.md · LIMITATIONS.md · VALIDATION.md
├── PREREGISTRATION.md           замороженный план + 1 датированная поправка
├── PROVENANCE.md · AGENT.md     происхождение; инструкция аудитору (человеку/LLM)
├── claims.yaml                  9 утверждений с классами + 2 ограничения
├── manifest.json · CHANGELOG.md · CITATION.cff · LICENSE.md
├── sources/registry.csv         реестр входов (лицензии, sha256)
├── params/assumptions.yaml      все допущения с обоснованиями
├── etl/sensors.py               весь расчёт
├── data/raw/, data/curated/, web/public/data/   входы: GHS-POP и официальный ряд (INF-15), огни (INF-08), времена в пути
├── data/final/computed_results.json   30 контрольных метрик
├── web/public/data/sensors.json       то, что читает страница
├── code/run.sh · code/verify.py  точка входа и сверка с заявленным
└── checks/                      инварианты, ожидаемые результаты, контрольные суммы`}</code></pre>

      <h2>{t('Быстрая проверка')}</h2>
      <pre><code>{`unzip by-maps-sensors-v1.0.0.zip && cd by-maps-sensors-v1.0.0
bash code/run.sh
# == 1/3 Расчёт долей, изменений, гипотез и гейтов ==
# == 2/3 Инварианты ==
# == 3/3 Сверка с заявленными результатами ==
# Все 30 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        {t('Три из четырёх гипотез опровергнуты, и пакет это закрепляет: контрольные метрики h2_confirmed, h3_confirmed, h4_confirmed = 0, инвариант падает, если опровержения исчезнут. GHS-POP не полностью независим от переписи, свет измеряет активность, а не людей. Полные ограничения — в LIMITATIONS.md пакета и в методблоке страницы.')}
      </p>
    </div>
  );
}
