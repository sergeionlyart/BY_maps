import type { Metadata } from 'next';
import ContentDoc from '@/components/ContentDoc';
import AuthorCard from '@/components/AuthorCard';
import JsonLd from '@/components/JsonLd';
import { loadContent } from '@/lib/content';
import { authors, ogImage, ogBase, altFor, articleJsonLd } from '@/lib/seo';

const c = loadContent('be', 'article');
export const metadata: Metadata = {
  title: c.title,
  description: c.description,
  authors,
  alternates: altFor('/be/article'),
  openGraph: { ...ogBase, locale: 'be_BY', title: c.title, description: c.description, images: [ogImage] },
};

export default function Page() {
  return (
    <>
      <JsonLd data={articleJsonLd({ title: c.title, description: c.description, path: '/be/article', lang: 'be' })} />
      <ContentDoc body={c.body} toc={true} lang="be" footer={<AuthorCard variant="full" lang="be" />} />
    </>
  );
}
