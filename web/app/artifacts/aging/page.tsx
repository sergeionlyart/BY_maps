import type { Metadata } from 'next';
import AgingArtifactBody from '@/components/artifacts/AgingArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('aging', 'ru'),
  alternates: altFor('/artifacts/aging'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('aging', 'ru', '/artifacts/aging')} />
      <AgingArtifactBody />
    </>
  );
}
