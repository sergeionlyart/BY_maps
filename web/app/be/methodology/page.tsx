import type { Metadata } from 'next';
import fs from 'fs';
import path from 'path';
import Markdown from '@/components/Markdown';
import MethodologyTabs from '@/components/MethodologyTabs';
import AuthorCard from '@/components/AuthorCard';
import { loadContent } from '@/lib/content';

const overview = loadContent('be', 'methodology');

function readPublic(rel: string): string {
  return fs.readFileSync(path.join(process.cwd(), 'public', rel), 'utf8');
}
const method = readPublic('content/methodology.be.md');
const sources = readPublic('content/sources.be.md');

export const metadata: Metadata = {
  title: overview.title || 'Метадалогія — BY Maps',
  description: overview.description,
  alternates: { languages: { ru: '/methodology', be: '/be/methodology' } },
};

export default function Page() {
  return (
    <div className="page content-page">
      <article className="content">
        <Markdown text={overview.body} />
      </article>
      <MethodologyTabs method={method} sources={sources} />
      <AuthorCard variant="callout" lang="be" />
    </div>
  );
}
