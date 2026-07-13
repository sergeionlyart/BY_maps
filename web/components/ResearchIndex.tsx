'use client';

import Link from 'next/link';
import { RESEARCH } from '@/lib/research';
import { useT, useLang } from '@/lib/i18n';

/** Клиентское тело индекса исследований: заголовок, лид, карточки
 *  опубликованных, раздел «В плане работ», подсказка. Русские UI-строки идут
 *  через t(); ссылки и title/question карточек учитывают язык маршрута. */
export default function ResearchIndex() {
  const t = useT();
  const lang = useLang();
  const be = lang === 'be';
  const published = RESEARCH.filter((r) => r.status === 'published');
  const planned = RESEARCH.filter((r) => r.status === 'planned');
  const artifactsHref = be ? '/be/artifacts' : '/artifacts';
  return (
    <div className="page">
      <h1>{t('Исследования')}</h1>
      <p className="page-lead">
        {t('Каждое исследование публикуется с методологическим блоком (данные, преобразования, ограничения) и')}{' '}
        <Link href={artifactsHref}>{t('проверяемым пакетом артефактов')}</Link>
        {t(': данные + код + допущения, достаточные, чтобы воспроизвести и оспорить каждое число.')}
      </p>

      <div className="cards">
        {published.map((r) => (
          <Link
            key={r.slug}
            href={be ? `/be/research/${r.slug}` : `/research/${r.slug}`}
            className="card"
          >
            <div className="card-code">{r.code} · {t('опубликовано')}</div>
            <div className="card-title">{t(r.title)}</div>
            <p>{t(r.question)}</p>
            <div className="card-foot">
              {r.artifact ? `${t('пакет')} v${r.artifact.version}` : ''} · {t('открыть →')}
            </div>
          </Link>
        ))}
      </div>

      <h2>{t('В плане работ')}</h2>
      <div className="cards">
        {planned.map((r) => (
          <div key={r.slug} className="card planned">
            <div className="card-code">{r.code} · {t('этап')} {r.stage} {t('плана')}</div>
            <div className="card-title">{t(r.title)}</div>
            <p>{t(r.question)}</p>
          </div>
        ))}
      </div>
      <p className="hint">
        {t('Порядок и зависимости этапов — в')}{' '}
        <a
          href="https://github.com/sergeionlyart/BY_maps/blob/master/docs/TASK_SPEC.md"
          target="_blank"
          rel="noreferrer"
        >{t('задании на доработку (TASK_SPEC.md)')}</a>.
      </p>
    </div>
  );
}
