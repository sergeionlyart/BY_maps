import type { Metadata } from 'next';
import ResearchIndex from '@/components/ResearchIndex';

export const metadata: Metadata = {
  title: 'Даследаванні — Насельніцтва Беларусі',
  description: 'Галерэя даследаванняў праекта: іерархія гарадоў, старэнне раёнаў, міграцыя і іншыя.',
  alternates: { languages: { ru: '/research', be: '/be/research' } },
};

export default function ResearchPage() {
  return <ResearchIndex />;
}
