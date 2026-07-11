import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Пакет forecast — версии и состав',
  description: 'Проверяемый пакет прогноза населения Беларуси 2026–2075 (v2026.1).',
};

export default function ForecastArtifactPage() {
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href="/artifacts">Артефакты</Link> · Прогноз
      </div>
      <h1>Пакет: Прогноз населения 2026–2075 (v2026.1)</h1>
      <p className="page-lead">
        Когортно-компонентный прогноз для страны, 6 областей и Минска: три
        сценария с обоснованием каждого параметра, 80% интервал, бэктест
        2009→2019 с гейтами и анализ чувствительности. Прогон детерминирован —
        воспроизведение даёт байт-в-байт те же числа.
      </p>

      <h2>Версии</h2>
      <div className="card">
        <div className="card-code">v1.0.0 · 2026-07-11 · git-тег artifact-forecast-v1.0.0 · прогноз v2026.1</div>
        <p>
          Первый релиз (этап MVP). Гейты: калибровка base-2050 = +1,0% к медиане
          UN WPP 2024 (порог ±3%); бэктест — национальный итог −0,41% (порог ±2%),
          MAPE 2,39% против 4,13% у наивной экстраполяции. 11 контрольных метрик.
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-forecast-v1.0.0.zip" download>
            ⬇ by-maps-forecast-v1.0.0.zip (821 КБ)
          </a>
        </div>
      </div>

      <h2>Состав</h2>
      <pre><code>{`by-maps-forecast-v1.0.0/
├── README.md · AGENT.md · LIMITATIONS.md · PROVENANCE.md · CHANGELOG.md
├── manifest.json                    машиночитаемое описание (sha256, допуски)
├── sources/registry.csv             реестр 18 первоисточников (WP-F1)
├── data/curated/                    входы: структуры 2026, переписи 2009/2019,
│                                    ASFR по областям, таблицы дожития, миграция
├── data/raw/wpp2024|wcde/           контрольные прогнозы ООН и WCDE
├── etl/forecast/                    код модели (CCMPP, миграция, бэктест)
│   └── scenarios/*.yaml             3 сценария, каждый параметр с обоснованием
├── params/assumptions.yaml          допущения модели с обоснованиями
├── code/run.sh                      единственная точка входа (~1 минута)
├── data/curated/forecast_v2026_1.csv · web/public/data/forecast.json   итоги
├── docs/notes/validation.md         бэктест, сверка с WPP/WCDE, чувствительность
└── checks/                          инварианты, ожидаемые результаты, chksums`}</code></pre>

      <h2>Быстрая проверка</h2>
      <pre><code>{`unzip by-maps-forecast-v1.0.0.zip && cd by-maps-forecast-v1.0.0
pip install -r code/requirements.lock   # PyYAML
bash code/run.sh
# == 1/5 Прогон прогноза (3 сценария, уровни 0-1) ==
# == 2/5 Бэктест 2009 -> 2019 ==
# == 3/5 Чувствительность ==
# == 4/5 Инварианты ==
# == 5/5 Сверка с заявленными результатами ==
# Все 11 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        Методика — кнопка «Методика прогноза» на <Link href="/">карте</Link> (в
        прогнозной зоне слайдера) или файл methods/forecast.md; валидация —
        docs/notes/validation.md внутри пакета.
      </p>
    </div>
  );
}
