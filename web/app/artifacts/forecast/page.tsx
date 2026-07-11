import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Пакет forecast — версии и состав',
  description: 'Проверяемый пакет прогноза населения Беларуси 2026–2075 (v2026.2, уровни 0–3).',
};

export default function ForecastArtifactPage() {
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href="/artifacts">Артефакты</Link> · Прогноз
      </div>
      <h1>Пакет: Прогноз населения 2026–2075 (v2026.2)</h1>
      <p className="page-lead">
        Прогноз всех уровней: страна, 6 областей, Минск (CCMPP), 118 районов
        (Гамильтон–Перри с IPF-согласованием), ~200 городов (доли в районах,
        облцентры — собственные когортные модели). Три сценария с обоснованием
        каждого параметра, 80% интервал (уровни 0–1), три бэктеста с гейтами.
        Прогон детерминирован — воспроизведение даёт байт-в-байт те же числа.
      </p>

      <h2>Версии</h2>
      <div className="card">
        <div className="card-code">v1.1.0 · 2026-07-11 · git-тег artifact-forecast-v1.1.0 · прогноз v2026.2</div>
        <p>
          Этап 5: добавлены уровни 2–3. Районы — CCR 2009→2019 со shrinkage и
          чернобыльским floor; города — логистические доли; 5 облцентров —
          CCMPP. Гейты: бэктест районов 2019→2026 MAPE 2,12% против 2,76%
          наивной; бэктест городов 6,7% против 10,9%. Уровни 0–1 идентичны
          v2026.1. 19 контрольных метрик.
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-forecast-v1.1.0.zip" download>
            ⬇ by-maps-forecast-v1.1.0.zip (1072 КБ)
          </a>
        </div>
      </div>
      <div className="card">
        <div className="card-code">v1.0.1 · 2026-07-11 · git-тег artifact-forecast-v1.0.1 · прогноз v2026.1</div>
        <p>
          Исправление входных данных по итогам агентного аудита этапа 4:
          устранена коллизия territory_id в age2009/age2019.csv (Октябрьский
          район Минска против Октябрьского района Гомельской области). Все
          результаты прогноза идентичны v1.0.0 — коллизия на модель не влияла.
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-forecast-v1.0.1.zip" download>
            ⬇ by-maps-forecast-v1.0.1.zip (822 КБ)
          </a>
        </div>
      </div>
      <div className="card">
        <div className="card-code">v1.0.0 · 2026-07-11 · git-тег artifact-forecast-v1.0.0 · прогноз v2026.1</div>
        <p>
          Первый релиз (этап MVP). Гейты: калибровка base-2050 = +1,0% к медиане
          UN WPP 2024 (порог ±3%); бэктест — национальный итог −0,41% (порог ±2%),
          MAPE 2,39% против 4,13% у наивной экстраполяции. 11 контрольных метрик.
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-forecast-v1.0.0.zip" download>
            ⬇ by-maps-forecast-v1.0.0.zip (822 КБ)
          </a>
        </div>
      </div>

      <h2>Состав (v1.1.0)</h2>
      <pre><code>{`by-maps-forecast-v1.1.0/
├── README.md · AGENT.md · LIMITATIONS.md · PROVENANCE.md · CHANGELOG.md
├── manifest.json                    машиночитаемое описание (sha256, допуски)
├── sources/registry.csv             реестр 18 первоисточников (WP-F1)
├── data/curated/                    входы: структуры 2026, переписи 2009/2019
│                                    (по районам!), ASFR, таблицы дожития,
│                                    миграция, city_raion.csv, chernobyl_zones.csv
├── web/public/data/data.json        ряды районов и городов 1897-2026
├── data/raw/wpp2024|wcde/           контрольные прогнозы ООН и WCDE
├── etl/forecast/                    код: CCMPP (run.py) + Гамильтон-Перри и
│   │                                города (sub.py) + бэктесты (backtest*.py)
│   └── scenarios/*.yaml             3 сценария, каждый параметр с обоснованием
├── params/assumptions.yaml          допущения модели с обоснованиями
├── code/run.sh                      единственная точка входа (~2 минуты)
├── data/curated/forecast_v2026_2.csv · web/public/data/forecast.json   итоги
├── docs/notes/validation.md · backtest_sub.json   валидация и бэктесты
└── checks/                          инварианты, ожидаемые результаты, chksums`}</code></pre>

      <h2>Быстрая проверка</h2>
      <pre><code>{`unzip by-maps-forecast-v1.1.0.zip && cd by-maps-forecast-v1.1.0
pip install -r code/requirements.lock   # PyYAML
bash code/run.sh
# == 1/6 Прогон прогноза (3 сценария, уровни 0-3) ==
# == 2/6 Бэктест уровней 0-1 (2009 -> 2019) ==
# == 3/6 Бэктесты уровней 2-3 (районы 2019->2026, города <=2009->2019) ==
# == 4/6 Чувствительность ==
# == 5/6 Инварианты ==
# == 6/6 Сверка с заявленными результатами ==
# Все 19 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        Методика — кнопка «Методика прогноза» на <Link href="/">карте</Link> (в
        прогнозной зоне слайдера) или файл methods/forecast.md; валидация —
        docs/notes/validation.md внутри пакета.
      </p>
    </div>
  );
}
