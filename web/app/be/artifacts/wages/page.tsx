import type { Metadata } from 'next';
import WagesArtifactBody from '@/components/artifacts/WagesArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет wages — версіі і склад',
  description: 'Правяральны пакет даследавання «Зарплата × дынаміка насельніцтва» (INF-03).',
  alternates: { languages: { ru: '/artifacts/wages', be: '/be/artifacts/wages' } },
};

export default function Page() {
  return <WagesArtifactBody />;
}
