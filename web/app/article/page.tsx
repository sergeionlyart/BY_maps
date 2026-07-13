import type { Metadata } from 'next';
import ContentDoc from '@/components/ContentDoc';
import AuthorCard from '@/components/AuthorCard';
import JsonLd from '@/components/JsonLd';
import { loadContent } from '@/lib/content';
import { authors, ogImage, ogBase, altFor, articleJsonLd } from '@/lib/seo';

const c = loadContent('ru', 'article');
export const metadata: Metadata = {
  title: c.title,
  description: c.description,
  authors,
  alternates: altFor('/article'),
  openGraph: { ...ogBase, locale: 'ru_RU', title: c.title, description: c.description, images: [ogImage] },
};

export default function Page() {
  return (
    <>
      <JsonLd data={articleJsonLd({ title: c.title, description: c.description, path: '/article', lang: 'ru' })} />
      <ContentDoc body={c.body} toc={true} lang="ru" footer={<AuthorCard variant="full" lang="ru" />} />
    </>
  );
}
