import type { Metadata } from 'next';
import ResearchIndex from '@/components/ResearchIndex';

export const metadata: Metadata = {
  title: 'Исследования — Население Беларуси',
  description: 'Галерея исследований проекта: иерархия городов, старение районов, миграция и другие.',
};

export default function ResearchPage() {
  return <ResearchIndex />;
}
