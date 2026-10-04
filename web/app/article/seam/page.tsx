import type { Metadata } from 'next';
import ContentDoc from '@/components/ContentDoc';
import AuthorCard from '@/components/AuthorCard';
import ArticlesMenu from '@/components/ArticlesMenu';
import JsonLd from '@/components/JsonLd';
import { loadContent } from '@/lib/content';
import { authors, ogBase, altFor, articleJsonLd, absUrl } from '@/lib/seo';

const c = loadContent('ru', 'article-seam');
const ogImage = { url: '/content/img/seam/cover.webp', width: 1600, height: 900 };
export const metadata: Metadata = {
  title: c.title,
  description: c.description,
  authors,
  alternates: altFor('/article/seam'),
  openGraph: { ...ogBase, locale: 'ru_RU', title: c.title, description: c.description, images: [ogImage] },
};

export default function Page() {
  return (
    <>
      <JsonLd data={articleJsonLd({
        title: c.title, description: c.description, path: '/article/seam', lang: 'ru',
        scholarly: false, image: absUrl(ogImage.url),
      })} />
      <ContentDoc
        body={c.body} toc={true} lang="ru"
        articlesNav={<ArticlesMenu current="/article/seam" lang="ru" />}
        footer={<AuthorCard variant="full" lang="ru" />}
      />
    </>
  );
}
