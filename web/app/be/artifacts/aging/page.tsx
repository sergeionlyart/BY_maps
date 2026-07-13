import type { Metadata } from 'next';
import AgingArtifactBody from '@/components/artifacts/AgingArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('aging', 'be'),
  alternates: altFor('/be/artifacts/aging'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('aging', 'be', '/be/artifacts/aging')} />
      <AgingArtifactBody />
    </>
  );
}
