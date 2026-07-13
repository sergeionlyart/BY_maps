import type { Metadata } from 'next';
import AccessArtifactBody from '@/components/artifacts/AccessArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет access — версіі і склад',
  description: 'Правяральны пакет даследавання «Транспартная даступнасць і „цень Мінска"» (INF-04).',
  alternates: { languages: { ru: '/artifacts/access', be: '/be/artifacts/access' } },
};

export default function Page() {
  return <AccessArtifactBody />;
}
