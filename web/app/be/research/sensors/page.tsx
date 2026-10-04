import type { Metadata } from 'next';
import SensorsView from '@/components/SensorsView';
import ResearchShell from '@/components/ResearchShell';
import { authors, altFor } from '@/lib/seo';

export const metadata: Metadata = {
  alternates: altFor('/be/research/sensors'),
  authors,
  title: 'Другі сэнсар — Насельніцтва Беларусі',
  description:
    'Праверка афіцыйнага рада колькасці насельніцтва раёнаў Беларусі двума незалежнымі датчыкамі — спадарожнікавай раскладкай насельніцтва GHS-POP і начнымі агнямі: дзе яны згодныя, дзе разыходзяцца і чаму святло не прыдатнае як прыбор міграцыі.',
};

export default function SensorsPage() {
  return (
    <ResearchShell
      code="INF-21"
      version="v1.0.0"
      title="Другі сэнсар"
      lead="Ці можна праверыць афіцыйную колькасць насельніцтва раёнаў, не зазіраючы ў саму статыстыку? Мы зверылі яе з двума фізічна рознымі датчыкамі. Спадарожнікавая раскладка насельніцтва па забудове згодная з афіцыйным радам у галоўным: ρ = 0,79, знак змянення супадае ў 109 раёнах са 117. Начныя агні — не: святло добра паказвае, дзе жывуць людзі, але не куды яны сыходзяць. Тры з чатырох загадзя заяўленых гіпотэз апровергнуты, і гэта таксама вынік."
    >
      <SensorsView />
    </ResearchShell>
  );
}
