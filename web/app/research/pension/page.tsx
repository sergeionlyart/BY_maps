import type { Metadata } from 'next';
import PensionView from '@/components/PensionView';
import ResearchShell from '@/components/ResearchShell';
import { authors, altFor } from '@/lib/seo';

export const metadata: Metadata = {
  alternates: altFor('/research/pension'),
  authors,
  title: 'Кто кого содержит: коэффициент поддержки по районам Беларуси — Население Беларуси',
  description:
    'Сколько работающих приходится на одного человека старше трудоспособного возраста — по каждому из 118 районов Беларуси, 2009–2056: карта, сценарии, три варианта пенсионного возраста, «найди себя».',
};

export default function PensionPage() {
  return (
    <ResearchShell
      code="INF-13"
      version="v1.0.0"
      title="Кто кого содержит"
      lead="Сколько работающих приходится на одного пожилого — в вашем районе, сегодня и через тридцать лет. Мы посчитали эту арифметику по каждому из 118 районов Беларуси, от переписи 2009 года до 2056-го."
      hideHeader
    >
      <PensionView />
    </ResearchShell>
  );
}
