'use client';

import Link from 'next/link';
import { useT, useLang } from '@/lib/i18n';

export default function GridArtifactBody() {
  const t = useT();
  const be = useLang() === 'be';
  const p = (path: string) => (be ? '/be' + path : path);
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href={p('/artifacts')}>{t('Артефакты')}</Link> · INF-15
      </div>
      <h1>{t('Пакет: Полотно')}</h1>
      <p className="page-lead">
        {t('Карта расселения Беларуси по сетке 1 км из GHS-POP R2023A, откалиброванная под официальные ряды районов (constrained dasymetric redistribution), 1975–2050. Проверка независимым сенсором (ночные огни) не подтвердила совпадение направления изменений (32.8% против порога 70%) — вывод о концентрации населения подаётся как открытый вопрос, не как факт.')}
      </p>

      <h2>{t('Версии')}</h2>
      <div className="card">
        <div className="card-code">v1.3.0 · 2026-07-28 · {t('git-тег')} artifact-grid-v1.3.0</div>
        <p>
          {t('MINOR: режим «История» расширен до 9 шагов — новый слой рек и матрица «река × дорога» (шаги 3-5), третья («полесская») группа опустевших районов на шаге 6. Гипотеза C-006 (растёт только пересечение реки и дороги) подтверждена направленно, но остаётся открытым вопросом. Гипотеза C-007 (максимум плотности в 2-5 км от реки, не у воды) — ОПРОВЕРГНУТА собственным заранее заданным критерием: доля населения у самой воды (0-2 км) больше, чем в 2-5 км, из-за нескольких крупных городов на берегу (см. CHANGELOG.md, D-015). Свободный режим: тумблеры для всех новых слоёв, таблица всех 119 территорий с сортировкой/CSV. 72 контрольных метрики (было 51), выводы C-1…C-5 не изменились.')}
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-grid-v1.3.0.zip" download>
            ⬇ by-maps-grid-v1.3.0.zip
          </a>
        </div>
      </div>
      <div className="card">
        <div className="card-code">v1.2.0 · 2026-07-28 · {t('git-тег')} artifact-grid-v1.2.0</div>
        <p>
          {t('MINOR: режим «История» на странице (7 пошаговых сцен, deep-link ?story=N) и новая проверка G-9 — независимо подтверждена находка: доля населения района в топ-5 плотных клетках почти не меняется эмпирически (25.6%→25.8%, 1975–2020), но прогноз даёт скачок до ~55% к 2050 — самоусиление экстраполяции по клетке, не ошибка данных; G-9 честно не пройдена по конструкции (62 из 118 районов). Данные для истории: 6 полос «правило пятисот» (C-004, подтверждено), 5 полос по расстоянию до магистрали (C-005, открытый вопрос), площадь половины населения, ранжирование районов. 51 контрольная метрика (было 26), выводы C-1/C-2/C-3 не изменились.')}
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-grid-v1.2.0.zip" download>
            ⬇ by-maps-grid-v1.2.0.zip
          </a>
        </div>
      </div>
      <div className="card">
        <div className="card-code">v1.1.0 · 2026-07-28 · {t('git-тег')} artifact-grid-v1.1.0</div>
        <p>
          {t('MINOR: доработка интерфейса страницы (дискретный ползунок по 16 узлам, режим «класс плотности» — ещё 46 кадров, режим «метры сети на жителя», коридор погрешности трека центра масс) и исправление вырожденных точек трека 1897–1959 (см. CHANGELOG.md, D-009). Трек центра масс достроен реальным прогнозом до 2050 года. 26 контрольных метрик (было 20), выводы C-1/C-2/C-3 не изменились.')}
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-grid-v1.1.0.zip" download>
            ⬇ by-maps-grid-v1.1.0.zip
          </a>
        </div>
      </div>
      <div className="card">
        <div className="card-code">v1.0.0 · 2026-07-26 · {t('git-тег')} artifact-grid-v1.0.0</div>
        <p>
          {t('Первый релиз. 10 наблюдаемых эпох (1975–2020) + прогноз до 2050 (3 сценария × 2 варианта). 20 контрольных метрик, воспроизведение на стандартной библиотеке за секунды.')}
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-grid-v1.0.0.zip" download>
            ⬇ by-maps-grid-v1.0.0.zip
          </a>
        </div>
      </div>

      <h2>{t('Состав')}</h2>
      <pre><code>{`by-maps-grid-v1.3.0/
├── README.md · AGENT.md · LIMITATIONS.md · PROVENANCE.md · METHODS.md
├── VALIDATION.md · DATA_DICTIONARY.md · EXECUTIVE_BRIEF.md · CHANGELOG.md
├── PREREGISTRATION.md · claims.yaml · CITATION.cff · LICENSE.md
├── manifest.json                    машиночитаемое описание (sha256, допуски)
├── sources/registry.csv             реестр источников (GHS-POP, OSM, огни, дороги, реки)
├── sources/raw/rasters/pop_<epoch>.tif   клетки по Беларуси, 10 эпох (откалиброваны)
├── sources/raw/metrics_observed.json · metrics_forecast.json
├── sources/raw/network_metrics.json · reconciliation.csv
├── sources/raw/story_metrics.json · g9_concentration_check.json
├── sources/raw/river_edges.csv.gz   полный граф рек OSM (waterway=river)
├── code/extract/grid_fetch.py · grid_extract.py · grid.py
├── code/extract/grid_project.py · grid_frames.py · grid_network.py
├── code/extract/grid_story.py · osm_rivers.py
├── params/assumptions.yaml          все замороженные и модельные параметры
├── code/run.sh                      единственная точка входа (стандартная библиотека)
└── checks/                          инварианты, ожидаемые результаты, chksums`}</code></pre>

      <h2>{t('Быстрая проверка')}</h2>
      <pre><code>{`unzip by-maps-grid-v1.3.0.zip && cd by-maps-grid-v1.3.0
bash code/run.sh          # только стандартная библиотека Python >= 3.10
# == 1/3 Пересчёт контрольных метрик из sources/raw ==
# == 2/3 Инварианты данных ==
# == 3/3 Сверка с заявленными результатами ==
# Все 72 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <h2>{t('Честно о находках')}</h2>
      <ul>
        <li>{t('C-007 (максимум плотности в поясе 2-5 км от реки, не у самой воды) — ОПРОВЕРГНУТА собственным заранее заданным критерием: доля населения у воды (0-2 км) больше, чем в 2-5 км, в оба сравниваемых года; причина — несколько крупных городов стоят прямо на берегу, см. CHANGELOG.md/D-015.')}</li>
        <li>{t('G-9 (внутрирайонная концентрация населения, доля в топ-5 плотных клетках района) — не пройдена по конструкции (62 из 118 районов): прогноз даёт скачок концентрации, которого не видно в исторических данных 1975–2020 — самоусиление экстраполяции по клетке, см. CHANGELOG.md/D-013.')}</li>
        <li>{t('G-1 (сверка сырого GHS-POP с официальными районами) — не пройдена; устранено калибровкой (см. METHODS.md/VALIDATION.md).')}</li>
        <li>{t('G-3 (перекрёстная проверка с ночными огнями) — не пройдена (32.8% против 70%); утверждения о концентрации населения — открытый вопрос.')}</li>
        <li>{t('G-2, G-4, G-5, G-6 — пройдены; корреляция «сеть на жителя vs убыль района» подтверждена (ρ = −0.75).')}</li>
      </ul>

      <p className="hint">
        {t('Живая версия — ')}<Link href={p('/research/grid')}>{p('/research/grid')}</Link>
        {t('; методика — кнопка «О данных и методике» на странице исследования.')}
      </p>
    </div>
  );
}
