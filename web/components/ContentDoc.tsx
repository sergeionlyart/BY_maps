import Markdown from '@/components/Markdown';
import { headings } from '@/lib/content';
import { slugify } from '@/lib/slug';

/** Статическая контентная страница: оглавление (по желанию) + markdown.
 *  Серверный компонент — весь текст попадает в статический HTML. */
export default function ContentDoc({ body, toc = false, lang = 'ru', footer }: {
  body: string;
  toc?: boolean;
  lang?: 'ru' | 'be';
  /** Доп. блок после статьи в той же читаемой колонке (напр. AuthorCard). */
  footer?: React.ReactNode;
}) {
  const h2 = toc ? headings(body) : [];
  return (
    <div className="page content-page" lang={lang}>
      {h2.length > 1 && (
        <nav className="content-toc" aria-label="Оглавление">
          <div className="content-toc-title">{lang === 'be' ? 'Змест' : 'Содержание'}</div>
          <ul>
            {h2.map((h) => (
              <li key={h.text}><a href={`#${slugify(h.text)}`}>{h.text}</a></li>
            ))}
          </ul>
        </nav>
      )}
      <article className="content">
        <Markdown text={body} />
      </article>
      {footer}
    </div>
  );
}
