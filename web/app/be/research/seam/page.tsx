import type { Metadata } from 'next';
import SeamView from '@/components/SeamView';
import ResearchShell from '@/components/ResearchShell';
import { authors, altFor } from '@/lib/seo';

export const metadata: Metadata = {
  authors,
  title: 'Шво на карце: Беларусь і суседзі па абодва бакі мяжы — Насельніцтва Беларусі',
  description:
    'Рэгрэсія разрыву на пяці межах Беларусі па спадарожнікавых слаях: 234 тысячы квадратаў 1 км, забудова WSF і GHSL, начныя агні DMSP і VIIRS, ралля GLAD. Шво ёсць у палях, але не ў дамах і не ў агнях; гіпотэзы зафіксаваныя да разліку.',
  alternates: altFor('/be/research/seam'),
};

export default function SeamPageBe() {
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
