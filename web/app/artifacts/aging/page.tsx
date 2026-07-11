import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Пакет aging — версии и состав',
  description: 'Проверяемый пакет исследования «Старение районов» (INF-02).',
};

export default function AgingArtifactPage() {
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href="/artifacts">Артефакты</Link> · INF-02
      </div>
      <h1>Пакет: Старение районов</h1>
      <p className="page-lead">
        Индикаторы возрастной структуры 2009/2019 для 118 районов и
        контрфактная когортная передвижка «при нулевой миграции». Расчёт
        детерминирован — воспроизведение даёт байт-в-байт те же числа.
      </p>

      <h2>Версии</h2>
      <div className="card">
        <div className="card-code">v1.0.0 · 2026-07-11 · git-тег artifact-aging-v1.0.0</div>
        <p>
          Первый релиз. Пирамиды сходятся с официальными итогами переписей
          (допуск — поэлементное округление, ≤17 чел. на регион); контрфакт —
          движок CCMPP пакета forecast (бэктест −0,41%). 10 контрольных метрик.
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-aging-v1.0.0.zip" download>
            ⬇ by-maps-aging-v1.0.0.zip (710 КБ)
          </a>
        </div>
      </div>

      <h2>Состав</h2>
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

      <h2>Быстрая проверка</h2>
      <pre><code>{`unzip by-maps-aging-v1.0.0.zip && cd by-maps-aging-v1.0.0
bash code/run.sh          # только стандартная библиотека Python >= 3.10
# == 1/3 Расчёт индикаторов и контрфактной передвижки ==
# == 2/3 Инварианты ==
# == 3/3 Сверка с заявленными результатами ==
# Все 10 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        Живая версия — <Link href="/research/aging">/research/aging</Link>;
        методика — кнопка «О данных и методике» на странице исследования.
      </p>
    </div>
  );
}
