import type { Metadata } from 'next';
import MigrationArtifactBody from '@/components/artifacts/MigrationArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет migration — версіі і склад',
  description: 'Правяральны пакет даследавання «Унутраная і знешняя міграцыя» (INF-05).',
  alternates: { languages: { ru: '/artifacts/migration', be: '/be/artifacts/migration' } },
};

export default function Page() {
  return <MigrationArtifactBody />;
}
