import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Пакет shocks — версии и состав',
  description: 'Проверяемый пакет исследования «Демографические шоки XX века» (INF-09).',
};

export default function ShocksArtifactPage() {
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href="/artifacts">Артефакты</Link> · INF-09
      </div>
      <h1>Пакет: Демографические шоки XX века</h1>
      <p className="page-lead">
        Национальный ряд населения 1897–2026 с событийными вехами (каждая
        с источником), оцифровка переписи-1897 по родному языку по 38
        городам и данные «города до/после» Холокоста. Расчёт
        детерминирован, стандартная библиотека.
      </p>

      <h2>Версии</h2>
      <div className="card">
        <div className="card-code">v1.0.0 · 2026-07-12 · git-тег artifact-shocks-v1.0.0</div>
        <p>
          Первый релиз. 9 сорсенных вех (беженство 1915 → распад СССР 1991),
          перепись-1897 (местечки с 55–90% еврейского населения), обрыв ВМВ
          9,05→7,71 млн. Холокост подан как исчезновение местечка (доля-1897
          как мера утраченного, не оценка жертв города). 8 контрольных метрик.
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-shocks-v1.0.0.zip" download>
            ⬇ by-maps-shocks-v1.0.0.zip
          </a>
        </div>
      </div>

      <h2>Состав</h2>
      <pre><code>{`by-maps-shocks-v1.0.0/
├── README.md · AGENT.md · LIMITATIONS.md · PROVENANCE.md · CHANGELOG.md
├── manifest.json                     машиночитаемое описание (sha256, допуски)
├── sources/registry.csv              sha256 сырья + провенанс
├── data/raw/shocks/                  перепись-1897 (язык/религия), события,
│                                     Холокост (все с источниками)
├── etl/shocks.py                     сборка ряда, долей, событий (stdlib)
├── params/assumptions.yaml           допущения с обоснованиями
├── code/run.sh                       единственная точка входа (~2 секунды)
├── web/public/data/shocks.json       итог лендинга
└── checks/                           инварианты, ожидаемые результаты, chksums`}</code></pre>

      <h2>Быстрая проверка</h2>
      <pre><code>{`unzip by-maps-shocks-v1.0.0.zip && cd by-maps-shocks-v1.0.0
bash code/run.sh          # только стандартная библиотека Python >= 3.10
# Все 8 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        Живая версия — <Link href="/research/shocks">/research/shocks</Link>;
        методика — кнопка «О данных и методике» на странице исследования.
      </p>
    </div>
  );
}
