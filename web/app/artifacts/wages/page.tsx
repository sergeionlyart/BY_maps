import type { Metadata } from 'next';
import WagesArtifactBody from '@/components/artifacts/WagesArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет wages — версии и состав',
  description: 'Проверяемый пакет исследования «Зарплата × динамика населения» (INF-03).',
  alternates: { languages: { ru: '/artifacts/wages', be: '/be/artifacts/wages' } },
};

export default function WagesArtifactPage() {
  return <WagesArtifactBody />;
}
