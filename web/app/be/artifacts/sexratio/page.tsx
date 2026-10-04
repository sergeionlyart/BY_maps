import type { Metadata } from 'next';
import SexratioArtifactBody from '@/components/artifacts/SexratioArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('sexratio', 'be'),
  alternates: altFor('/be/artifacts/sexratio'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('sexratio', 'be', '/be/artifacts/sexratio')} />
      <SexratioArtifactBody />
    </>
  );
}
