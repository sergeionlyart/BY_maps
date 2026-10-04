import type { Metadata } from 'next';
import SexRatioView from '@/components/SexRatioView';
import ResearchShell from '@/components/ResearchShell';
import { authors, altFor } from '@/lib/seo';

export const metadata: Metadata = {
  alternates: altFor('/be/research/sexratio'),
  authors,
  title: 'Карта, дзе не хапае мужчын — Насельніцтва Беларусі',
  description:
    'Дзе ў Беларусі не хапае мужчын, а дзе жанчын: суадносіны полаў па 17 узроставых групах і 118 раёнах ад перапісу 2009 да 2056 года, падзел «памерлі ці з’ехалі» і апровергнутая гіпотэза пра сувязь з аддаленасцю ад Мінска.',
};

export default function SexRatioPage() {
  return (
    <ResearchShell
      code="INF-20"
      version="v1.0.0"
      title="Карта, дзе не хапае мужчын"
      lead="На сто жанчын у Беларусі прыпадае 86 мужчын — але за гэтай сярэдняй цыфрай стаяць два супрацьлеглыя перакосы. У 95 раёнах са 118 у ўзросце 25–39 мужчын больш, чым жанчын, а ў 70+ мужчын не застаецца амаль нідзе: медыяна па раёнах — 40 на сто жанчын. Мы правяралі, ці ўзмацняецца мужчынская перавага з аддаленасцю ад Мінска, і атрымалі адваротнае: сувязь адмоўная, максімум перакосу — у паясе паўтары гадзіны ад сталіцы, а не на перыферыі."
    >
      <SexRatioView />
    </ResearchShell>
  );
}
