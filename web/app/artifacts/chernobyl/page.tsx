import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Пакет chernobyl — версии и состав',
  description: 'Проверяемый пакет исследования «Чернобыльский след» (INF-07).',
};

export default function ChernobylArtifactPage() {
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href="/artifacts">Артефакты</Link> · INF-07
      </div>
      <h1>Пакет: Чернобыльский след</h1>
      <p className="page-lead">
        Реестр зон радиоактивного загрязнения по официальным НПА (оба
        постановления завендорены как PDF), классификация районов, матчинг
        контролей и сравнение траекторий 1970–2026. Суммы НП по зонам
        сходятся с итогами актов до единицы.
      </p>

      <h2>Версии</h2>
      <div className="card">
        <div className="card-code">v1.0.0 · 2026-07-11 · git-тег artifact-chernobyl-v1.0.0</div>
        <p>
          Первый релиз. Перечни: пост. СМ РБ № 75/2021 (2022 НП) и № 9/2016
          (2193 НП); класс 1 (Брагинский, Хойникский, Наровлянский) отстал от
          контролей на 14–20 п.п. индекса к 2019 г. 10 контрольных метрик.
        </p>
        <div className="card-foot">
          <a href="/artifacts/by-maps-chernobyl-v1.0.0.zip" download>
            ⬇ by-maps-chernobyl-v1.0.0.zip (613 КБ)
          </a>
        </div>
      </div>

      <h2>Состав</h2>
      <pre><code>{`by-maps-chernobyl-v1.0.0/
├── README.md · AGENT.md · LIMITATIONS.md · PROVENANCE.md · CHANGELOG.md
├── manifest.json                    машиночитаемое описание (sha256, допуски)
├── sources/registry.csv             реестр первоисточников (НПА, МЧС)
├── data/raw/chernobyl/pravo_75.pdf          пост. № 75/2021, официальный PDF
├── data/raw/chernobyl/pravo_2016_9.pdf      пост. № 9/2016, официальный PDF
├── data/raw/chernobyl/belarus_chernobyl_36.txt   брошюра МЧС (табл. 12)
├── data/raw/chernobyl/districts_zones.json  агрегат: район -> НП по зонам
├── web/public/data/data.json        ряды населения районов (база проекта)
├── etl/chernobyl.py                 классификация, матчинг, выгрузка
├── params/assumptions.yaml          допущения матчинга с обоснованиями
├── code/run.sh                      единственная точка входа (~2 секунды)
├── web/public/data/chernobyl.json · data/curated/chernobyl_zones.csv   итоги
└── checks/                          инварианты, ожидаемые результаты, chksums`}</code></pre>

      <h2>Быстрая проверка</h2>
      <pre><code>{`unzip by-maps-chernobyl-v1.0.0.zip && cd by-maps-chernobyl-v1.0.0
bash code/run.sh          # только стандартная библиотека Python >= 3.10
# == 1/3 Реестр зон, классификация, матчинг контролей ==
# == 2/3 Инварианты ==
# == 3/3 Сверка с заявленными результатами ==
# Все 10 контрольных метрик воспроизведены в допусках.`}</code></pre>

      <p className="hint">
        Живая версия — <Link href="/research/chernobyl">/research/chernobyl</Link>;
        методика — кнопка «О данных и методике» на странице исследования.
      </p>
    </div>
  );
}
