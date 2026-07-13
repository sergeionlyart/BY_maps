import type { Metadata } from 'next';
import { altFor } from '@/lib/seo';
import ResearchIndex from '@/components/ResearchIndex';

export const metadata: Metadata = {
  alternates: altFor('/research'),
  title: 'Исследования — Население Беларуси',
  description: 'Галерея исследований проекта: иерархия городов, старение районов, миграция и другие.',
};

export default function ResearchPage() {
  return <ResearchIndex />;
}
