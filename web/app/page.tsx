import type { Metadata } from 'next';
import LandingBody from '@/components/LandingBody';
import JsonLd from '@/components/JsonLd';
import { altFor, webSiteJsonLd, organizationJsonLd } from '@/lib/seo';

// title/description наследуются из корневого layout (русская главная).
export const metadata: Metadata = {
  alternates: altFor('/'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={[webSiteJsonLd('ru'), organizationJsonLd()]} />
      <LandingBody />
    </>
  );
}
