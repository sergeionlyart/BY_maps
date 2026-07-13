'use client';

import Link from 'next/link';
import { useT, useLang } from '@/lib/i18n';

export default function MigrationArtifactBody() {
  const t = useT();
  const be = useLang() === 'be';
  const p = (path: string) => (be ? '/be' + path : path);
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href={p('/artifacts')}>{t('Артефакты')}</Link> · INF-05
      </div>
      <h1>{t('Пакет: Внутренняя и внешняя миграция')}</h1>
      <p className="page-lead">
        {t('Сальдо миграции 128 территорий (1994–2019 + 2024–2025; 2020–2023 Белстат не публиковал), ярусы расселения 1959–2026, межобластная матрица переписи-2019 и внешняя волна 2020+ интервалами: сток ВНЖ ЕС по странам, интервал WP-F3, точечные оценки со снапшотами. Конвейер стартует с сырых ответов API; расчёт детерминирован.')}
      </p>

      <h2>{t('Версии')}</h2>
      <div className="card">
        <div className="card-code">v1.0.0 · 2026-07-12 · {t('git-тег')} artifact-migration-v1.0.0</div>
        <p>
          {t('Первый релиз. Контраст официального (+13,9 тыс. в 2019) и зеркального рядов (сток ВНЖ ЕС 133,9 → 386,8 тыс. за 2019–2024; интервал неучтённого оттока 178–416 тыс.); лестница: село −65% с 1959, Минск ×3,9, единственный нетто-магнит матрицы. 17 контрольных метрик.')}
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-migration-v1.0.0.zip" download>
            ⬇ by-maps-migration-v1.0.0.zip (2,4 МБ)
          </a>
        </div>
      </div>

      <h2>{t('Состав')}</h2>
      <pre><code>{`by-maps-migration-v1.0.0/
├── README.md · AGENT.md · LIMITATIONS.md · PROVENANCE.md · CHANGELOG.md
├── manifest.json                    машиночитаемое описание (sha256, допуски)
├── sources/registry.csv             реестр 53 файлов сырья с sha256 и датами
├── data/raw/migration/              дата-портал (индикаторы 10101300001/2/3,
│                                    тела запросов), Eurostat по 31 geo,
│                                    снапшоты всех точечных оценок
├── data/raw/mirror/                 входы интервала WP-F3
├── data/curated/migration_internal.csv   матрица F602 переписи-2019
├── etl/migration.py                 весь расчёт; etl/mirror.py - интервал
├── params/assumptions.yaml          допущения с обоснованиями
├── code/run.sh                      единственная точка входа (~5 секунд)
├── web/public/data/migration.json   итог лендинга
└── checks/                          инварианты, ожидаемые результаты, chksums`}</code></pre>

      <h2>{t('Быстрая проверка')}</h2>
      <pre><code>{`unzip by-maps-migration-v1.0.0.zip && cd by-maps-migration-v1.0.0
bash code/run.sh          # только стандартная библиотека Python >= 3.10
# == 1/3 Лестница, сальдо, матрица, внешняя волна ==
# == 2/3 Инварианты ==
# == 3/3 Сверка с заявленными результатами ==
# Все 17 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        {t('Живая версия — ')}<Link href={p('/research/migration')}>{p('/research/migration')}</Link>
        {t('; методика — кнопка «О данных и методике» на странице исследования.')}
      </p>
    </div>
  );
}
