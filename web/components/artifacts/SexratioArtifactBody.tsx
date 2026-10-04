'use client';

import Link from 'next/link';
import { useT, useLang } from '@/lib/i18n';

const VERSIONS = [
  {
    version: '1.0.0',
    date: '2026-10-04',
    file: 'by-maps-sexratio-v1.0.0.zip',
    sizeKb: 1444,
    tag: 'artifact-sexratio-v1.0.0',
    changes:
      'Первый релиз: соотношение полов по 17 возрастным группам и 118 районам (переписи 2009 и 2019, прогноз v2026.4 до 2056), разделение полового разрыва на смертностный и не-смертностный вклад методом переписной передвижки, вердикты четырёх заранее заданных гипотез (главная опровергнута с обратным знаком), помеченный пост-хок, шесть вычислимых гейтов пройдены, три гейта исправлены датированными поправками к пререгистрации, 28 контрольных метрик.',
  },
];

export default function SexratioArtifactBody() {
  const t = useT();
  const be = useLang() === 'be';
  const p = (path: string) => (be ? '/be' + path : path);
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href={p('/artifacts')}>{t('Артефакты')}</Link> · INF-20
      </div>
      <h1>{t('Пакет: Карта, где не хватает мужчин')}</h1>
      <p className="page-lead">
        {t('Проверяемый пакет исследования ')}
        <Link href={p('/research/sexratio')}>
          {t('«Карта, где не хватает мужчин: соотношение полов по 118 районам Беларуси»')}
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
      <pre><code>{`by-maps-sexratio-v1.0.0/
├── README.md                    вопрос, вывод, как воспроизвести
├── METHODS.md · LIMITATIONS.md · VALIDATION.md
├── PREREGISTRATION.md           замороженный план + 3 датированные поправки
├── PROVENANCE.md · AGENT.md     происхождение; инструкция аудитору (человеку/LLM)
├── manifest.json · CHANGELOG.md · CITATION.cff · LICENSE.md
├── sources/registry.csv         реестр входов (лицензии, sha256)
├── params/assumptions.yaml      все допущения с обоснованиями
├── etl/sexratio.py              весь расчёт
├── data/curated/, web/public/data/   входы: переписи 2009/2019, прогноз v2026.4, таблицы смертности
├── data/final/computed_results.json   28 контрольных метрик
├── web/public/data/sexratio.json      то, что читает страница
├── code/run.sh · code/verify.py  точка входа и сверка с заявленным
└── checks/                      инварианты, ожидаемые результаты, контрольные суммы`}</code></pre>

      <h2>{t('Быстрая проверка')}</h2>
      <pre><code>{`unzip by-maps-sexratio-v1.0.0.zip && cd by-maps-sexratio-v1.0.0
bash code/run.sh
# == 1/3 Расчёт соотношений, декомпозиции, гипотез и гейтов ==
# == 2/3 Инварианты ==
# == 3/3 Сверка с заявленными результатами ==
# Все 28 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        {t('Главная гипотеза исследования опровергнута, и пакет это закрепляет: контрольная метрика h1_confirmed = 0, инвариант падает, если опровержение исчезнет. Остаток передвижки — не только миграция, но и недоучёт переписи; внешней проверки разделения «умерли / уехали» нет, потому что разреза внутренней миграции по полу в проекте нет. Полные ограничения — в LIMITATIONS.md пакета и в методблоке страницы.')}
      </p>
    </div>
  );
}
