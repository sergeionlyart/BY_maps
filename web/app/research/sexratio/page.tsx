import type { Metadata } from 'next';
import SexRatioView from '@/components/SexRatioView';
import ResearchShell from '@/components/ResearchShell';
import { authors, altFor } from '@/lib/seo';

export const metadata: Metadata = {
  alternates: altFor('/research/sexratio'),
  authors,
  title: 'Карта, где не хватает мужчин — Население Беларуси',
  description:
    'Где в Беларуси не хватает мужчин, а где женщин: соотношение полов по 17 возрастным группам и 118 районам от переписи 2009 до 2056 года, разделение «умерли или уехали» и опровергнутая гипотеза о связи с удалённостью от Минска.',
};

export default function SexRatioPage() {
  return (
    <ResearchShell
      code="INF-21"
      version="v1.0.0"
      title="Карта, где не хватает мужчин"
      lead="На сто женщин в Беларуси приходится 86 мужчин — но за этой средней цифрой стоят два противоположных перекоса. В 95 районах из 118 в возрасте 25–39 мужчин больше, чем женщин, а в 70+ мужчин не остаётся почти нигде: медиана по районам — 40 на сто женщин. Мы проверяли, усиливается ли мужской перевес с удалённостью от Минска, и получили обратное: связь отрицательная, максимум перекоса — в поясе полутора часов от столицы, а не на периферии."
    >
      <SexRatioView />
    </ResearchShell>
  );
}
