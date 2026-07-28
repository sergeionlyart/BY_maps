import type { Metadata } from 'next';
import ContentDoc from '@/components/ContentDoc';
import AuthorCard from '@/components/AuthorCard';
import JsonLd from '@/components/JsonLd';
import { loadContent } from '@/lib/content';
import { authors, ogBase, altFor, articleJsonLd, absUrl } from '@/lib/seo';

const c = loadContent('be', 'article-grid');
const ogImage = { url: '/content/img/grid/cover.webp', width: 1600, height: 900 };
export const metadata: Metadata = {
  title: c.title,
  description: c.description,
  authors,
  alternates: altFor('/be/article/grid'),
  openGraph: { ...ogBase, locale: 'be_BY', title: c.title, description: c.description, images: [ogImage] },
};

export default function Page() {
  return (
    <>
      <JsonLd data={articleJsonLd({
        title: c.title, description: c.description, path: '/be/article/grid', lang: 'be',
        scholarly: false, image: absUrl(ogImage.url),
      })} />
      <ContentDoc body={c.body} toc={true} lang="be" footer={<AuthorCard variant="full" lang="be" />} />
    </>
  );
}
