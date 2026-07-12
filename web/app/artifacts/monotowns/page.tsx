import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Пакет monotowns — версии и состав',
  description: 'Проверяемый пакет исследования «Моногорода и градообразующие предприятия» (INF-06).',
};

export default function MonotownsArtifactPage() {
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href="/artifacts">Артефакты</Link> · INF-06
      </div>
      <h1>Пакет: Моногорода и градообразующие предприятия</h1>
      <p className="page-lead">
        Реестр 49 пар «город — предприятие» (отрасль, оценка занятости,
        санкционная экспозиция EU/US/UK/Canada, построчные источники),
        типология по отраслям и matched-comparison траекторий с «типовыми»
        городами того же размера. Расчёт детерминирован, стандартная
        библиотека.
      </p>

      <h2>Версии</h2>
      <div className="card">
        <div className="card-code">v1.0.0 · 2026-07-12 · git-тег artifact-monotowns-v1.0.0</div>
        <p>
          Первый релиз. 46 моногородов, 16 отраслей. Ассоциация (не
          причинность): среди сопоставимых по размеру моногородов высокая
          зависимость от одного завода связана с бОльшим отставанием от
          типовых (−7 п.п.), средняя — с опережением (+3). 15 крупнейших
          сравнивать не с чем (нет города их размера вне облцентров) —
          показаны индивидуально. 10 контрольных метрик.
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-monotowns-v1.0.0.zip" download>
            ⬇ by-maps-monotowns-v1.0.0.zip
          </a>
        </div>
      </div>

      <h2>Состав</h2>
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

      <h2>Быстрая проверка</h2>
      <pre><code>{`unzip by-maps-monotowns-v1.0.0.zip && cd by-maps-monotowns-v1.0.0
bash code/run.sh          # только стандартная библиотека Python >= 3.10
# Все 10 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        Живая версия — <Link href="/research/monotowns">/research/monotowns</Link>;
        методика — кнопка «О данных и методике» на странице исследования.
      </p>
    </div>
  );
}
