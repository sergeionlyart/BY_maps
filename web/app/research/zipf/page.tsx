import type { Metadata } from 'next';
import ZipfView from '@/components/ZipfView';
import ResearchShell from '@/components/ResearchShell';
import { authors, altFor } from '@/lib/seo';

export const metadata: Metadata = {
  alternates: altFor('/research/zipf'),
  authors,
  title: 'Иерархия городов и закон Ципфа — Население Беларуси',
  description:
    'Rank-size распределение городов Беларуси 1897–2026: наклон Ципфа держится у −1, но примация Минска выросла с 1,4× до 4× при ожидании 2×.',
};

export default function ZipfPage() {
  return (
    <ResearchShell
      code="INF-01"
      version="v1.0.0"
      title="Иерархия городов и закон Ципфа, 1897–2026"
      lead="Закон Ципфа предсказывает: второй город страны вдвое меньше первого, третий — втрое, и так далее (наклон −1 в лог-лог осях). Городская система Беларуси следует этому закону весь наблюдаемый период — кроме столицы. С послевоенной индустриализацией Минск оторвался от «положенного» размера: сегодня он в 4 раза больше Гомеля при ципфовском ожидании 2. От сети местечек — к макроцефалии."
    >
      <ZipfView />
    </ResearchShell>
  );
}
