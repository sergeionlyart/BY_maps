import type { Metadata } from 'next';
import AccessArtifactBody from '@/components/artifacts/AccessArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('access', 'ru'),
  alternates: altFor('/artifacts/access'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('access', 'ru', '/artifacts/access')} />
      <AccessArtifactBody />
    </>
  );
}
