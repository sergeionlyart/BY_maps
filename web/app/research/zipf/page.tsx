import type { Metadata } from 'next';
import Link from 'next/link';
import ZipfView from '@/components/ZipfView';
import AuthorCard from '@/components/AuthorCard';
import { authors } from '@/lib/seo';

export const metadata: Metadata = {
  authors,
  title: 'Иерархия городов и закон Ципфа — Население Беларуси',
  description:
    'Rank-size распределение городов Беларуси 1897–2026: наклон Ципфа держится у −1, но примация Минска выросла с 1,4× до 4× при ожидании 2×.',
};

export default function ZipfPage() {
  return (
    <div className="page page-wide">
      <div className="page-breadcrumb">
        <Link href="/research">Исследования</Link> · INF-01 · v1.0.0
      </div>
      <h1>Иерархия городов и закон Ципфа, 1897–2026</h1>
      <p className="page-lead">
        Закон Ципфа предсказывает: второй город страны вдвое меньше первого,
        третий — втрое, и так далее (наклон −1 в лог-лог осях). Городская
        система Беларуси следует этому закону весь наблюдаемый период — кроме
        столицы. С послевоенной индустриализацией Минск оторвался от
        «положенного» размера: сегодня он в 4 раза больше Гомеля при
        ципфовском ожидании 2. От сети местечек — к макроцефалии.
      </p>
      <ZipfView />
      <AuthorCard variant="compact" lang="ru" />
    </div>
  );
}
