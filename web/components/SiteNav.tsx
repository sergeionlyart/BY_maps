'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

/** Пары RU↔BE для шести контентных страниц. Непереведённое (карта,
 *  исследования) языкового аналога пока не имеет. */
export const LANG_PAIRS: Record<string, string> = {
  '/article': '/be/article',
  '/about': '/be/about',
  '/goals': '/be/goals',
  '/author': '/be/author',
  '/methodology': '/be/methodology',
  '/artifacts': '/be/data-artifacts',
};
const BE_TO_RU: Record<string, string> = Object.fromEntries(
  Object.entries(LANG_PAIRS).map(([ru, be]) => [be, ru]),
);

function navItems(be: boolean) {
  return [
    { href: '/', label: 'Карта' },
    { href: '/research', label: 'Исследования' },
    { href: be ? '/be/article' : '/article', label: 'Статья' },
    { href: be ? '/be/methodology' : '/methodology', label: 'Методология' },
    { href: be ? '/be/data-artifacts' : '/artifacts', label: 'Данные и артефакты' },
    { href: be ? '/be/about' : '/about', label: 'О проекте' },
  ];
}

export default function SiteNav() {
  const path = usePathname();
  const be = path.startsWith('/be');
  const ruEquiv = be ? (BE_TO_RU[path] ?? '/') : path;
  const beEquiv = be ? path : (LANG_PAIRS[path] ?? '/be/about');
  const beReady = be || path in LANG_PAIRS; // есть ли прямой перевод текущей страницы

  return (
    <nav className="site-nav">
      <span className="site-brand">Население Беларуси, 1897–2026</span>
      {navItems(be).map((it) => {
        const active = it.href === '/' ? path === '/' : path.startsWith(it.href);
        return (
          <Link key={it.label} href={it.href} className={active ? 'on' : ''}>
            {it.label}
          </Link>
        );
      })}
      <span className="lang-switch" aria-label="Язык">
        <Link href={ruEquiv} className={be ? '' : 'on'}>RU</Link>
        <span className="lang-sep">|</span>
        <Link
          href={beEquiv}
          className={be ? 'on' : ''}
          title={beReady ? undefined : 'па-беларуску даступныя тэкставыя старонкі; карта і даследаванні — хутка'}
        >BY</Link>
      </span>
    </nav>
  );
}
