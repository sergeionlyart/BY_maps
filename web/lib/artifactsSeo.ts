/** Предметные (поисковые) title/description и Dataset JSON-LD для страниц
 *  пакетов-артефактов (SEO-аудит, задачи 7 и 8). Ключ — роут-слаг /artifacts/<slug>. */
import { datasetJsonLd } from '@/lib/seo';

type Lang = 'ru' | 'be';

interface ArtifactSeo {
  ru: string; // предметная тема, RU
  be: string; // предметная тема, BE
  file: string; // последний zip (public/artifacts/<file>)
  version: string;
}

export const ARTIFACT_SEO: Record<string, ArtifactSeo> = {
  zipf: { ru: 'Иерархия городов и закон Ципфа в Беларуси', be: 'Іерархія гарадоў і закон Цыпфа ў Беларусі', file: 'by-maps-zipf-v1.0.0.zip', version: '1.0.0' },
  aging: { ru: 'Старение районов Беларуси', be: 'Старэнне раёнаў Беларусі', file: 'by-maps-aging-v1.0.3.zip', version: '1.0.3' },
  wages: { ru: 'Зарплата и динамика населения районов Беларуси', be: 'Зарплата і дынаміка насельніцтва раёнаў Беларусі', file: 'by-maps-wages-v1.0.0.zip', version: '1.0.0' },
  access: { ru: 'Транспортная доступность и «тень Минска»', be: 'Транспартная даступнасць і «цень Мінска»', file: 'by-maps-access-v1.0.0.zip', version: '1.0.0' },
  migration: { ru: 'Внутренняя и внешняя миграция в Беларуси', be: 'Унутраная і знешняя міграцыя ў Беларусі', file: 'by-maps-migration-v1.0.0.zip', version: '1.0.0' },
  monotowns: { ru: 'Моногорода Беларуси и градообразующие предприятия', be: 'Монагарады Беларусі і горадаўтваральныя прадпрыемствы', file: 'by-maps-monotowns-v1.0.0.zip', version: '1.0.0' },
  chernobyl: { ru: 'Чернобыльский след в демографии районов Беларуси', be: 'Чарнобыльскі след у дэмаграфіі раёнаў Беларусі', file: 'by-maps-chernobyl-v1.0.0.zip', version: '1.0.0' },
  nightlights: { ru: 'Ночные огни против официальной статистики населения', be: 'Начныя агні супраць афіцыйнай статыстыкі насельніцтва', file: 'by-maps-nightlights-v1.0.0.zip', version: '1.0.0' },
  shocks: { ru: 'Демографические шоки XX века в Беларуси', be: 'Дэмаграфічныя шокі XX стагоддзя ў Беларусі', file: 'by-maps-shocks-v1.0.0.zip', version: '1.0.0' },
  ml: { ru: 'ML-challenger структурной модели районов Беларуси', be: 'ML-challenger структурнай мадэлі раёнаў Беларусі', file: 'by-maps-mlchallenger-v1.0.0.zip', version: '1.0.0' },
  forecast: { ru: 'Прогноз населения Беларуси 2026–2075', be: 'Прагноз насельніцтва Беларусі 2026–2075', file: 'by-maps-forecast-v1.3.0.zip', version: '1.3.0' },
};

/** Предметные title/description для metadata (задача 8). */
export function artifactMeta(slug: string, lang: Lang) {
  const a = ARTIFACT_SEO[slug];
  const subject = lang === 'be' ? a.be : a.ru;
  if (lang === 'be') {
    return {
      title: `${subject}: даныя, методыка і правяральны пакет — BY Maps`,
      description: `Адкрыты ўзнаўляльны пакет даследавання «${subject}»: сырыя і ачышчаныя даныя, код, дапушчэнні і кантрольныя сумы sha256. Спампаваць, перазабраць і аспрэчыць кожны лік.`,
    };
  }
  return {
    title: `${subject}: данные, методика и проверяемый пакет — BY Maps`,
    description: `Открытый воспроизводимый пакет исследования «${subject}»: сырые и очищенные данные, код, допущения и контрольные суммы sha256. Скачать, пересобрать и оспорить каждое число.`,
  };
}

/** Dataset JSON-LD страницы пакета (задача 7). */
export function artifactDataset(slug: string, lang: Lang, path: string) {
  const a = ARTIFACT_SEO[slug];
  const meta = artifactMeta(slug, lang);
  return datasetJsonLd({
    name: lang === 'be' ? a.be : a.ru,
    description: meta.description,
    path,
    lang,
    version: a.version,
    downloadFile: a.file,
  });
}
