import type { Metadata } from 'next';
import ShocksArtifactBody from '@/components/artifacts/ShocksArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет shocks — версіі і склад',
  description: 'Правяральны пакет даследавання «Дэмаграфічныя шокі XX стагоддзя» (INF-09).',
  alternates: { languages: { ru: '/artifacts/shocks', be: '/be/artifacts/shocks' } },
};

export default function Page() {
  return <ShocksArtifactBody />;
}
