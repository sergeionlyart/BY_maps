import type { Metadata } from 'next';
import MapPage from '../../map/page';

export const metadata: Metadata = {
  title: 'Карта — Насельніцтва Беларусі, 1897–2026',
  description:
    'Інтэрактыўная карта колькасці, шчыльнасці і канцэнтрацыі насельніцтва Беларусі: краіна, вобласці, раёны і гарады. Перапісы 1897–2019 і прагноз да 2075.',
  alternates: { languages: { ru: '/map', be: '/be/map' } },
};

export default MapPage;
