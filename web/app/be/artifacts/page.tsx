import type { Metadata } from 'next';
import { loadContent } from '@/lib/content';
import ArtifactsIndexBody from '@/components/artifacts/ArtifactsIndexBody';

const intro = loadContent('be', 'data-artifacts');

export const metadata: Metadata = {
  title: intro.title || 'Даныя і артэфакты — BY Maps',
  description: intro.description,
  alternates: { languages: { ru: '/artifacts', be: '/be/artifacts' } },
};

export default function Page() {
  return <ArtifactsIndexBody introBody={intro.body} />;
}
