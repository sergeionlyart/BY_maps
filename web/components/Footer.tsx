'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Footer() {
  const path = usePathname();
  const be = path.startsWith('/be');
  const p = (ru: string, be: string) => (be ? be : ru);
  return (
    <footer className="site-footer">
      <div className="footer-links">
        <Link href={p('/about', '/be/about')}>О проекте</Link>
        <Link href={p('/goals', '/be/goals')}>Цели</Link>
        <Link href={p('/author', '/be/author')}>Автор</Link>
        <Link href={p('/methodology', '/be/methodology')}>Методология</Link>
        <a href="https://github.com/sergeionlyart/BY_maps" target="_blank" rel="noreferrer">GitHub</a>
        <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">Лицензия CC&nbsp;BY&nbsp;4.0</a>
      </div>
      <div className="footer-note">
        Данные, код и производные наборы — под лицензией CC&nbsp;BY&nbsp;4.0 (первичные
        источники — по своим условиям, см. пакеты). Контакты автора — в разделе{' '}
        <Link href={p('/author', '/be/author')}>«Автор»</Link>. © 2026 «Население Беларуси, 1897–2026».
      </div>
    </footer>
  );
}
