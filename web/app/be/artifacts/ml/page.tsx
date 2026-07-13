import type { Metadata } from 'next';
import MLChallengerArtifactBody from '@/components/artifacts/MLChallengerArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет mlchallenger — версіі і склад',
  description: 'Правяральны пакет ML-challenger: дыягностыка сістэматычных памылак структурнай мадэлі раёнаў (градыентны бустынг на CCR-астатку, 2019–2026).',
  alternates: { languages: { ru: '/artifacts/ml', be: '/be/artifacts/ml' } },
};

export default function Page() {
  return <MLChallengerArtifactBody />;
}
