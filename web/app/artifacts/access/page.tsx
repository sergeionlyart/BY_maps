import type { Metadata } from 'next';
import AccessArtifactBody from '@/components/artifacts/AccessArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет access — версии и состав',
  description: 'Проверяемый пакет исследования «Транспортная доступность и „тень Минска"» (INF-04).',
  alternates: { languages: { ru: '/artifacts/access', be: '/be/artifacts/access' } },
};

export default function AccessArtifactPage() {
  return <AccessArtifactBody />;
}
