import type { Metadata } from 'next';
import ContentDoc from '@/components/ContentDoc';
import AuthorCard from '@/components/AuthorCard';
import { loadContent } from '@/lib/content';
import { authors, ogImage, ogBase } from '@/lib/seo';

const c = loadContent('ru', 'article');
export const metadata: Metadata = {
  title: c.title,
  description: c.description,
  authors,
  alternates: { languages: { ru: '/article', be: '/be/article' } },
  openGraph: { ...ogBase, locale: 'ru_RU', title: c.title, description: c.description, images: [ogImage] },
};

export default function Page() {
  return <ContentDoc body={c.body} toc={true} lang="ru" footer={<AuthorCard variant="full" lang="ru" />} />;
}
