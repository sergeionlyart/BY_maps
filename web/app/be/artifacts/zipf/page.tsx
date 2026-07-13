import type { Metadata } from 'next';
import ZipfArtifactBody from '@/components/artifacts/ZipfArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('zipf', 'be'),
  alternates: altFor('/be/artifacts/zipf'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('zipf', 'be', '/be/artifacts/zipf')} />
      <ZipfArtifactBody />
    </>
  );
}
