import type { Metadata } from 'next';
import UrbanOverhangArtifactBody from '@/components/artifacts/UrbanOverhangArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactDataset, artifactMeta } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('urban-overhang', 'ru'),
  alternates: altFor('/artifacts/urban-overhang'),
};

export default function UrbanOverhangArtifactPage() {
  return (
    <>
      <JsonLd data={artifactDataset('urban-overhang', 'ru', '/artifacts/urban-overhang')} />
      <UrbanOverhangArtifactBody />
    </>
  );
}
