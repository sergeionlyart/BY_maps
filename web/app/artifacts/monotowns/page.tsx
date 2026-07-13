import type { Metadata } from 'next';
import MonotownsArtifactBody from '@/components/artifacts/MonotownsArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('monotowns', 'ru'),
  alternates: altFor('/artifacts/monotowns'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('monotowns', 'ru', '/artifacts/monotowns')} />
      <MonotownsArtifactBody />
    </>
  );
}
