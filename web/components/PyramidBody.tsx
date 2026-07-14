'use client';

/** Обёртка страницы /pyramid: интро и методблок из утверждённого
 *  контента + интерактивная пирамида. Тексты приходят распарсенными
 *  с сервера (RU/BE — свой файл на маршрут). */

import Link from 'next/link';
import Markdown from '@/components/Markdown';
import PyramidView from '@/components/PyramidView';
import AuthorCard from '@/components/AuthorCard';
import { useT, useLang } from '@/lib/i18n';
import type { ParsedPyramidContent } from '@/lib/pyramidContent';

export default function PyramidBody({ parsed }: {
  parsed: ParsedPyramidContent;
}) {
  const t = useT();
  const lang = useLang();
  const p = (path: string) => (lang === 'be' ? '/be' + path : path);
  return (
    <div className="page">
      <div className="page-breadcrumb">
        <Link href={p('/')}>{t('Главная')}</Link> · INF-11 · v1.0.0
      </div>
      <h1>{parsed.heading}</h1>
      <div className="page-lead md">
        <Markdown text={parsed.intro} />
      </div>
      <PyramidView annotations={parsed.annotations} />
      <div className="chart-block pyr-method md">
        <div className="chart-title">{t('Методблок')}</div>
        <Markdown text={parsed.method} />
        <p className="hint">
          {t('Числа аннотаций за 2019 год цитируют официальную оценку на 1 января 2019 года; кадр «2019» на пирамиде — перепись (октябрь 2019), поэтому значения когорт в тултипе могут отличаться от текста на 2–3%.')}
        </p>
      </div>
      <AuthorCard variant="compact" lang={lang} />
    </div>
  );
}
