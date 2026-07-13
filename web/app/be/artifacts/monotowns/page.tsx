import type { Metadata } from 'next';
import MonotownsArtifactBody from '@/components/artifacts/MonotownsArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет monotowns — версіі і склад',
  description: 'Правяральны пакет даследавання «Монагарады і горадаўтваральныя прадпрыемствы» (INF-06).',
  alternates: { languages: { ru: '/artifacts/monotowns', be: '/be/artifacts/monotowns' } },
};

export default function Page() {
  return <MonotownsArtifactBody />;
}
