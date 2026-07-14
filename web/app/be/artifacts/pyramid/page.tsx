import type { Metadata } from 'next';
import PyramidArtifactBody from '@/components/artifacts/PyramidArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('pyramid', 'be'),
  alternates: altFor('/be/artifacts/pyramid'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('pyramid', 'be', '/be/artifacts/pyramid')} />
      <PyramidArtifactBody />
    </>
  );
}
