import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Пакет mlchallenger — версии и состав',
  description: 'Проверяемый пакет ML-challenger: диагностика систематических ошибок структурной модели районов (градиентный бустинг на CCR-остатке, 2019–2026).',
};

export default function MLChallengerArtifactPage() {
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href="/artifacts">Артефакты</Link> · ML
      </div>
      <h1>Пакет: ML-challenger структурной модели районов</h1>
      <p className="page-lead">
        Градиентный бустинг (чистый Python, без sklearn/scipy/numpy) как
        challenger когортной модели районов CCR/Гамильтона-Перри — по мандату
        ROADMAP §2 «только для проверки, где статистические модели
        систематически ошибаются». Мишень — знаковая ошибка CCR на его
        единственном out-of-sample окне (2019→2026), импортируется из движка
        forecast. Это диагностика, а не конкурирующий прогноз и не инструмент
        на 50 лет. Прогон детерминирован (сеяный Монте-Карло) — воспроизведение
        даёт байт-в-байт те же числа.
      </p>

      <h2>Версии</h2>
      <div className="card">
        <div className="card-code">v1.0.0 · 2026-07-12 · git-тег artifact-mlchallenger-v1.0.0</div>
        <p>
          Первый релиз (этап 8). Бустинг предсказывает 33% дисперсии CCR-остатка
          вне выборки (OOF R²=0,33; повторная CV 0,30–0,34; перестановочный нуль
          p=0,005), из них +13 п.п. — экзогенный сигнал над структурой.
          Доминирует миграционное сальдо 2015–2019 (единственный признак явно
          вне нуль-полосы): когортная модель структурно не видит миграционную
          динамику — недооценивает пригороды с притоком (Смолевичский +8,7%),
          переоценивает районы прошлого бума (Минский −9,2%). MAPE (понижено):
          CCR 2,19% → CCR+ML 1,67% → наив 2,84%. Честность встроена: LOO-по-
          областям CV, перестановочный нуль, инвариант «на перемешанной мишени
          сигнала нет». 16 контрольных метрик.
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-mlchallenger-v1.0.0.zip" download>
            ⬇ by-maps-mlchallenger-v1.0.0.zip (872 КБ)
          </a>
        </div>
      </div>

      <h2>Состав</h2>
      <pre><code>{`by-maps-mlchallenger-v1.0.0/
├── README.md · AGENT.md · LIMITATIONS.md · PROVENANCE.md · CHANGELOG.md
├── manifest.json                     машиночитаемое описание (sha256, допуски)
├── sources/registry.csv              провенанс 12 признаков (INF-03/04/05/08 + WP-F1)
├── etl/challenger.py                 весь расчёт: панель, бустинг, нуль, важности (stdlib)
├── etl/forecast/                     движок CCR (мишень = его OOS-ошибка): sub.py +
│                                     backtest_sub.py + ccmpp/lifetable/data/migration
├── data/curated/                     входы: перепись 2009/2019, зарплаты, смертность,
│                                     чернобыльские классы, оценки 2026
├── web/public/data/                  data.json + access/migration/nightlights.json (признаки)
├── params/assumptions.yaml           гиперпараметры и допущения с обоснованием
├── code/run.sh                       единственная точка входа (~5 минут)
├── web/public/data/mlchallenger.json итог лендинга
└── checks/                           инварианты (в т.ч. «нет ложного сигнала»), метрики`}</code></pre>

      <h2>Быстрая проверка</h2>
      <pre><code>{`unzip by-maps-mlchallenger-v1.0.0.zip && cd by-maps-mlchallenger-v1.0.0
bash code/run.sh          # только стандартная библиотека Python >= 3.10, ~5 минут
# == 1/3 Панель + CCR-остаток + бустинг + перестановочный нуль ==
# == 2/3 Инварианты ==   (в т.ч.: на перемешанной мишени OOF R2 падает в нуль-полосу)
# == 3/3 Сверка с заявленными результатами ==
# Все 16 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        Живая версия — <Link href="/research/ml">/research/ml</Link>; методика —
        кнопка «Методика» на странице исследования.
      </p>
    </div>
  );
}
