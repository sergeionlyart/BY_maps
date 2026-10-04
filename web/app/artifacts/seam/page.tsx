import type { Metadata } from 'next';
import SeamArtifactBody from '@/components/artifacts/SeamArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactDataset, artifactMeta } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('seam', 'ru'),
  alternates: altFor('/artifacts/seam'),
};

export default function SeamArtifactPage() {
  return (
    <>
      <JsonLd data={artifactDataset('seam', 'ru', '/artifacts/seam')} />
      <SeamArtifactBody />
    </>
  );
}
