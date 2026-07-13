import type { Metadata } from 'next';
import Markdown from '@/components/Markdown';
import AuthorLanding from '@/components/AuthorLanding';
import { loadContent } from '@/lib/content';
import { authors, ogImage, ogBase, personJsonLd, altFor } from '@/lib/seo';

const c = loadContent('ru', 'author');
export const metadata: Metadata = {
  title: 'Сергей Авдейчик — AI/ML-инженер, к.т.н. · автор BY Maps',
  description: c.description,
  authors,
  alternates: altFor('/author'),
  openGraph: { ...ogBase, locale: 'ru_RU', title: 'Сергей Авдейчик — AI/ML Engineer', description: c.description, images: [ogImage] },
};

export default function Page() {
  return (
    <div className="page author-page">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(personJsonLd) }} />
      <AuthorLanding lang="ru" />
      <div className="author-bio">
        <article className="content">
          <Markdown text={c.body} />
        </article>
      </div>
    </div>
  );
}
