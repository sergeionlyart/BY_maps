/** Реестр статей (длинные нарративные тексты через ContentDoc, в отличие от
 *  исследований — см. research.ts). Список используется боковым меню
 *  «Статьи» на страницах /article/* (см. ArticlesMenu в ContentDoc.tsx). */

export interface ArticleEntry {
  /** RU-путь статьи; BE-путь получается через beTwin() из lib/seo.ts */
  path: string;
  title: string;
  description: string;
}

export const ARTICLES: ArticleEntry[] = [
  {
    path: '/article',
    title: 'Страна, которая стягивается к столице',
    description: 'Зачем я построил 130-летнюю карту населения Беларуси и что она показала.',
  },
  {
    path: '/article/grid',
    title: 'Страна не вымирает. Она переезжает',
    description: 'Двадцать иллюстраций: километровая сетка населения, 1975–2050.',
  },
];
