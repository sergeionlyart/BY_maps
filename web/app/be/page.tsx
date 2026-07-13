import type { Metadata } from 'next';
import LandingBody from '@/components/LandingBody';
import JsonLd from '@/components/JsonLd';
import { altFor, webSiteJsonLd, organizationJsonLd } from '@/lib/seo';

export const metadata: Metadata = {
  title: 'Насельніцтва Беларусі, 1897–2026',
  description:
    'Адкрытае даследаванне дэмаграфіі Беларусі на правяральных даных: карта за 129 гадоў, дзесяць даследаванняў і прагноз да 2075 года.',
  alternates: altFor('/be'),
};

export default function Page() {
  return (
    <>
      <JsonLd data={[webSiteJsonLd('be'), organizationJsonLd()]} />
      <LandingBody />
    </>
  );
}
