import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Пакет access — версии и состав',
  description: 'Проверяемый пакет исследования «Транспортная доступность и „тень Минска"» (INF-04).',
};

export default function AccessArtifactPage() {
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href="/artifacts">Артефакты</Link> · INF-04
      </div>
      <h1>Пакет: Транспортная доступность и «тень Минска»</h1>
      <p className="page-lead">
        Травел-таймы 118 райцентров до Минска, облцентров и переходов с ЕС
        по дорожному графу OSM (выгрузка 2026-07-10, md5 в реестре), пояса
        доступности, немонотонный профиль динамики 2015–2025 и регрессия с
        зарплатным контролем INF-03. Конвейер стартует с завендоренного
        графа; Дейкстра и OLS детерминированы.
      </p>

      <h2>Версии</h2>
      <div className="card">
        <div className="card-code">v1.0.0 · 2026-07-11 · git-тег artifact-access-v1.0.0</div>
        <p>
          Первый релиз. «Тень Минска» в сырых медианах: кольцо 1,5–2,5 ч —
          дно (−14,2%), дальняя периферия — −12,5%; после контроля зарплаты
          пояса статистически слабы. Граница: 13 легковых переходов (2019) →
          4 (надир 2024–2025) → 6 (июль 2026). 17 контрольных метрик.
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-access-v1.0.0.zip" download>
            ⬇ by-maps-access-v1.0.0.zip (13,9 МБ)
          </a>
        </div>
      </div>

      <h2>Состав</h2>
      <pre><code>{`by-maps-access-v1.0.0/
├── README.md · AGENT.md · LIMITATIONS.md · PROVENANCE.md · CHANGELOG.md
├── manifest.json                    машиночитаемое описание (sha256, допуски)
├── sources/registry.csv             OSM: версия PBF, md5, параметры графа
├── sources/registry_border.csv      источники статусов погранпереходов
├── data/raw/osm/graph_edges.csv.gz  дорожный граф: 833 438 рёбер (ODbL)
├── data/raw/border/ · data/curated/border_crossings.csv   переходы с ЕС
├── data/raw/wages/                  зарплатный контроль (сырьё INF-03)
├── etl/access.py                    весь расчёт: Дейкстра, пояса, OLS+HC1
├── etl/osm_graph.py                 документация шага извлечения из PBF
├── params/assumptions.yaml          допущения с обоснованиями
├── code/run.sh                      единственная точка входа (~1–2 мин)
├── web/public/data/access.json · data/curated/travel_times.csv   итоги
└── checks/                          инварианты, ожидаемые результаты, chksums`}</code></pre>

      <h2>Быстрая проверка</h2>
      <pre><code>{`unzip by-maps-access-v1.0.0.zip && cd by-maps-access-v1.0.0
bash code/run.sh          # только стандартная библиотека Python >= 3.10
# == 1/3 Травел-таймы (Дейкстра), пояса, профиль, регрессия ==
# == 2/3 Инварианты ==
# == 3/3 Сверка с заявленными результатами ==
# Все 17 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        Живая версия — <Link href="/research/access">/research/access</Link>;
        методика — кнопка «О данных и методике» на странице исследования.
      </p>
    </div>
  );
}
