/** Метаданные автора и og:image для шаринга/поиска (релиз 1.2, B-6). */

export const AUTHOR_NAME = 'Сергей Авдейчик';
export const AUTHOR_URL = 'https://by-population-maps.vercel.app/author';

/** Для metadata.authors статей и исследований. */
export const authors = [{ name: AUTHOR_NAME, url: AUTHOR_URL }];

/** og:image 1200×630 (public/og.png; относительный путь резолвится metadataBase). */
export const ogImage = { url: '/og.png', width: 1200, height: 630 };

/** База openGraph: Next заменяет вложенный openGraph целиком при переопределении
 *  на странице, поэтому type/siteName нужно повторять — иначе теряются. */
export const ogBase = { type: 'website' as const, siteName: 'BY Maps' };

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
