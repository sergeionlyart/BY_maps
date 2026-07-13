import type { Metadata } from 'next';
import ZipfView from '@/components/ZipfView';
import ResearchShell from '@/components/ResearchShell';
import { authors, altFor } from '@/lib/seo';

export const metadata: Metadata = {
  authors,
  title: 'Іерархія гарадоў і закон Цыпфа — Насельніцтва Беларусі',
  description:
    'Rank-size размеркаванне гарадоў Беларусі 1897–2026: нахіл Цыпфа трымаецца каля −1, але прымацыя Мінска вырасла з 1,4× да 4× пры чаканні 2×.',
  alternates: altFor('/be/research/zipf'),
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
