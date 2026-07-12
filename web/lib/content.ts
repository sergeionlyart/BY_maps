import fs from 'fs';
import path from 'path';

/** Загрузка контентной страницы на этапе СБОРКИ (серверный код, не клиент).
 *  Метаданные — из первой строки-комментария `<!-- title: … | description: … -->`.
 *  Используется контентными маршрутами (/article, /about, /be/*, …) для
 *  статического рендера — без клиентского fetch (см. T-08). */
export interface Content {
  title: string;
  description: string;
  body: string;
}

export type Lang = 'ru' | 'be';

export function loadContent(lang: Lang, name: string): Content {
  const file = path.join(process.cwd(), 'public', 'content', lang, `${name}.md`);
  const raw = fs.readFileSync(file, 'utf8');
  const m = raw.match(/^<!--\s*title:\s*([\s\S]*?)\s*\|\s*description:\s*([\s\S]*?)\s*-->\s*\n?/);
  if (m) {
    return { title: m[1].trim(), description: m[2].trim(), body: raw.slice(m[0].length) };
  }
  return { title: '', description: '', body: raw };
}

/** Список заголовков h2 для оглавления (тот же слаг, что в Markdown). */
export function headings(body: string): { text: string }[] {
  return body
    .split('\n')
    .map((l) => l.match(/^##\s+(.+)$/))
    .filter((m): m is RegExpMatchArray => !!m)
    .map((m) => ({ text: m[1].trim() }));
}
