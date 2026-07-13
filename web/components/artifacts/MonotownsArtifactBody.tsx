'use client';

import Link from 'next/link';
import { useT, useLang } from '@/lib/i18n';

export default function MonotownsArtifactBody() {
  const t = useT();
  const be = useLang() === 'be';
  const p = (path: string) => (be ? '/be' + path : path);
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href={p('/artifacts')}>{t('Артефакты')}</Link> · INF-06
      </div>
      <h1>{t('Пакет: Моногорода и градообразующие предприятия')}</h1>
      <p className="page-lead">
        {t('Реестр 49 пар «город — предприятие» (отрасль, оценка занятости, санкционная экспозиция EU/US/UK/Canada, построчные источники), типология по отраслям и matched-comparison траекторий с «типовыми» городами того же размера. Расчёт детерминирован, стандартная библиотека.')}
      </p>

      <h2>{t('Версии')}</h2>
      <div className="card">
        <div className="card-code">v1.0.0 · 2026-07-12 · {t('git-тег')} artifact-monotowns-v1.0.0</div>
        <p>
          {t('Первый релиз. 46 моногородов, 16 отраслей. Ассоциация (не причинность): среди сопоставимых по размеру моногородов высокая зависимость от одного завода связана с бОльшим отставанием от типовых (−7 п.п.), средняя — с опережением (+3). 15 крупнейших сравнивать не с чем (нет города их размера вне облцентров) — показаны индивидуально. 10 контрольных метрик.')}
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-monotowns-v1.0.0.zip" download>
            ⬇ by-maps-monotowns-v1.0.0.zip
          </a>
        </div>
      </div>

      <h2>{t('Состав')}</h2>
      <pre><code>{`by-maps-monotowns-v1.0.0/
├── README.md · AGENT.md · LIMITATIONS.md · PROVENANCE.md · CHANGELOG.md
├── manifest.json                    машиночитаемое описание (sha256, допуски)
├── sources/registry.csv             sha256 реестра + провенанс
├── data/raw/monotowns/registry.json реестр 49 пар с санкциями и источниками
├── data/curated/monotowns.csv       плоский реестр с построчными URL
├── etl/monotowns.py                 типология, matched-comparison, риск (stdlib)
├── params/assumptions.yaml          допущения с обоснованиями
├── code/run.sh                      единственная точка входа (~2 секунды)
├── web/public/data/monotowns.json   итог лендинга
└── checks/                          инварианты, ожидаемые результаты, chksums`}</code></pre>

      <h2>{t('Быстрая проверка')}</h2>
      <pre><code>{`unzip by-maps-monotowns-v1.0.0.zip && cd by-maps-monotowns-v1.0.0
bash code/run.sh          # только стандартная библиотека Python >= 3.10
# Все 10 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        {t('Живая версия — ')}<Link href={p('/research/monotowns')}>{p('/research/monotowns')}</Link>
        {t('; методика — кнопка «О данных и методике» на странице исследования.')}
      </p>
    </div>
  );
}
