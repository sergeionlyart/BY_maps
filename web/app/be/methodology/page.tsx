import type { Metadata } from 'next';
import ContentDoc from '@/components/ContentDoc';
import { loadContent } from '@/lib/content';

const c = loadContent('be', 'methodology');
export const metadata: Metadata = {
  title: c.title,
  description: c.description,
  alternates: { languages: { ru: '/methodology', be: '/be/methodology' } },
};

export default function Page() {
  return <ContentDoc body={c.body} toc={false} lang="be" />;
}
