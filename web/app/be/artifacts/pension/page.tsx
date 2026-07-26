import type { Metadata } from 'next';
import PensionArtifactBody from '@/components/artifacts/PensionArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactDataset, artifactMeta } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('pension', 'be'),
  alternates: altFor('/be/artifacts/pension'),
};

export default function PensionArtifactPageBe() {
  return (
    <>
      <JsonLd data={artifactDataset('pension', 'be', '/be/artifacts/pension')} />
      <PensionArtifactBody />
    </>
  );
}
