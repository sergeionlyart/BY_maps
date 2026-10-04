import type { Metadata } from 'next';
import SeamArtifactBody from '@/components/artifacts/SeamArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactDataset, artifactMeta } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('seam', 'be'),
  alternates: altFor('/be/artifacts/seam'),
};

export default function SeamArtifactPageBe() {
  return (
    <>
      <JsonLd data={artifactDataset('seam', 'be', '/be/artifacts/seam')} />
      <SeamArtifactBody />
    </>
  );
}
