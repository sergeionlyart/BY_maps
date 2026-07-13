import type { Metadata } from 'next';
import NightlightsArtifactBody from '@/components/artifacts/NightlightsArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('nightlights', 'be'),
  alternates: altFor('/be/artifacts/nightlights'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('nightlights', 'be', '/be/artifacts/nightlights')} />
      <NightlightsArtifactBody />
    </>
  );
}
