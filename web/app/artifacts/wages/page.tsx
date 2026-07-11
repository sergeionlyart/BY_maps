import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Пакет wages — версии и состав',
  description: 'Проверяемый пакет исследования «Зарплата × динамика населения» (INF-03).',
};

export default function WagesArtifactPage() {
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href="/artifacts">Артефакты</Link> · INF-03
      </div>
      <h1>Пакет: Зарплата × динамика населения</h1>
      <p className="page-lead">
        Зарплатные дифференциалы 118 районов к Минску (2010–2025),
        биваритная классификация 3×3 и регрессионная эластичность
        десятилетней динамики со спецификациями устойчивости. Конвейер
        стартует с сырых ответов API Белстата; расчёт детерминирован.
      </p>

      <h2>Версии</h2>
      <div className="card">
        <div className="card-code">v1.0.0 · 2026-07-11 · git-тег artifact-wages-v1.0.0</div>
        <p>
          Первый релиз. Эластичность +5,2 п.п. на +10% дифференциала
          (t = 9,6; без пригородов Минска +2,7; переписное окно +5,5);
          знак во всех спецификациях, робастная (HC1) значимость p ≤ 0,05. 11 контрольных метрик.
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-wages-v1.0.0.zip" download>
            ⬇ by-maps-wages-v1.0.0.zip (136 КБ)
          </a>
        </div>
      </div>

      <h2>Состав</h2>
      <pre><code>{`by-maps-wages-v1.0.0/
├── README.md · AGENT.md · LIMITATIONS.md · PROVENANCE.md · CHANGELOG.md
├── manifest.json                    машиночитаемое описание (sha256, допуски)
├── sources/registry.csv             реестр с протоколом API (id, тела запросов)
├── data/raw/wages/                  сырые ответы дата-портала: зарплата
│                                    (10218000003), ВРП на душу (10202100055)
├── web/public/data/data.json        ряды населения районов (база проекта)
├── etl/wages.py                     весь расчёт, включая OLS (stdlib)
├── params/assumptions.yaml          допущения с обоснованиями
├── code/run.sh                      единственная точка входа (~5 секунд)
├── web/public/data/wages.json · data/curated/wages.csv   итоги
└── checks/                          инварианты, ожидаемые результаты, chksums`}</code></pre>

      <h2>Быстрая проверка</h2>
      <pre><code>{`unzip by-maps-wages-v1.0.0.zip && cd by-maps-wages-v1.0.0
bash code/run.sh          # только стандартная библиотека Python >= 3.10
# == 1/3 Расчёт дифференциалов, классификации и регрессий ==
# == 2/3 Инварианты ==
# == 3/3 Сверка с заявленными результатами ==
# Все 11 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        Живая версия — <Link href="/research/wages">/research/wages</Link>;
        методика — кнопка «О данных и методике» на странице исследования.
      </p>
    </div>
  );
}
