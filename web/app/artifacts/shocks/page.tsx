import type { Metadata } from 'next';
import ShocksArtifactBody from '@/components/artifacts/ShocksArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет shocks — версии и состав',
  description: 'Проверяемый пакет исследования «Демографические шоки XX века» (INF-09).',
  alternates: { languages: { ru: '/artifacts/shocks', be: '/be/artifacts/shocks' } },
};

export default function ShocksArtifactPage() {
  return <ShocksArtifactBody />;
}
