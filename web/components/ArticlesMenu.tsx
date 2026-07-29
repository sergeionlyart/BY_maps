import Link from 'next/link';
import { ARTICLES } from '@/lib/articles';
import { beTwin } from '@/lib/seo';
import DICT from '@/lib/be-dict';

/** lib/i18n.tsx помечен 'use client' целиком (там же LangProvider/useT), поэтому
 *  его tr() нельзя звать из серверного компонента - ArticlesMenu держит эту же
 *  логику локально поверх словаря напрямую, оставаясь серверным. */
function tr(lang: 'ru' | 'be', s: string): string {
  return lang === 'be' ? (DICT[s] ?? s) : s;
}

/** Список статей для боковой колонки /article/* (см. ContentDoc.tsx проп
 *  articlesNav) - текущая страница выделена текстом, не ссылкой. `current`
 *  всегда RU-канонический путь (даже на BE-странице) - так сравнение с
 *  ARTICLES[].path работает независимо от lang, а href резолвится отдельно. */
export default function ArticlesMenu({ current, lang }: { current: string; lang: 'ru' | 'be' }) {
  return (
    <div className="content-toc-articles">
      <div className="content-toc-title">{lang === 'be' ? 'Артыкулы' : 'Статьи'}</div>
      <ul>
        {ARTICLES.map((a) => {
          const isCurrent = a.path === current;
          const href = lang === 'be' ? beTwin(a.path) : a.path;
          return (
            <li key={a.path}>
              {isCurrent
                ? <span className="content-toc-current">{tr(lang, a.title)}</span>
                : <Link href={href}>{tr(lang, a.title)}</Link>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
