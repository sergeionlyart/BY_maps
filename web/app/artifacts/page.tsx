import type { Metadata } from 'next';
import Link from 'next/link';
import { RESEARCH } from '@/lib/research';
import { loadContent } from '@/lib/content';
import Markdown from '@/components/Markdown';
import AuthorCard from '@/components/AuthorCard';

const intro = loadContent('ru', 'data-artifacts');

export const metadata: Metadata = {
  title: intro.title || 'Данные и артефакты — BY Maps',
  description: intro.description,
  alternates: { languages: { ru: '/artifacts', be: '/be/data-artifacts' } },
};

const PROMPTS = [
  {
    title: 'Проверка источников',
    text: 'В приложенном ZIP-пакете исследования открой sources/registry.csv и AGENT.md. Проверь, что sha256 завендоренных источников совпадают с реестром; если есть доступ в сеть — скачай живые версии по URL и зафиксируй, изменились ли они после даты обращения. Составь таблицу: источник, статус (совпал / изменился / недоступен).',
  },
  {
    title: 'Воспроизведение расчёта',
    text: 'Распакуй пакет и выполни bash code/run.sh (окружение — по code/requirements.lock). Сравни полученные data/final/computed_results.json с checks/expected_results.json в заявленных допусках. Отчитайся по каждой метрике: заявлено, воспроизведено, расхождение.',
  },
  {
    title: 'Стресс допущений',
    text: 'Прочитай params/assumptions.yaml и LIMITATIONS.md, выбери 3 самых сильных допущения и проверь чувствительность к ним способами, описанными в AGENT.md (задача 3). Какие выводы устойчивы, какие «плывут»? Приведи числа до/после.',
  },
  {
    title: 'Отчёт о расхождениях',
    text: 'Сформируй итоговый отчёт по формату из AGENT.md: совпадения, расхождения (с величинами), недоступные источники, спорные допущения, вердикт воспроизводимости.',
  },
];

export default function ArtifactsPage() {
  const published = RESEARCH.filter((r) => r.status === 'published' && r.artifact);
  return (
    <div className="page">
      <article className="content">
        <Markdown text={intro.body} />
      </article>

      <h2>Каталог пакетов</h2>
      <p className="page-lead" style={{ fontSize: 14 }}>
        Машиночитаемый каталог со всеми версиями и контрольными суммами —{' '}
        <a href="/artifacts/catalog.json">catalog.json</a>; внешние суммы для быстрой
        проверки целостности — <a href="/artifacts/checksums.txt">checksums.txt</a>{' '}
        (<code>sha256sum -c checksums.txt</code>).
      </p>
      <div className="cards">
        <div className="card">
          <div className="card-code">Прогноз · v2026.4 · пакет v1.3.0</div>
          <div className="card-title">Прогноз населения 2026–2075 (уровни 0–3; ряды official/adjusted; вероятностный веер)</div>
          <p>CCMPP + Гамильтон–Перри + доли городов, 3 сценария; вероятностный
            веер — сеяный Монте-Карло СКР/ОПЖ, калиброванный по 80% PI WPP
            (уровни 0–1); ряд adjusted — поправка на незарегистрированную
            эмиграцию 2020–2026 (WP-F3); три бэктеста с гейтами.</p>
          <div className="card-foot">
            <a href="/artifacts/by-maps-forecast-v1.3.0.zip" download>
              ⬇ by-maps-forecast-v1.3.0.zip (2051 КБ)
            </a>
            {' · '}
            <Link href="/artifacts/forecast">версии и состав</Link>
            {' · '}
            <Link href="/map">живая версия (слайдер за 2026)</Link>
          </div>
        </div>
        {published.map((r) => (
          <div key={r.slug} className="card">
            <div className="card-code">{r.code} · v{r.artifact!.version}</div>
            <div className="card-title">{r.title}</div>
            <div className="card-foot">
              <a href={`/artifacts/${r.artifact!.file}`} download>
                ⬇ {r.artifact!.file} ({r.artifact!.sizeKb} КБ)
              </a>
              {' · '}
              <Link href={`/artifacts/${r.slug}`}>версии и состав</Link>
              {' · '}
              <Link href={`/research/${r.slug}`}>живая версия</Link>
            </div>
          </div>
        ))}
      </div>

      <h2 id="reproduction">Процедура воспроизведения</h2>
      <p>
        Проверено в чистом окружении (Ubuntu 22, Python 3.10, Node 20). Сценарий
        A не требует репозитория вообще — достаточно скачанного пакета.
      </p>
      <h3>A. Проверить одно исследование без репозитория (15–30 минут)</h3>
      <pre><code>{`sha256sum by-maps-zipf-v1.0.0.zip     # 1. целостность (сверить с catalog.json)
unzip by-maps-zipf-v1.0.0.zip -d zipf && cd zipf
cat README.md LIMITATIONS.md          # 2. что утверждается и чего НЕ утверждается
sha256sum -c checks/checksums.sha256  # 3. целостность каждого файла пакета
bash code/run.sh                      # 4. полный расчёт от сырых данных до финальных
                                      #    со сверкой expected_results в допусках`}</code></pre>
      <p>
        Успех: <code>run.sh</code> завершается кодом 0 и сообщает о совпадении с
        эталоном. Файлы в <code>data/final/</code> в точности совпадают с
        опубликованными на сайте. <strong>Вариант для агента:</strong> передайте
        архив своей LLM-системе с инструкцией «выполни задания из AGENT.md»
        (готовые промпты — ниже).
      </p>
      <h3>B. Полное воспроизведение из репозитория</h3>
      <pre><code>{`git clone https://github.com/sergeionlyart/BY_maps && cd BY_maps
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt  # shapely pytest pyyaml
.venv/bin/python -m etl.build                     # сборка web/public/data
.venv/bin/python -m pytest etl/tests/ -q          # 155 инвариантов данных
.venv/bin/python -m etl.artifacts.build --all --check   # байт-воспроизводимость (CI-гейт)
.venv/bin/python -m etl.artifacts.validate --all  # прогон run.sh каждого + сверка допусков`}</code></pre>
      <p>
        Контрольные значения прогноза (official-ряд): базовый сценарий 2050 —
        7&nbsp;529 тыс., 2075 — 5&nbsp;970 тыс.; калибровка base-2050 к медиане UN
        WPP 2024 — +1,0% (гейт ±3%); бэктест 2009→2019 — −0,4% (гейт ±2%);
        80% интервал вероятностного веера на 2050 — [7&nbsp;042; 8&nbsp;046] тыс.
        Монте-Карло использует фиксированный seed (20260712) — квантили детерминированы.
      </p>

      <h2>Что поручить агенту</h2>
      <div className="prompts">
        {PROMPTS.map((p) => (
          <details key={p.title} className="prompt">
            <summary>{p.title}</summary>
            <pre><code>{p.text}</code></pre>
          </details>
        ))}
      </div>

      <h2>Пример: агент проверяет пакет zipf</h2>
      <p>
        Реальный отчёт независимого агента (Claude, 2026-07-11), которому
        передали <code>by-maps-zipf-v1.0.0.zip</code> и AGENT.md — без доступа
        к нашему репозиторию. По итогам этого аудита в пакете исправлена
        документация допущения об оценке GI/OLS (см. CHANGELOG пакета) — так
        конвейер и должен работать:
      </p>
      <div className="agent-report">
        <div className="ar-head">Отчёт агента-аудитора · дословно</div>
        <div className="ar-body">
          <h3>Совпадения</h3>
          <p>
            Все контрольные метрики воспроизведены точно, в допусках ±0,001:
            наклоны rank-size по топ-30 (Габэ–Ибрагимов) 1897 = −1,1324;
            1959 = −0,9817; 2019 = −0,9651; 2026 = −0,9532; примация Минска
            1897 = 1,38; 1959 = 3,066; 2026 = 3,991; городских НП в переписи
            2019 = 199. <code>bash code/run.sh</code> завершился кодом 0
            (6 инвариантов); повторная сборка бит-в-бит совпала со всеми
            суммами <code>checks/checksums.sha256</code>. Собственный пересчёт
            GI-наклона 2019 дал −0,9651.
          </p>
          <h3>Расхождения</h3>
          <p>
            Заявленный сдвиг «~0,05» между GI и обычной OLS log(rank)~log(pop)
            занижен: фактически ~0,11 во все годы (2019: −0,965 против −0,857).
            Выводы не меняются (SE ≈ 0,25), но цифра в AGENT.md/assumptions.yaml
            неверна. <em>[исправлено в пакете по итогам аудита]</em>
          </p>
          <h3>Источники</h3>
          <p>
            sha256 завендоренного <code>ps_cities.html</code> совпадает с
            registry.csv. Живой источник проверить не удалось: сеть недоступна
            из среды аудита — работа велась с завендоренной копией.
          </p>
          <h3>Спорные допущения</h3>
          <p>
            N=30: при N=50 наклон 2019 положе (−0,858) — вывод «ципфовость» на
            топ-50 слабеет, как и заявлено в LIMITATIONS.md. Топ-30 1897 года
            весь ≥ 5104 жителей — пропуски малых местечек на него не влияют.
            Разрыв перепись-2019/оценка-2026 мал (0,012). Примация от выбора N
            не зависит по построению.
          </p>
          <h3>Вердикт</h3>
          <p>
            <strong>Воспроизводится с оговорками:</strong> расчёт полностью
            детерминирован и совпадает; единственная оговорка — заниженная в
            документации величина сдвига GI/OLS (исправлена).
          </p>
        </div>
      </div>

      <h2>Как цитировать</h2>
      <p>
        Версия пакета — semver; каждый релиз имеет git-тег
        (<code>artifact-&lt;slug&gt;-v&lt;X.Y.Z&gt;</code>) и{' '}
        <code>CITATION.cff</code> внутри пакета. Опубликованные версии
        неизменяемы: любое изменение данных, кода или параметров — новая
        версия и запись в changelog на странице пакета.
      </p>

      <AuthorCard variant="callout" lang="ru" />
    </div>
  );
}
