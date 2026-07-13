import type { Metadata } from 'next';
import Markdown from '@/components/Markdown';
import AuthorLanding from '@/components/AuthorLanding';
import { loadContent } from '@/lib/content';
import { authors, ogImage, ogBase, personJsonLd, altFor } from '@/lib/seo';

const c = loadContent('be', 'author');
export const metadata: Metadata = {
  title: 'Сяргей Аўдзейчык — AI/ML-інжынер, к.т.н. · аўтар BY Maps',
  description: c.description,
  authors,
  alternates: altFor('/be/author'),
  openGraph: { ...ogBase, locale: 'be_BY', title: 'Сяргей Аўдзейчык — AI/ML Engineer', description: c.description, images: [ogImage] },
};

export default function Page() {
  return (
    <div className="page author-page">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(personJsonLd) }} />
      <AuthorLanding lang="be" />
      <div className="author-bio">
        <article className="content">
          <Markdown text={c.body} />
        </article>
      </div>
    </div>
  );
}
