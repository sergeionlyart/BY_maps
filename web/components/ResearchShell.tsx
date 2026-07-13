'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import AuthorCard from '@/components/AuthorCard';
import JsonLd from '@/components/JsonLd';
import { articleJsonLd } from '@/lib/seo';
import { useT, useLang } from '@/lib/i18n';

/** Клиентская оболочка страницы исследования: хлебные крошки + заголовок +
 *  лид + вьюшка + карточка автора. Русские строки идут через t(); язык — из
 *  маршрута (useLang). Один и тот же компонент рендерит и RU (/research/*),
 *  и BE (/be/research/*) — различие даёт словарь + языковой контекст. */
export default function ResearchShell({
  code,
  version,
  title,
  lead,
  children,
}: {
  code: string;
  version?: string;
  title: string;
  lead: string;
  children: React.ReactNode;
}) {
  const t = useT();
  const lang = useLang();
  const pathname = usePathname();
  return (
    <div className="page page-wide">
      <JsonLd
        data={articleJsonLd({
          title: t(title),
          description: t(lead),
          path: pathname,
          lang,
          scholarly: true,
        })}
      />
      <div className="page-breadcrumb">
        <Link href={lang === 'be' ? '/be/research' : '/research'}>{t('Исследования')}</Link>
        {' · '}
        {code}
        {version ? ` · ${version}` : ''}
      </div>
      <h1>{t(title)}</h1>
      <p className="page-lead">{t(lead)}</p>
      {children}
      <AuthorCard variant="compact" lang={lang} />
    </div>
  );
}
