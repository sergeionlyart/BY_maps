import type { MetadataRoute } from 'next';
import { RESEARCH } from '@/lib/research';
import { absUrl, beTwin } from '@/lib/seo';

export const dynamic = 'force-static';

/** Роут-слаги страниц пакетов-артефактов (совпадают с app/artifacts/<slug>). */
const ARTIFACT_SLUGS = [
  'zipf', 'aging', 'wages', 'access', 'migration',
  'monotowns', 'chernobyl', 'nightlights', 'shocks', 'ml', 'forecast', 'pyramid',
  'urban-overhang',
];

/** Канонические RU-пути всех индексируемых страниц (BE-двойник добавляется автоматически). */
function ruPaths(): string[] {
  const paths = [
    '/',
    '/map',
    '/research',
    ...RESEARCH.map((r) => `/research/${r.slug}`),
    '/artifacts',
    ...ARTIFACT_SLUGS.map((s) => `/artifacts/${s}`),
    '/pyramid',
    '/methodology',
    '/article',
    '/about',
    '/goals',
    '/author',
  ];
  return paths;
}

/** /sitemap.xml — генерируется на сборке (output: export отдаёт статический файл).
 *  Каждый URL несёт взаимные hreflang-альтернаты ru/be. */
export default function sitemap(): MetadataRoute.Sitemap {
  const entries: MetadataRoute.Sitemap = [];
  for (const ru of ruPaths()) {
    const be = beTwin(ru);
    const languages = { ru: absUrl(ru), be: absUrl(be) };
    entries.push({ url: absUrl(ru), alternates: { languages } });
    entries.push({ url: absUrl(be), alternates: { languages } });
  }
  return entries;
}
