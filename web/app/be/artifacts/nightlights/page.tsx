import type { Metadata } from 'next';
import NightlightsArtifactBody from '@/components/artifacts/NightlightsArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет nightlights — версіі і склад',
  description: 'Правяральны пакет даследавання «Начныя агні супраць афіцыйнай статыстыкі» (INF-08).',
  alternates: { languages: { ru: '/artifacts/nightlights', be: '/be/artifacts/nightlights' } },
};

export default function Page() {
  return <NightlightsArtifactBody />;
}
