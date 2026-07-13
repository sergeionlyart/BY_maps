import type { Metadata } from 'next';
import ForecastArtifactBody from '@/components/artifacts/ForecastArtifactBody';
import JsonLd from '@/components/JsonLd';
import { altFor } from '@/lib/seo';
import { artifactMeta, artifactDataset } from '@/lib/artifactsSeo';

export const metadata: Metadata = {
  ...artifactMeta('forecast', 'be'),
  alternates: altFor('/be/artifacts/forecast'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={artifactDataset('forecast', 'be', '/be/artifacts/forecast')} />
      <ForecastArtifactBody />
    </>
  );
}
