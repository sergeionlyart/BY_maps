import type { Metadata } from 'next';
import NightlightsArtifactBody from '@/components/artifacts/NightlightsArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет nightlights — версии и состав',
  description: 'Проверяемый пакет исследования «Ночные огни против официальной статистики» (INF-08).',
  alternates: { languages: { ru: '/artifacts/nightlights', be: '/be/artifacts/nightlights' } },
};

export default function NightlightsArtifactPage() {
  return <NightlightsArtifactBody />;
}
