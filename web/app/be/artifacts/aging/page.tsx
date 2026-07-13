import type { Metadata } from 'next';
import AgingArtifactBody from '@/components/artifacts/AgingArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет aging — версіі і склад',
  description: 'Правяральны пакет даследавання «Старэнне раёнаў» (INF-02).',
  alternates: { languages: { ru: '/artifacts/aging', be: '/be/artifacts/aging' } },
};

export default function Page() {
  return <AgingArtifactBody />;
}
