import type { Metadata } from 'next';
import MonotownsArtifactBody from '@/components/artifacts/MonotownsArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет monotowns — версии и состав',
  description: 'Проверяемый пакет исследования «Моногорода и градообразующие предприятия» (INF-06).',
  alternates: { languages: { ru: '/artifacts/monotowns', be: '/be/artifacts/monotowns' } },
};

export default function MonotownsArtifactPage() {
  return <MonotownsArtifactBody />;
}
