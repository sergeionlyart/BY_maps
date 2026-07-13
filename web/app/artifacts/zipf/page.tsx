import type { Metadata } from 'next';
import ZipfArtifactBody from '@/components/artifacts/ZipfArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет zipf — версии и состав',
  description: 'Версии проверяемого пакета исследования «Иерархия городов и закон Ципфа».',
  alternates: { languages: { ru: '/artifacts/zipf', be: '/be/artifacts/zipf' } },
};

export default function ZipfArtifactPage() {
  return <ZipfArtifactBody />;
}
