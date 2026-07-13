import type { Metadata } from 'next';
import NightlightsArtifactBody from '@/components/artifacts/NightlightsArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('nightlights', 'ru'),
  alternates: altFor('/artifacts/nightlights'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('nightlights', 'ru', '/artifacts/nightlights')} />
      <NightlightsArtifactBody />
    </>
  );
}
