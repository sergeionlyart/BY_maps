import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Пакет nightlights — версии и состав',
  description: 'Проверяемый пакет исследования «Ночные огни против официальной статистики» (INF-08).',
};

export default function NightlightsArtifactPage() {
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href="/artifacts">Артефакты</Link> · INF-08
      </div>
      <h1>Пакет: Ночные огни против официальной статистики</h1>
      <p className="page-lead">
        Зональная светимость 118 районов и Минска (2015–2023) по подлинным
        композитам VIIRS (EOG average_masked VNL, обработка WorldPop),
        докризисные тренды долей и индекс расхождения «свет против
        официального населения». Конвейер стартует с завендоренной
        зональной суммы; расчёт детерминирован и идёт на стандартной
        библиотеке.
      </p>

      <h2>Версии</h2>
      <div className="card">
        <div className="card-code">v1.0.0 · 2026-07-12 · git-тег artifact-nightlights-v1.0.0</div>
        <p>
          Первый релиз. Расхождение сосредоточено в индустриальных районах
          (Жодино свет ×0,55, Борисов ×0,78, Гомельский ×0,80, Орша ×0,83
          при стабильном населении); Минск держится вровень (индекс ≈ +0,03).
          Свет — маркер расхождения, не оценка численности. 10 контрольных
          метрик.
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-nightlights-v1.0.0.zip" download>
            ⬇ by-maps-nightlights-v1.0.0.zip (476 КБ)
          </a>
        </div>
      </div>

      <h2>Состав</h2>
      <pre><code>{`by-maps-nightlights-v1.0.0/
├── README.md · AGENT.md · LIMITATIONS.md · PROVENANCE.md · CHANGELOG.md
├── manifest.json                    машиночитаемое описание (sha256, допуски)
├── sources/registry.csv             URL и sha256 годовых композитов VIIRS
├── data/raw/nightlights/zonal_light.csv   зональная светимость 119 зон x 9 лет
├── etl/nightlights.py               весь расчёт: доли, тренд, индекс (stdlib)
├── etl/nightlights_extract.py       документация шага извлечения (rasterio)
├── params/assumptions.yaml          допущения с обоснованиями
├── code/run.sh                      единственная точка входа (~2 секунды)
├── web/public/data/nightlights.json итог лендинга
└── checks/                          инварианты, ожидаемые результаты, chksums`}</code></pre>

      <h2>Быстрая проверка</h2>
      <pre><code>{`unzip by-maps-nightlights-v1.0.0.zip && cd by-maps-nightlights-v1.0.0
bash code/run.sh          # только стандартная библиотека Python >= 3.10
# == 1/3 Зональные суммы, тренды, индекс расхождения ==
# == 2/3 Инварианты ==
# == 3/3 Сверка с заявленными результатами ==
# Все 10 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        Живая версия — <Link href="/research/nightlights">/research/nightlights</Link>;
        методика — кнопка «О данных и методике» на странице исследования.
      </p>
    </div>
  );
}
