import type { Metadata } from 'next';
import PensionView from '@/components/PensionView';
import ResearchShell from '@/components/ResearchShell';
import { authors, altFor } from '@/lib/seo';

export const metadata: Metadata = {
  alternates: altFor('/be/research/pension'),
  authors,
  title: 'Хто каго ўтрымлівае: каэфіцыент падтрымкі па раёнах Беларусі — Насельніцтва Беларусі',
  description:
    'Колькі працуючых прыпадае на аднаго чалавека старэйшага за працаздольны ўзрост — па кожным з 118 раёнаў Беларусі, 2009–2056: карта, сцэнарыі, тры варыянты пенсійнага ўзросту, «знайдзі сябе».',
};

export default function PensionPageBe() {
  return (
    <ResearchShell
      code="INF-13"
      version="v1.0.0"
      title="Хто каго ўтрымлівае"
      lead="Колькі працуючых прыпадае на аднаго пажылога — у вашым раёне, сёння і праз трыццаць гадоў. Мы палічылі гэтую арыфметыку па кожным з 118 раёнаў Беларусі, ад перапісу 2009 года да 2056-га."
      hideHeader
    >
      <PensionView />
    </ResearchShell>
  );
}
