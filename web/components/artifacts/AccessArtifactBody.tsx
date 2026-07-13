'use client';

import Link from 'next/link';
import { useT, useLang } from '@/lib/i18n';

export default function AccessArtifactBody() {
  const t = useT();
  const be = useLang() === 'be';
  const p = (path: string) => (be ? '/be' + path : path);
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href={p('/artifacts')}>{t('Артефакты')}</Link> · INF-04
      </div>
      <h1>{t('Пакет: Транспортная доступность и «тень Минска»')}</h1>
      <p className="page-lead">
        {t('Травел-таймы 118 райцентров до Минска, облцентров и переходов с ЕС по дорожному графу OSM (выгрузка 2026-07-10, md5 в реестре), пояса доступности, немонотонный профиль динамики 2015–2025 и регрессия с зарплатным контролем INF-03. Конвейер стартует с завендоренного графа; Дейкстра и OLS детерминированы.')}
      </p>

      <h2>{t('Версии')}</h2>
      <div className="card">
        <div className="card-code">v1.0.0 · 2026-07-11 · {t('git-тег')} artifact-access-v1.0.0</div>
        <p>
          {t('Первый релиз. «Тень Минска» в сырых медианах: кольцо 1,5–2,5 ч — дно (−14,2%), дальняя периферия — −12,5%; после контроля зарплаты пояса статистически слабы. Граница: 13 легковых переходов (2019) → 4 (надир 2024–2025) → 6 (июль 2026). 17 контрольных метрик.')}
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-access-v1.0.0.zip" download>
            ⬇ by-maps-access-v1.0.0.zip (13,9 МБ)
          </a>
        </div>
      </div>

      <h2>{t('Состав')}</h2>
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

      <h2>{t('Быстрая проверка')}</h2>
      <pre><code>{`unzip by-maps-access-v1.0.0.zip && cd by-maps-access-v1.0.0
bash code/run.sh          # только стандартная библиотека Python >= 3.10
# == 1/3 Травел-таймы (Дейкстра), пояса, профиль, регрессия ==
# == 2/3 Инварианты ==
# == 3/3 Сверка с заявленными результатами ==
# Все 17 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        {t('Живая версия — ')}<Link href={p('/research/access')}>{p('/research/access')}</Link>
        {t('; методика — кнопка «О данных и методике» на странице исследования.')}
      </p>
    </div>
  );
}
