import type { Metadata } from 'next';
import { altFor } from '@/lib/seo';
import ResearchIndex from '@/components/ResearchIndex';

export const metadata: Metadata = {
  title: 'Даследаванні — Насельніцтва Беларусі',
  description: 'Галерэя даследаванняў праекта: іерархія гарадоў, старэнне раёнаў, міграцыя і іншыя.',
  alternates: altFor('/be/research'),
};

export default function ResearchPage() {
  return <ResearchIndex />;
}
