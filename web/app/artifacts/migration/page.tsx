import type { Metadata } from 'next';
import MigrationArtifactBody from '@/components/artifacts/MigrationArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('migration', 'ru'),
  alternates: altFor('/artifacts/migration'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('migration', 'ru', '/artifacts/migration')} />
      <MigrationArtifactBody />
    </>
  );
}
