import type { Metadata } from 'next';
import WagesView from '@/components/WagesView';
import ResearchShell from '@/components/ResearchShell';
import { authors, altFor } from '@/lib/seo';

export const metadata: Metadata = {
  authors,
  title: 'Зарплата × дынаміка насельніцтва — Насельніцтва Беларусі',
  description:
    'Ці ідзе насельніцтва за грашыма: біварыятная карта зарплатнага дыферэнцыялу да Мінска і дзесяцігадовай дынамікі 118 раёнаў, рэгрэсійная эластычнасць і анамаліі.',
  alternates: altFor('/be/research/wages'),
};

export default function WagesPage() {
  return (
    <ResearchShell
      code="INF-03"
      version="v1.0.0"
      title="Зарплата × динамика: следует ли население за деньгами"
      lead="Медианный район платит чуть больше половины минской зарплаты — и именно туда, где платят больше, население и стекается: связь зарплатного дифференциала с десятилетней динамикой района положительна и значима во всех спецификациях. Но половину силы связи создают пригороды Минска, а самые интересные истории — в исключениях: Солигорский район в среднем за десятилетие платил больше Минска (калий), а Островецкий взлетел на стройке АЭС."
    >
      <WagesView />
    </ResearchShell>
  );
}
