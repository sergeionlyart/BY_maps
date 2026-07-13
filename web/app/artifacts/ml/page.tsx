import type { Metadata } from 'next';
import MLChallengerArtifactBody from '@/components/artifacts/MLChallengerArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет mlchallenger — версии и состав',
  description: 'Проверяемый пакет ML-challenger: диагностика систематических ошибок структурной модели районов (градиентный бустинг на CCR-остатке, 2019–2026).',
  alternates: { languages: { ru: '/artifacts/ml', be: '/be/artifacts/ml' } },
};

export default function MLChallengerArtifactPage() {
  return <MLChallengerArtifactBody />;
}
