import type { Metadata } from 'next';
import SensorsArtifactBody from '@/components/artifacts/SensorsArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('sensors', 'ru'),
  alternates: altFor('/artifacts/sensors'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('sensors', 'ru', '/artifacts/sensors')} />
      <SensorsArtifactBody />
    </>
  );
}
