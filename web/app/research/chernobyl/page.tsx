import type { Metadata } from 'next';
import Link from 'next/link';
import ChernobylView from '@/components/ChernobylView';
import AuthorCard from '@/components/AuthorCard';
import { authors } from '@/lib/seo';

export const metadata: Metadata = {
  authors,
  title: 'Чернобыльский след — Население Беларуси',
  description:
    'Как эвакуация и отселение изменили траектории юго-восточных районов: официальный реестр зон (НПА с реквизитами) и сравнение с демографически схожими контрольными районами.',
};

export default function ChernobylPage() {
  return (
    <div className="page page-wide">
      <div className="page-breadcrumb">
        <Link href="/research">Исследования</Link> · INF-07 · v1.0.0
      </div>
      <h1>Чернобыльский след: траектории отселённых районов</h1>
      <p className="page-lead">
        Катастрофа 1986 года вырезала из карты юго-востока страны целый пласт:
        только из трёх наиболее пострадавших районов в 1986 году эвакуировано
        22 тыс. человек, всего государство навсегда отселило ~138 тыс., ещё
        ~200 тыс. уехали сами; 479 населённых пунктов прекратили существование. Но районы теряли население
        и без Чернобыля. Чтобы отделить эффект катастрофы от общего сельского
        оттока, каждому пострадавшему району подобран «двойник» — демографически
        схожий район вне зон загрязнения. Разрыв траекторий после 1986 года —
        мера чернобыльского следа.
      </p>
      <ChernobylView />
      <AuthorCard variant="compact" lang="ru" />
    </div>
  );
}
