'use client';

import Link from 'next/link';
import { RESEARCH } from '@/lib/research';
import Markdown from '@/components/Markdown';
import AuthorCard from '@/components/AuthorCard';
import { useT, useLang } from '@/lib/i18n';

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

export default function ArtifactsIndexBody({ introBody }: { introBody: string }) {
  const t = useT();
  const lang = useLang();
  const be = lang === 'be';
  const p = (path: string) => (be ? '/be' + path : path);
  const published = RESEARCH.filter((r) => r.status === 'published' && r.artifact);

  return (
    <div className="page">
      <article className="content">
        <Markdown text={introBody} />
      </article>

      <h2>{t('Каталог пакетов')}</h2>
      <p className="page-lead" style={{ fontSize: 14 }}>
        {t('Машиночитаемый каталог со всеми версиями и контрольными суммами — ')}
        <a href="/artifacts/catalog.json">catalog.json</a>
        {t('; внешние суммы для быстрой проверки целостности — ')}
        <a href="/artifacts/checksums.txt">checksums.txt</a>{' '}
        (<code>sha256sum -c checksums.txt</code>).
      </p>
      <div className="cards">
        <div className="card">
          <div className="card-code">{t('Прогноз')} · v2026.4 · пакет v1.3.0</div>
          <div className="card-title">{t('Прогноз населения 2026–2075 (уровни 0–3; ряды official/adjusted; вероятностный веер)')}</div>
          <p>{t('CCMPP + Гамильтон–Перри + доли городов, 3 сценария; вероятностный веер — сеяный Монте-Карло СКР/ОПЖ, калиброванный по 80% PI WPP (уровни 0–1); ряд adjusted — поправка на незарегистрированную эмиграцию 2020–2026 (WP-F3); три бэктеста с гейтами.')}</p>
          <div className="card-foot">
            <a href="/artifacts/by-maps-forecast-v1.3.0.zip" download>
              ⬇ by-maps-forecast-v1.3.0.zip (2051 КБ)
            </a>
            {' · '}
            <Link href={p('/artifacts/forecast')}>{t('версии и состав')}</Link>
            {' · '}
            <Link href={p('/map')}>{t('живая версия (слайдер за 2026)')}</Link>
          </div>
        </div>
        {published.map((r) => (
          <div key={r.slug} className="card">
            <div className="card-code">{r.code} · v{r.artifact!.version}</div>
            <div className="card-title">{t(r.title)}</div>
            <div className="card-foot">
              <a href={`/artifacts/${r.artifact!.file}`} download>
                ⬇ {r.artifact!.file} ({r.artifact!.sizeKb} КБ)
              </a>
              {' · '}
              <Link href={p(`/artifacts/${r.slug}`)}>{t('версии и состав')}</Link>
              {' · '}
              <Link href={p(`/research/${r.slug}`)}>{t('живая версия')}</Link>
            </div>
          </div>
        ))}
      </div>

      <h2 id="reproduction">{t('Процедура воспроизведения')}</h2>
      <p>
        {t('Проверено в чистом окружении (Ubuntu 22, Python 3.10, Node 20). Сценарий A не требует репозитория вообще — достаточно скачанного пакета.')}
      </p>
      <h3>{t('A. Проверить одно исследование без репозитория (15–30 минут)')}</h3>
      <pre><code>{`sha256sum by-maps-zipf-v1.0.0.zip     # 1. целостность (сверить с catalog.json)
unzip by-maps-zipf-v1.0.0.zip -d zipf && cd zipf
cat README.md LIMITATIONS.md          # 2. что утверждается и чего НЕ утверждается
sha256sum -c checks/checksums.sha256  # 3. целостность каждого файла пакета
bash code/run.sh                      # 4. полный расчёт от сырых данных до финальных
                                      #    со сверкой expected_results в допусках`}</code></pre>
      <p>
        {t('Успех: ')}<code>run.sh</code>{t(' завершается кодом 0 и сообщает о совпадении с эталоном. Файлы в ')}<code>data/final/</code>{t(' в точности совпадают с опубликованными на сайте. ')}<strong>{t('Вариант для агента:')}</strong>{t(' передайте архив своей LLM-системе с инструкцией «выполни задания из AGENT.md» (готовые промпты — ниже).')}
      </p>
      <h3>{t('B. Полное воспроизведение из репозитория')}</h3>
      <pre><code>{`git clone https://github.com/sergeionlyart/BY_maps && cd BY_maps
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt  # shapely pytest pyyaml
.venv/bin/python -m etl.build                     # сборка web/public/data
.venv/bin/python -m pytest etl/tests/ -q          # 155 инвариантов данных
.venv/bin/python -m etl.artifacts.build --all --check   # байт-воспроизводимость (CI-гейт)
.venv/bin/python -m etl.artifacts.validate --all  # прогон run.sh каждого + сверка допусков`}</code></pre>
      <p>
        {t('Контрольные значения прогноза (official-ряд): базовый сценарий 2050 — 7 529 тыс., 2075 — 5 970 тыс.; калибровка base-2050 к медиане UN WPP 2024 — +1,0% (гейт ±3%); бэктест 2009→2019 — −0,4% (гейт ±2%); 80% интервал вероятностного веера на 2050 — [7 042; 8 046] тыс. Монте-Карло использует фиксированный seed (20260712) — квантили детерминированы.')}
      </p>

      <h2>{t('Что поручить агенту')}</h2>
      <div className="prompts">
        {PROMPTS.map((pr) => (
          <details key={pr.title} className="prompt">
            <summary>{t(pr.title)}</summary>
            <pre><code>{t(pr.text)}</code></pre>
          </details>
        ))}
      </div>

      <h2>{t('Пример: агент проверяет пакет zipf')}</h2>
      <p>
        {t('Реальный отчёт независимого агента (Claude, 2026-07-11), которому передали ')}<code>by-maps-zipf-v1.0.0.zip</code>{t(' и AGENT.md — без доступа к нашему репозиторию. По итогам этого аудита в пакете исправлена документация допущения об оценке GI/OLS (см. CHANGELOG пакета) — так конвейер и должен работать:')}
      </p>
      <div className="agent-report">
        <div className="ar-head">{t('Отчёт агента-аудитора · дословно')}</div>
        <div className="ar-body">
          <h3>{t('Совпадения')}</h3>
          <p>
            {t('Все контрольные метрики воспроизведены точно, в допусках ±0,001: наклоны rank-size по топ-30 (Габэ–Ибрагимов) 1897 = −1,1324; 1959 = −0,9817; 2019 = −0,9651; 2026 = −0,9532; примация Минска 1897 = 1,38; 1959 = 3,066; 2026 = 3,991; городских НП в переписи 2019 = 199. ')}<code>bash code/run.sh</code>{t(' завершился кодом 0 (6 инвариантов); повторная сборка бит-в-бит совпала со всеми суммами ')}<code>checks/checksums.sha256</code>{t('. Собственный пересчёт GI-наклона 2019 дал −0,9651.')}
          </p>
          <h3>{t('Расхождения')}</h3>
          <p>
            {t('Заявленный сдвиг «~0,05» между GI и обычной OLS log(rank)~log(pop) занижен: фактически ~0,11 во все годы (2019: −0,965 против −0,857). Выводы не меняются (SE ≈ 0,25), но цифра в AGENT.md/assumptions.yaml неверна. ')}<em>{t('[исправлено в пакете по итогам аудита]')}</em>
          </p>
          <h3>{t('Источники')}</h3>
          <p>
            {t('sha256 завендоренного ')}<code>ps_cities.html</code>{t(' совпадает с registry.csv. Живой источник проверить не удалось: сеть недоступна из среды аудита — работа велась с завендоренной копией.')}
          </p>
          <h3>{t('Спорные допущения')}</h3>
          <p>
            {t('N=30: при N=50 наклон 2019 положе (−0,858) — вывод «ципфовость» на топ-50 слабеет, как и заявлено в LIMITATIONS.md. Топ-30 1897 года весь ≥ 5104 жителей — пропуски малых местечек на него не влияют. Разрыв перепись-2019/оценка-2026 мал (0,012). Примация от выбора N не зависит по построению.')}
          </p>
          <h3>{t('Вердикт')}</h3>
          <p>
            <strong>{t('Воспроизводится с оговорками:')}</strong>{t(' расчёт полностью детерминирован и совпадает; единственная оговорка — заниженная в документации величина сдвига GI/OLS (исправлена).')}
          </p>
        </div>
      </div>

      <h2>{t('Как цитировать')}</h2>
      <p>
        {t('Версия пакета — semver; каждый релиз имеет git-тег (')}<code>artifact-&lt;slug&gt;-v&lt;X.Y.Z&gt;</code>{t(') и ')}<code>CITATION.cff</code>{t(' внутри пакета. Опубликованные версии неизменяемы: любое изменение данных, кода или параметров — новая версия и запись в changelog на странице пакета.')}
      </p>

      <AuthorCard variant="callout" lang={lang} />
    </div>
  );
}
