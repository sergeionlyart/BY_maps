import type { Metadata } from 'next';
import AgingView from '@/components/AgingView';
import ResearchShell from '@/components/ResearchShell';
import { authors, altFor } from '@/lib/seo';

export const metadata: Metadata = {
  authors,
  title: 'Старэнне раёнаў — Насельніцтва Беларусі',
  description:
    'Узроставая структура 118 раёнаў па перапісах 2009/2019: медыянны ўзрост, доля 65+, дэмаграфічная нагрузка і контрфактная перасунка «пры нулявой міграцыі».',
  alternates: altFor('/be/research/aging'),
};

export default function AgingPage() {
  return (
    <ResearchShell
      code="INF-02"
      version="v1.0.3"
      title="Старение районов: где депопуляция самоподдерживается"
      lead="Десятилетия оттока молодёжи изменили саму возрастную структуру периферийных районов — настолько, что убыль продолжится, даже если миграция полностью остановится: некому рожать и всё больше поколений входит в старшие возраста. Когортная передвижка без миграции показывает: естественная убыль ждёт 117 из 118 районов, а 28 районов в ближайшие 60 лет пересекут порог, за которым 65-летних и старше — почти треть населения."
    >
      <AgingView />
    </ResearchShell>
  );
}
