import type { Metadata } from 'next';
import ChernobylArtifactBody from '@/components/artifacts/ChernobylArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет chernobyl — версіі і склад',
  description: 'Правяральны пакет даследавання «Чарнобыльскі след» (INF-07).',
  alternates: { languages: { ru: '/artifacts/chernobyl', be: '/be/artifacts/chernobyl' } },
};

export default function Page() {
  return <ChernobylArtifactBody />;
}
