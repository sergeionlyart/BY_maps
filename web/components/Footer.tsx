'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Footer() {
  const path = usePathname();
  // на карте (режим приложения, /map) подвал не показываем — страница не прокручивается
  if (path === '/map') return null;
  const be = path.startsWith('/be');
  // выбор варианта по текущему языку (раньше параметр be затенял внешний булев
  // флаг и ссылки всегда вели на /be — исправлено)
  const p = (ru: string, beVal: string) => (be ? beVal : ru);
  return (
    <footer className="site-footer">
      <div className="footer-links">
        <Link href={p('/about', '/be/about')}>{p('О проекте', 'Пра праект')}</Link>
        <Link href={p('/goals', '/be/goals')}>{p('Цели', 'Мэты')}</Link>
        <Link href={p('/author', '/be/author')}>{p('Автор', 'Аўтар')}</Link>
        <Link href={p('/methodology', '/be/methodology')}>{p('Методология', 'Метадалогія')}</Link>
        <a href="https://github.com/sergeionlyart/BY_maps" target="_blank" rel="noreferrer">GitHub</a>
        <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">{p('Лицензия', 'Ліцэнзія')} CC&nbsp;BY&nbsp;4.0</a>
      </div>
      <div className="footer-author">
        {be ? 'Зрабіў ' : 'Сделал '}
        <Link href={p('/author', '/be/author')} className="footer-author-name">
          {be ? 'Сяргей Аўдзейчык' : 'Сергей Авдейчик'}
        </Link>
        {be ? ' — AI/ML-інжынер · ментарынг і распрацоўка → ' : ' — AI/ML-инженер · менторинг и разработка → '}
        <a href="mailto:chatwebmarket@gmail.com?subject=BY%20Maps">{be ? 'напісаць' : 'написать'}</a>
      </div>
      <div className="footer-note">
        {p(
          'Данные, код и производные наборы — под лицензией CC BY 4.0 (первичные источники — по своим условиям, см. пакеты). Контакты автора — в разделе ',
          'Даныя, код і вытворныя наборы — пад ліцэнзіяй CC BY 4.0 (першасныя крыніцы — паводле сваіх умоў, гл. пакеты). Кантакты аўтара — у раздзеле ',
        )}
        <Link href={p('/author', '/be/author')}>{p('«Автор»', '«Аўтар»')}</Link>.{' '}
        {p('© 2026 «Население Беларуси, 1897–2026».', '© 2026 «Насельніцтва Беларусі, 1897–2026».')}
      </div>
    </footer>
  );
}
