'use client';

import Link from 'next/link';
import { useT, useLang } from '@/lib/i18n';

export default function AgingArtifactBody() {
  const t = useT();
  const be = useLang() === 'be';
  const p = (path: string) => (be ? '/be' + path : path);
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href={p('/artifacts')}>{t('Артефакты')}</Link> · INF-02
      </div>
      <h1>{t('Пакет: Старение районов')}</h1>
      <p className="page-lead">
        {t('Индикаторы возрастной структуры 2009/2019 для 118 районов и контрфактная когортная передвижка «при нулевой миграции». Расчёт детерминирован — воспроизведение даёт байт-в-байт те же числа.')}
      </p>

      <h2>{t('Версии')}</h2>
      <div className="card">
        <div className="card-code">v1.0.3 · 2026-07-12 · {t('git-тег')} artifact-aging-v1.0.3</div>
        <p>
          {t('Исправлен баг бисекции ОПЖ в общем модуле lifetable (найден агентным аудитом вероятностного слоя прогноза): при раннем выходе цикла возвращалось непроверенное k. На контрфакт влияние минимально (изменился один незаданный в контроле показатель — naturalCagr Кормянского района −0,24 → −0,25); все заявленные метрики без изменений.')}
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-aging-v1.0.3.zip" download>
            ⬇ by-maps-aging-v1.0.3.zip (711 КБ)
          </a>
        </div>
      </div>
      <div className="card">
        <div className="card-code">v1.0.2 · 2026-07-11 · {t('git-тег')} artifact-aging-v1.0.2</div>
        <p>
          {t('Версионно-независимая метка контрфакта; синхронизация с движком v2026.3. Метрики без изменений.')}
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-aging-v1.0.2.zip" download>
            ⬇ by-maps-aging-v1.0.2.zip (710 КБ)
          </a>
        </div>
      </div>
      <div className="card">
        <div className="card-code">v1.0.1 · 2026-07-11 · {t('git-тег')} artifact-aging-v1.0.1</div>
        <p>
          {t('Синхронизация с прогнозом v2026.2 (этап 5): обновлён вендоренный движок; все контрольные метрики без изменений.')}
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-aging-v1.0.1.zip" download>
            ⬇ by-maps-aging-v1.0.1.zip (710 КБ)
          </a>
        </div>
      </div>
      <div className="card">
        <div className="card-code">v1.0.0 · 2026-07-11 · {t('git-тег')} artifact-aging-v1.0.0</div>
        <p>
          {t('Первый релиз. Пирамиды сходятся с официальными итогами переписей (допуск — поэлементное округление, ≤17 чел. на регион); контрфакт — движок CCMPP пакета forecast (бэктест −0,41%). 10 контрольных метрик.')}
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-aging-v1.0.0.zip" download>
            ⬇ by-maps-aging-v1.0.0.zip (710 КБ)
          </a>
        </div>
      </div>

      <h2>{t('Состав')}</h2>
      <pre><code>{`by-maps-aging-v1.0.0/
├── README.md · AGENT.md · LIMITATIONS.md · PROVENANCE.md · CHANGELOG.md
├── manifest.json                    машиночитаемое описание (sha256, допуски)
├── sources/registry.csv             реестр первоисточников (WP-F1)
├── data/curated/age2009.csv, age2019.csv   переписные структуры, до человека
├── data/curated/mortality.csv, fertility_oblast.csv   входы передвижки
├── etl/aging.py                     индикаторы + контрфакт
├── etl/forecast/                    движок CCMPP (идентичен пакету forecast)
├── params/assumptions.yaml          допущения с обоснованиями
├── code/run.sh                      единственная точка входа (~10 секунд)
├── web/public/data/aging.json · data/curated/aging_indicators.csv   итоги
└── checks/                          инварианты, ожидаемые результаты, chksums`}</code></pre>

      <h2>{t('Быстрая проверка')}</h2>
      <pre><code>{`unzip by-maps-aging-v1.0.0.zip && cd by-maps-aging-v1.0.0
bash code/run.sh          # только стандартная библиотека Python >= 3.10
# == 1/3 Расчёт индикаторов и контрфактной передвижки ==
# == 2/3 Инварианты ==
# == 3/3 Сверка с заявленными результатами ==
# Все 10 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        {t('Живая версия — ')}<Link href={p('/research/aging')}>{p('/research/aging')}</Link>
        {t('; методика — кнопка «О данных и методике» на странице исследования.')}
      </p>
    </div>
  );
}
