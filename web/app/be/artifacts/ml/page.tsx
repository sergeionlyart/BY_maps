import type { Metadata } from 'next';
import MLChallengerArtifactBody from '@/components/artifacts/MLChallengerArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('ml', 'be'),
  alternates: altFor('/be/artifacts/ml'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('ml', 'be', '/be/artifacts/ml')} />
      <MLChallengerArtifactBody />
    </>
  );
}
