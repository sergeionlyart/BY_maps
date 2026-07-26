import type { Metadata } from 'next';
import GridArtifactBody from '@/components/artifacts/GridArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactDataset, artifactMeta } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('grid', 'ru'),
  alternates: altFor('/artifacts/grid'),
};

export default function GridArtifactPage() {
  return (
    <>
      <JsonLd data={artifactDataset('grid', 'ru', '/artifacts/grid')} />
      <GridArtifactBody />
    </>
  );
}
