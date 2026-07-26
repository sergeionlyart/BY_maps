'use client';

import Link from 'next/link';
import { useT, useLang } from '@/lib/i18n';

const VERSIONS = [
  {
    version: '1.0.0',
    date: '2026-07-26',
    file: 'by-maps-pension-v1.0.0.zip',
    sizeKb: 4280,
    tag: 'artifact-pension-v1.0.0',
    changes:
      'Первый релиз: коэффициент поддержки (SR) и полная нагрузка (TDR) по 118 районам и стране, 1989–2056 (районы — с 2009 года), 3 сценария × 2 стартовых ряда × 3 варианта пенсионного возраста, год перехода трёх порогов (интервалом на районном уровне — гейт G-3), условная денежная арифметика (CG) с подавлением для пригородов Минска, 12 главных утверждений с классами DATA/CALC/MODEL/INTERPRETATION, 7 проверок валидации.',
  },
];

export default function PensionArtifactBody() {
  const t = useT();
  const be = useLang() === 'be';
  const p = (path: string) => (be ? '/be' + path : path);
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href={p('/artifacts')}>{t('Артефакты')}</Link> · INF-13
      </div>
      <h1>{t('Пакет: Кто кого содержит')}</h1>
      <p className="page-lead">
        {t('Проверяемый пакет исследования ')}
        <Link href={p('/research/pension')}>
          {t('«Кто кого содержит: коэффициент поддержки по 118 районам Беларуси»')}
        </Link>
        {t('. Демографический расчёт по годовой законной границе трудоспособного возраста + условная денежная арифметика; весь итоговый расчёт — стандартная библиотека Python, воспроизведение за секунды.')}
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
      <pre><code>{`by-maps-pension-v1.0.0/
├── README.md                    вопрос, вывод, как воспроизвести
├── EXECUTIVE_BRIEF.md           краткий бриф [ДАННЫЕ]/[РАСЧЁТ]/[МОДЕЛЬ]/[ИНТЕРПРЕТАЦИЯ]
├── METHODS.md · LIMITATIONS.md · VALIDATION.md
├── DATA_DICTIONARY.md · PROVENANCE.md · PREREGISTRATION.md
├── AGENT.md                     инструкции независимому аудитору (человеку/LLM)
├── claims.yaml                  12 главных утверждений с классами и источниками
├── manifest.json · CHANGELOG.md · CITATION.cff · LICENSE.md
├── sources/registry.csv         реестр источников (URL, лицензии, sha256)
├── sources/raw/                 5 вендоренных документальных источников
├── params/assumptions.yaml      все допущения денежного слоя с обоснованиями
├── etl/                         pension.py + минимальное подмножество зависимостей
├── data/curated/, data/raw/, web/public/data/   входные данные (пути как в репозитории)
├── data/final/computed_results.json   14 контрольных метрик (канонический снимок)
├── web/public/data/pension.json       полные ряды SR/TDR/crossing/CG — то, что читает страница
├── code/run.sh                  единственная точка входа (stdlib, секунды)
├── code/verify.py                сверка с checks/expected_results.json
└── checks/                      инварианты, ожидаемые результаты, контрольные суммы`}</code></pre>

      <h2>{t('Быстрая проверка')}</h2>
      <pre><code>{`unzip by-maps-pension-v1.0.0.zip && cd by-maps-pension-v1.0.0
bash code/run.sh
# == 1/3 Расчёт от sources/raw до data/final ==
# == 2/3 Инварианты данных ==
# == 3/3 Сверка с заявленными результатами ==
# 14 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        {t('Годовая законная граница трудоспособного возраста (не константа) — реформа 2017–2022 учтена погодично. Год перехода районов — интервал, а не точная дата (гейт G-3 не пройден на районном уровне). Условная денежная арифметика — не реальные доходы или расходы района: общереспубликанский пенсионный фонд по районам не делится. Полные ограничения — в LIMITATIONS.md пакета и в методблоке страницы.')}
      </p>
    </div>
  );
}
