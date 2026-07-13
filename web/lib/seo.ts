/** Метаданные автора, канонические URL, hreflang и JSON-LD для поиска
 *  (релиз 1.2 B-6 + SEO-аудит 07.2026). */

export const SITE_URL = 'https://by-population-maps.vercel.app';

export const AUTHOR_NAME = 'Сергей Авдейчик';
export const AUTHOR_URL = `${SITE_URL}/author`;
export const SITE_NAME = 'BY Maps';

/** Для metadata.authors статей и исследований. */
export const authors = [{ name: AUTHOR_NAME, url: AUTHOR_URL }];

/** og:image 1200×630 (public/og.png; относительный путь резолвится metadataBase). */
export const ogImage = { url: '/og.png', width: 1200, height: 630 };

/** База openGraph: Next заменяет вложенный openGraph целиком при переопределении
 *  на странице, поэтому type/siteName нужно повторять — иначе теряются. */
export const ogBase = { type: 'website' as const, siteName: SITE_NAME };

/** Абсолютный URL из пути ('/' → корень со слэшем). */
export function absUrl(path: string): string {
  if (path === '/') return `${SITE_URL}/`;
  return SITE_URL + path;
}

/** RU-путь ↔ BE-путь по правилу маршрутов /be/*. */
export function ruTwin(path: string): string {
  const isBe = path === '/be' || path.startsWith('/be/');
  if (!isBe) return path;
  return path === '/be' ? '/' : path.slice(3);
}
export function beTwin(ruPath: string): string {
  return ruPath === '/' ? '/be' : `/be${ruPath}`;
}

/**
 * metadata.alternates для страницы: canonical на саму себя + взаимный hreflang
 * ru/be + x-default (на RU-версию). Относительные пути резолвятся metadataBase
 * в абсолютные. `path` — собственный путь страницы (RU или BE).
 */
export function altFor(path: string) {
  const ru = ruTwin(path);
  const be = beTwin(ru);
  return {
    canonical: path,
    languages: {
      ru,
      be,
      'x-default': ru,
    },
  };
}

type Lang = 'ru' | 'be';

/** Organization — издатель проекта (общий @id для ссылок publisher). */
export function organizationJsonLd() {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    '@id': `${SITE_URL}/#organization`,
    name: SITE_NAME,
    url: SITE_URL,
    logo: `${SITE_URL}/og.png`,
    founder: { '@type': 'Person', name: AUTHOR_NAME, url: AUTHOR_URL },
    sameAs: ['https://github.com/sergeionlyart/BY_maps'],
  };
}

/** WebSite — для главной (RU и BE). */
export function webSiteJsonLd(lang: Lang) {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    '@id': `${SITE_URL}/#website`,
    name:
      lang === 'be'
        ? 'Насельніцтва Беларусі, 1897–2026'
        : 'Население Беларуси, 1897–2026',
    alternateName: SITE_NAME,
    url: lang === 'be' ? absUrl('/be') : absUrl('/'),
    inLanguage: lang,
    publisher: { '@id': `${SITE_URL}/#organization` },
  };
}

/** JSON-LD Person для /author. */
export const personJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'Person',
  name: AUTHOR_NAME,
  alternateName: 'Sergei Audzeichyk',
  jobTitle: 'AI/ML Engineer',
  description: 'к.т.н., AI/ML-инженер, разработчик AI-продуктов. Автор проекта BY Maps.',
  url: AUTHOR_URL,
  email: 'mailto:chatwebmarket@gmail.com',
  sameAs: [
    'https://www.linkedin.com/in/sergei-audzeichyk',
    'https://github.com/sergeionlyart',
    'https://medium.com/@onlyartpl',
    'https://www.facebook.com/share/1C5Ev1hwPw',
  ],
};

/** Article / ScholarlyArticle — для исследований и большой статьи. */
export function articleJsonLd(opts: {
  title: string;
  description: string;
  path: string;
  lang: Lang;
  scholarly?: boolean;
}) {
  return {
    '@context': 'https://schema.org',
    '@type': opts.scholarly ? 'ScholarlyArticle' : 'Article',
    headline: opts.title,
    description: opts.description,
    inLanguage: opts.lang,
    url: absUrl(opts.path),
    mainEntityOfPage: absUrl(opts.path),
    image: `${SITE_URL}/og.png`,
    author: { '@type': 'Person', name: AUTHOR_NAME, url: AUTHOR_URL },
    publisher: {
      '@type': 'Organization',
      name: SITE_NAME,
      logo: { '@type': 'ImageObject', url: `${SITE_URL}/og.png` },
    },
    isAccessibleForFree: true,
  };
}

/** Dataset — для страниц открытых пакетов-артефактов. */
export function datasetJsonLd(opts: {
  name: string;
  description: string;
  path: string;
  lang: Lang;
  version?: string;
  downloadFile?: string;
}) {
  const distribution = opts.downloadFile
    ? [
        {
          '@type': 'DataDownload',
          encodingFormat: 'application/zip',
          contentUrl: `${SITE_URL}/artifacts/${opts.downloadFile}`,
        },
      ]
    : undefined;
  return {
    '@context': 'https://schema.org',
    '@type': 'Dataset',
    name: opts.name,
    description: opts.description,
    inLanguage: opts.lang,
    url: absUrl(opts.path),
    ...(opts.version ? { version: opts.version } : {}),
    license: 'https://creativecommons.org/licenses/by/4.0/',
    isAccessibleForFree: true,
    creator: { '@type': 'Person', name: AUTHOR_NAME, url: AUTHOR_URL },
    publisher: { '@type': 'Organization', name: SITE_NAME, url: SITE_URL },
    ...(distribution ? { distribution } : {}),
  };
}
