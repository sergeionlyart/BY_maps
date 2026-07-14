'use client';

import Link from 'next/link';
import { useT, useLang } from '@/lib/i18n';

export default function NightlightsArtifactBody() {
  const t = useT();
  const be = useLang() === 'be';
  const p = (path: string) => (be ? '/be' + path : path);
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href={p('/artifacts')}>{t('Артефакты')}</Link> · INF-08
      </div>
      <h1>{t('Пакет: Беларусь из космоса, 1992–2075')}</h1>
      <p className="page-lead">
        {t('Гармонизированная ночная светимость 118 районов и Минска за 33 года (DMSP 1992–2011 + VIIRS 2012–2024, стык «мостом» с гейтами R² ≥ 0,9 и разрывом ≤ 5%), индекс расхождения «свет против населения» и модельная иллюстрация будущего 2030–2075 по трём сценариям прогноза v2026.4. Вендорены вырезки растров по Беларуси; конвейер от зональных сумм — стандартная библиотека; рилс-конвейер включён и детерминирован.')}
      </p>

      <h2>{t('Связанный пакет: расхождение свет/статистика')}</h2>
      <div className="card">
        <div className="card-code">nightlights-divergence v1.0.0 · 2026-07-14 · {t('git-тег')} artifact-nightlights-divergence-v1.0.0</div>
        <p>
          {t('Пересчёт кандидатов H1–H3 (Минская агломерация +31,2% в уровнях, Смолевичи–Жодино −27,3% в долях, Островец +23,1% в долях), декомпозиция по 119 зонам и внешняя проверка открытой статистикой: промпроизводство районов (Жодино 2019→2021 — 84,4%, Островец — 376,6% с вводом БелАЭС), занятость, зарплата, миграция, электроэнергия. Статус кейсов — «кандидат»: согласованность рядов не устанавливает причину. 15 контрольных метрик; stdlib.')}
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-nightlights-divergence-v1.0.0.zip" download>
            ⬇ by-maps-nightlights-divergence-v1.0.0.zip (294 КБ)
          </a>
        </div>
      </div>

      <h2>{t('Версии')}</h2>
      <div className="card">
        <div className="card-code">v2.1.1 · 2026-07-14 · {t('git-тег')} artifact-nightlights-v2.1.1</div>
        <p>
          {t('PATCH: скорость воспроизведения снижена вдвое по решению автора — адаптивные длительности событийного слоя 760–2700 мс (остановка на переходах 3000 мс), сцена рилса ~97 с. Аналитика, события и кадры без изменений.')}
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-nightlights-v2.1.1.zip" download>
            ⬇ by-maps-nightlights-v2.1.1.zip (4,6 МБ)
          </a>
        </div>
      </div>
      <div className="card">
        <div className="card-code">v2.1.0 · 2026-07-14 · {t('git-тег')} artifact-nightlights-v2.1.0</div>
        <p>
          {t('MINOR: разделение аналитического и визуального слоёв (аналитические числа v2.0.0 без изменений). Визуальный ряд: 1992–2011 — шаблонная VIIRS-like реконструкция, 2012–2024 — наблюдения, 2030–2075 — модель; манифест кадров с sha256; delta-слои с единой шкалой; события и адаптивная скорость из аналитического z-скоринга (методологические переходы исключены, причины — только ручные аннотации с источником). 21 контрольная метрика.')}
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-nightlights-v2.1.0.zip" download>
            ⬇ by-maps-nightlights-v2.1.0.zip (4,6 МБ)
          </a>
        </div>
      </div>
      <div className="card">
        <div className="card-code">v2.0.0 · 2026-07-14 · {t('git-тег')} artifact-nightlights-v2.0.0</div>
        <p>
          {t('MAJOR: ряд 9→33 года + модель до 2075. Ретро — DMSP в калибровке Li et al.; современность — EOG VNL v2.1 (зеркало OpenGeoHub); сюжет v1 воспроизведён на независимом источнике (Смолевичский −0,45, Минск +0,07); самый быстрый рост света — Островецкий район (БелАЭС). Модель: light = bright·(pop-ratio)^β + floor, β из межрайонной эластичности; каждый модельный кадр несёт впечатанный маркер «МОДЕЛЬ». 17 контрольных метрик.')}
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-nightlights-v2.0.0.zip" download>
            ⬇ by-maps-nightlights-v2.0.0.zip (4,6 МБ)
          </a>
        </div>
      </div>
      <div className="card">
        <div className="card-code">v1.0.0 · 2026-07-12 · {t('git-тег')} artifact-nightlights-v1.0.0</div>
        <p>
          {t('Первый релиз: VIIRS 2015–2023 (WorldPop fvf), индекс расхождения; расхождение сосредоточено в индустриальных районах (Жодино свет ×0,55, Борисов ×0,78), Минск вровень. В v2 источник оставлен как независимая кросс-проверка.')}
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-nightlights-v1.0.0.zip" download>
            ⬇ by-maps-nightlights-v1.0.0.zip (476 КБ)
          </a>
        </div>
      </div>

      <h2>{t('Состав')}</h2>
      <pre><code>{`by-maps-nightlights-v2.1.0/
├── README.md · AGENT.md · LIMITATIONS.md · PROVENANCE.md · CHANGELOG.md
├── manifest.json                    машиночитаемое описание (sha256, допуски)
├── sources/registry.csv             83 записи: URL, лицензии, sha256 глобальных
│                                    файлов и вырезок (DMSP, VNL, simVIIRS)
├── data/raw/nightlights/rasters/    35 вырезок GeoTIFF по Беларуси
├── data/raw/nightlights/zonal_*.csv зональные суммы трёх продуктов + floor
├── etl/nightlights_harmonize.py     гармонизация «мостом» + валидация (stdlib)
├── etl/nightlights_model.py         эластичности и модель 2030-2075 (stdlib)
├── etl/nightlights_v2.py            финальный набор (stdlib)
├── etl/nightlights_{fetch,zonal,frames}.py   растровые шаги (rasterio)
├── tools/render_reel_space.py       рилс-конвейер 1080x1920 (детерминирован)
├── params/assumptions.json|yaml     ВСЕ параметры: пороги, дефакеляция, β, floor
├── docs/notes/nightlights_v2_validation.md   отчёт с гейтами стыка
├── code/run.sh                      единственная точка входа (~10 секунд)
├── web/public/data/nightlights_v2.json        итог лендинга
├── web/public/data/nightlights/     манифест кадров, события, аннотации
└── checks/                          инварианты, 21 контрольная метрика, chksums`}</code></pre>

      <h2>{t('Быстрая проверка')}</h2>
      <pre><code>{`unzip by-maps-nightlights-v2.1.0.zip && cd by-maps-nightlights-v2.1.0
bash code/run.sh          # только стандартная библиотека Python >= 3.10
# == 1/6 Гармонизация ==   == 2/6 Эластичности ==
# == 3/6 Финальный набор == == 4/6 События и адаптивная скорость ==
# == 5/6 Инварианты ==      == 6/6 Сверка с заявленными результатами ==
# Все 21 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        {t('Живая версия — ')}<Link href={p('/research/nightlights')}>{p('/research/nightlights')}</Link>
        {t('; методика — кнопка «О данных и методике» на странице исследования. AGENT.md содержит три обязательных задания, включая стресс-тест модели.')}
      </p>
    </div>
  );
}
