import type { Metadata } from 'next';
import ChernobylArtifactBody from '@/components/artifacts/ChernobylArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('chernobyl', 'ru'),
  alternates: altFor('/artifacts/chernobyl'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('chernobyl', 'ru', '/artifacts/chernobyl')} />
      <ChernobylArtifactBody />
    </>
  );
}
