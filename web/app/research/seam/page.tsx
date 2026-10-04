import type { Metadata } from 'next';
import SeamView from '@/components/SeamView';
import ResearchShell from '@/components/ResearchShell';
import { authors, altFor } from '@/lib/seo';

export const metadata: Metadata = {
  alternates: altFor('/research/seam'),
  authors,
  title: 'Шов на карте: Беларусь и соседи по обе стороны границы — Население Беларуси',
  description:
    'Разрывная регрессия на пяти границах Беларуси по спутниковым слоям: 234 тысячи квадратов 1 км, застройка WSF и GHSL, ночные огни DMSP и VIIRS, пашня GLAD. Шов есть в полях, но не в домах и не в огнях; гипотезы зафиксированы до расчёта.',
};

export default function SeamPage() {
  return (
    <ResearchShell
      code="INF-20"
      version="v1.0.0"
      title="Шов на карте: Беларусь и соседи по обе стороны границы"
      lead="Граница Беларуси с каждым из пяти соседей идёт по одинаковому ландшафту: почвы, климат и реки на линии не меняются, меняются только правила — с 1991 года. Мы разбили полосу по 50 км по обе стороны всех пяти границ на 234 тысячи квадратов по 1 км и сравнили у самой линии то, что видно из космоса: рост застройки, ночные огни и пашню. Итог: государство оставило шов в полях, а не в домах и не в огнях. Гипотезы записаны до расчёта, поэтому мы показываем и то, что не подтвердилось."
    >
      <SeamView />
    </ResearchShell>
  );
}
