'use client';

import Link from 'next/link';
import { useT, useLang } from '@/lib/i18n';

export default function PyramidArtifactBody() {
  const t = useT();
  const be = useLang() === 'be';
  const p = (path: string) => (be ? '/be' + path : path);
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href={p('/artifacts')}>{t('Артефакты')}</Link> · INF-11
      </div>
      <h1>{t('Пакет: возрастно-половая пирамида, 1959–2075')}</h1>
      <p className="page-lead">
        {t('128 кадров национальной возрастно-половой структуры (17 групп × пол), каждый с типом достоверности: переписи 1959–1989 (БССР, Демоскоп) и 2009/2019 (OLAP F201N) — до человека; годовые оценки Белстата 1990–2026; когортная интерполяция между переписями; будущее 2030–2075 — экспорт CCMPP v2026.4 (3 сценария × 2 стартовых ряда). WPP-2024 — только кросс-чек: заглушка прототипа в набор не входит.')}
      </p>

      <h2>{t('Версии')}</h2>
      <div className="card">
        <div className="card-code">v1.0.0 · 2026-07-14 · {t('git-тег')} artifact-pyramid-v1.0.0</div>
        <p>
          {t('Первый релиз: страница /pyramid (морфинг, «найди себя», аннотации A1–A7, RU/BE), датасет с контрольными итогами до человека (1959 = 8 054 648 … 2026 = 9 056 080), согласование будущего с итогами прогноза ±0,1%, 14 контрольных метрик, рилс-конвейер R-1. Ограничение: переписной таблицы 1999 года в открытых машиночитаемых источниках нет — кадр 1999 является официальной оценкой.')}
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-pyramid-v1.0.0.zip" download>
            ⬇ by-maps-pyramid-v1.0.0.zip (336 КБ)
          </a>
        </div>
      </div>

      <h2>{t('Быстрая проверка')}</h2>
      <pre><code>{`unzip by-maps-pyramid-v1.0.0.zip && cd by-maps-pyramid-v1.0.0
bash code/run.sh          # только стандартная библиотека Python >= 3.10
# == 1/4 Сборка ==  == 2/4 Инварианты ==
# == 3/4 Кросс-чек WPP ==  == 4/4 Сверка ==
# Все 14 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        {t('Живая версия — ')}<Link href={p('/pyramid')}>{p('/pyramid')}</Link>
        {t('; AGENT.md содержит три обязательных задания, включая стресс-тест формы 2075 по сценариям.')}
      </p>
    </div>
  );
}
