'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const ITEMS = [
  { href: '/', label: 'Карта' },
  { href: '/research', label: 'Исследования' },
  { href: '/methodology', label: 'Методика' },
  { href: '/artifacts', label: 'Артефакты' },
];

export default function SiteNav() {
  const path = usePathname();
  return (
    <nav className="site-nav">
      <span className="site-brand">Население Беларуси, 1897–2026</span>
      {ITEMS.map((it) => {
        const active = it.href === '/' ? path === '/' : path.startsWith(it.href);
        return (
          <Link key={it.href} href={it.href} className={active ? 'on' : ''}>
            {it.label}
          </Link>
        );
      })}
    </nav>
  );
}
