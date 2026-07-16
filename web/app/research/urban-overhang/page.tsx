import type { Metadata } from 'next';
import UrbanOverhangView from '@/components/urban/UrbanOverhangView';
import ResearchShell from '@/components/ResearchShell';
import { authors, altFor } from '@/lib/seo';

export const metadata: Metadata = {
  alternates: altFor('/research/urban-overhang'),
  authors,
  title: 'Цена пустеющей карты: материальный навес городов — Население Беларуси',
  description:
    'Спутниковый ряд застройки GHSL 1975–2020 против рядов населения 94 городов Беларуси: где накопленный фонд на жителя растёт при сокращении жителей, как активность смещается из ядра на край и сколько дорог приходится на тысячу оставшихся.',
};

export default function UrbanOverhangPage() {
  return (
    <ResearchShell
      code="INF-12"
      version="v1.0.0"
      title="Цена пустеющей карты: материальный навес городов, 1975–2020"
      lead="Когда город теряет жителей, его дома, улицы и сети никуда не исчезают. Мы совместили спутниковый ряд накопленной застройки (GHSL, 10 эпох с 1975 по 2020 год) с рядами населения 94 городов, ночными огнями и современным срезом OpenStreetMap — чтобы измерить «материальный навес»: сколько физического города приходится на одного оставшегося жителя, где активность стягивается из ядра на край и где этот разрыв не возник. «Цена» здесь — метафора удельной нагрузки, а не денежная величина: бюджетных расходов это исследование не измеряет."
    >
      <UrbanOverhangView />
    </ResearchShell>
  );
}
