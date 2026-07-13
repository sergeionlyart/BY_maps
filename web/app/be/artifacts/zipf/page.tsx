import type { Metadata } from 'next';
import ZipfArtifactBody from '@/components/artifacts/ZipfArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет zipf — версіі і склад',
  description: 'Версіі правяральнага пакета даследавання «Іерархія гарадоў і закон Цыпфа».',
  alternates: { languages: { ru: '/artifacts/zipf', be: '/be/artifacts/zipf' } },
};

export default function Page() {
  return <ZipfArtifactBody />;
}
