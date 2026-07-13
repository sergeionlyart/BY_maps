import type { Metadata } from 'next';
import ChernobylArtifactBody from '@/components/artifacts/ChernobylArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет chernobyl — версии и состав',
  description: 'Проверяемый пакет исследования «Чернобыльский след» (INF-07).',
  alternates: { languages: { ru: '/artifacts/chernobyl', be: '/be/artifacts/chernobyl' } },
};

export default function ChernobylArtifactPage() {
  return <ChernobylArtifactBody />;
}
