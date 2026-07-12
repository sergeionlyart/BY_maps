import type { Metadata } from 'next';
import ContentDoc from '@/components/ContentDoc';
import { loadContent } from '@/lib/content';

const c = loadContent('be', 'article');
export const metadata: Metadata = {
  title: c.title,
  description: c.description,
  alternates: { languages: { ru: '/article', be: '/be/article' } },
};

export default function Page() {
  return <ContentDoc body={c.body} toc={true} lang="be" />;
}
