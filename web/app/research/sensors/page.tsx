import type { Metadata } from 'next';
import SensorsView from '@/components/SensorsView';
import ResearchShell from '@/components/ResearchShell';
import { authors, altFor } from '@/lib/seo';

export const metadata: Metadata = {
  alternates: altFor('/research/sensors'),
  authors,
  title: 'Второй сенсор — Население Беларуси',
  description:
    'Проверка официального ряда численности районов Беларуси двумя независимыми датчиками — спутниковой раскладкой населения GHS-POP и ночными огнями: где они согласны, где расходятся и почему свет не годится как прибор миграции.',
};

export default function SensorsPage() {
  return (
    <ResearchShell
      code="INF-21"
      version="v1.0.0"
      title="Второй сенсор"
      lead="Можно ли проверить официальную численность районов, не заглядывая в саму статистику? Мы сверили её с двумя физически разными датчиками. Спутниковая раскладка населения по застройке согласна с официальным рядом в главном: ρ = 0,79, знак изменения совпадает в 109 районах из 117. Ночные огни — нет: свет хорошо показывает, где живут люди, но не куда они уходят. Три из четырёх заранее заявленных гипотез опровергнуты, и это тоже результат."
    >
      <SensorsView />
    </ResearchShell>
  );
}
