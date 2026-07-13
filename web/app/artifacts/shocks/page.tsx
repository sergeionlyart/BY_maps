import type { Metadata } from 'next';
import ShocksArtifactBody from '@/components/artifacts/ShocksArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('shocks', 'ru'),
  alternates: altFor('/artifacts/shocks'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('shocks', 'ru', '/artifacts/shocks')} />
      <ShocksArtifactBody />
    </>
  );
}
