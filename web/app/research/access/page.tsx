import type { Metadata } from 'next';
import Link from 'next/link';
import AccessView from '@/components/AccessView';
import AuthorCard from '@/components/AuthorCard';
import { authors } from '@/lib/seo';

export const metadata: Metadata = {
  authors,
  title: 'Транспортная доступность и «тень Минска» — Население Беларуси',
  description:
    'Пояса травел-тайма до Минска и облцентров по дорожному графу OSM: кольцо 1,5–2,5 ч убывает быстрее и пригорода, и дальней периферии; что закрытие переходов с ЕС изменило для западных районов.',
};

export default function AccessPage() {
  return (
    <div className="page page-wide">
      <div className="page-breadcrumb">
        <Link href="/research">Исследования</Link> · INF-04 · v1.0.0
      </div>
      <h1>Транспортная доступность: «тень Минска» и закрытая граница</h1>
      <p className="page-lead">
        Полтора-два часа пути до большого города — самое опасное место на
        карте Беларуси: кольцо в 1,5–2,5 ч от центров теряет население
        быстрее и ближнего пригорода, и дальней периферии — профиль
        немонотонный, центр «вытягивает» ровно то, до чего дотягивается
        маятниковая миграция (растёт при этом только пояс до 45 мин от
        самого Минска: +11,9%). Второй сюжет — граница: из 13 легковых
        переходов в ЕС к весне 2024 года осталось 4, и гродненский пояс
        почти на три года «отъехал» от Европы на 1,5–2,5 часа, тогда как
        брестский коридор терял Тересполь лишь на две недели учений
        «Запад-2025».
      </p>
      <AccessView />
      <AuthorCard variant="compact" lang="ru" />
    </div>
  );
}
