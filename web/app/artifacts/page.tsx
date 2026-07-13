import type { Metadata } from 'next';
import { loadContent } from '@/lib/content';
import ArtifactsIndexBody from '@/components/artifacts/ArtifactsIndexBody';

const intro = loadContent('ru', 'data-artifacts');

export const metadata: Metadata = {
  title: intro.title || 'Данные и артефакты — BY Maps',
  description: intro.description,
  alternates: { languages: { ru: '/artifacts', be: '/be/artifacts' } },
};

export default function ArtifactsPage() {
  return <ArtifactsIndexBody introBody={intro.body} />;
}
