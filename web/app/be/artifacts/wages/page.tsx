import type { Metadata } from 'next';
import WagesArtifactBody from '@/components/artifacts/WagesArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('wages', 'be'),
  alternates: altFor('/be/artifacts/wages'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('wages', 'be', '/be/artifacts/wages')} />
      <WagesArtifactBody />
    </>
  );
}
