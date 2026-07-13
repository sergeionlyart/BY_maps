import type { Metadata } from 'next';
import MigrationArtifactBody from '@/components/artifacts/MigrationArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет migration — версии и состав',
  description: 'Проверяемый пакет исследования «Внутренняя и внешняя миграция» (INF-05).',
  alternates: { languages: { ru: '/artifacts/migration', be: '/be/artifacts/migration' } },
};

export default function MigrationArtifactPage() {
  return <MigrationArtifactBody />;
}
