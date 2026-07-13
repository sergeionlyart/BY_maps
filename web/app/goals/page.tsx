import type { Metadata } from 'next';
import { altFor } from '@/lib/seo';
import ContentDoc from '@/components/ContentDoc';
import { loadContent } from '@/lib/content';

const c = loadContent('ru', 'goals');
export const metadata: Metadata = {
  title: c.title,
  description: c.description,
  alternates: altFor('/goals'),
};

export default function Page() {
  return <ContentDoc body={c.body} toc={false} lang="ru" />;
}
