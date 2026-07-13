import type { Metadata } from 'next';
import { altFor } from '@/lib/seo';
import { loadContent } from '@/lib/content';
import ArtifactsIndexBody from '@/components/artifacts/ArtifactsIndexBody';

const intro = loadContent('ru', 'data-artifacts');

export const metadata: Metadata = {
  title: intro.title || 'Данные и артефакты — BY Maps',
  description: intro.description,
  alternates: altFor('/artifacts'),
};

export default function ArtifactsPage() {
  return <ArtifactsIndexBody introBody={intro.body} />;
}
