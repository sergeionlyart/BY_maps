import type { Metadata } from 'next';
import SensorsArtifactBody from '@/components/artifacts/SensorsArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('sensors', 'be'),
  alternates: altFor('/be/artifacts/sensors'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('sensors', 'be', '/be/artifacts/sensors')} />
      <SensorsArtifactBody />
    </>
  );
}
