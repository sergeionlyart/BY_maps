import type { Metadata } from 'next';
import GridArtifactBody from '@/components/artifacts/GridArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactDataset, artifactMeta } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('grid', 'be'),
  alternates: altFor('/be/artifacts/grid'),
};

export default function GridArtifactPageBe() {
  return (
    <>
      <JsonLd data={artifactDataset('grid', 'be', '/be/artifacts/grid')} />
      <GridArtifactBody />
    </>
  );
}
