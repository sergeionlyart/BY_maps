import type { Metadata } from 'next';
import PyramidArtifactBody from '@/components/artifacts/PyramidArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('pyramid', 'ru'),
  alternates: altFor('/artifacts/pyramid'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('pyramid', 'ru', '/artifacts/pyramid')} />
      <PyramidArtifactBody />
    </>
  );
}
