import type { Metadata } from 'next';
import UrbanOverhangArtifactBody from '@/components/artifacts/UrbanOverhangArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactDataset, artifactMeta } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('urban-overhang', 'be'),
  alternates: altFor('/be/artifacts/urban-overhang'),
};

export default function UrbanOverhangArtifactPageBe() {
  return (
    <>
      <JsonLd data={artifactDataset('urban-overhang', 'be', '/be/artifacts/urban-overhang')} />
      <UrbanOverhangArtifactBody />
    </>
  );
}
