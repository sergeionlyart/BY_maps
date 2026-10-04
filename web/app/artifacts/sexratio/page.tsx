import type { Metadata } from 'next';
import SexratioArtifactBody from '@/components/artifacts/SexratioArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('sexratio', 'ru'),
  alternates: altFor('/artifacts/sexratio'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('sexratio', 'ru', '/artifacts/sexratio')} />
      <SexratioArtifactBody />
    </>
  );
}
