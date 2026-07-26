import type { Metadata } from 'next';
import PensionArtifactBody from '@/components/artifacts/PensionArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactDataset, artifactMeta } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('pension', 'ru'),
  alternates: altFor('/artifacts/pension'),
};

export default function PensionArtifactPage() {
  return (
    <>
      <JsonLd data={artifactDataset('pension', 'ru', '/artifacts/pension')} />
      <PensionArtifactBody />
    </>
  );
}
