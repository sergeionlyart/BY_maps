import type { Metadata } from 'next';
import GridView from '@/components/GridView';
import ResearchShell from '@/components/ResearchShell';
import { authors, altFor } from '@/lib/seo';

export const metadata: Metadata = {
  alternates: altFor('/research/grid'),
  authors,
  title: 'Полотно: карта расселения Беларуси по сетке 1 км, 1975–2050 — Население Беларуси',
  description:
    'Страна без административных границ: сетка в один километр, население по клеткам с 1975 по 2050 год из GHS-POP, откалиброванного под официальную статистику. Люди концентрируются быстрее, чем пустеет территория — но перекрёстная проверка с ночными огнями не подтвердила направление изменений, поэтому вывод подаётся как открытый вопрос.',
};

export default function GridPage() {
  return (
    <ResearchShell
      code="INF-15"
      version="v1.0.0"
      title="Полотно: карта расселения Беларуси по сетке 1 км, 1975–2050"
      lead="Страна без административных границ: сетка в один километр вместо 118 районов одним цветом. Клетки — из открытого набора данных Европейской комиссии (GHS-POP), приведённого к официальной статистике, с 1975 по 2050 год."
    >
      <GridView />
    </ResearchShell>
  );
}
