import type { Metadata } from 'next';
import WagesArtifactBody from '@/components/artifacts/WagesArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('wages', 'ru'),
  alternates: altFor('/artifacts/wages'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('wages', 'ru', '/artifacts/wages')} />
      <WagesArtifactBody />
    </>
  );
}
