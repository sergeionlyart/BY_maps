'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useT } from '@/lib/i18n';

/** RU↔BE — теперь каждая страница имеет двойник /be/*, поэтому маппинг общий. */
export function toBe(p: string): string { return p === '/' ? '/be' : '/be' + p; }
export function toRu(p: string): string { return p === '/be' ? '/' : p.slice(3); }

const NAV = [
  { href: '/map', label: 'Карта' },
  { href: '/research', label: 'Исследования' },
  { href: '/article', label: 'Статья' },
  { href: '/methodology', label: 'Методология' },
  { href: '/artifacts', label: 'Данные и артефакты' },
  { href: '/about', label: 'О проекте' },
];

export default function SiteNav() {
  const path = usePathname();
  const be = path.startsWith('/be');
  const t = useT();
  const ruEquiv = be ? toRu(path) : path;
  const beEquiv = be ? path : toBe(path);

  const [open, setOpen] = useState(false);
  useEffect(() => { setOpen(false); }, [path]);

  const home = be ? '/be' : '/';

  return (
    <nav className={`site-nav ${open ? 'nav-open' : ''}`}>
      <Link href={home} className="site-brand site-brand-full">{t('Население Беларуси, 1897–2026')}</Link>
      <Link href={home} className="site-brand site-brand-short">BY&nbsp;Maps</Link>

      <button
        className="nav-burger"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? t('закрыть меню') : t('открыть меню')}
        aria-expanded={open}
      >
        {open ? '✕' : '☰'}
      </button>

      <div className="site-links">
        {NAV.map((it) => {
          const href = be ? toBe(it.href) : it.href;
          const active = path === href || path.startsWith(href + '/');
          return (
            <Link key={it.href} href={href} className={active ? 'on' : ''}>
              {t(it.label)}
            </Link>
          );
        })}
        <span className="lang-switch" aria-label={t('Язык')}>
          <Link href={ruEquiv} className={be ? '' : 'on'}>RU</Link>
          <span className="lang-sep">|</span>
          <Link href={beEquiv} className={be ? 'on' : ''}>BY</Link>
        </span>
      </div>

      {open && <div className="nav-backdrop" onClick={() => setOpen(false)} />}
    </nav>
  );
}
