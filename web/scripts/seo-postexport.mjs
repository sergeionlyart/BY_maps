/**
 * Пост-обработка статического экспорта (out/) под SEO-аудит.
 *
 * Next App Router имеет один корневой layout → `<html lang>` одинаков для всех
 * маршрутов. Для белорусских страниц (out/be/**) переписываем язык документа
 * ru → be, чтобы поисковики/скринридеры получали корректный сигнал языка.
 *
 * Запускается после `next build` (см. package.json "build").
 */
import { readdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const OUT = join(process.cwd(), 'out');
const BE_DIR = join(OUT, 'be');

async function* htmlFiles(dir) {
  let items;
  try {
    items = await readdir(dir, { withFileTypes: true });
  } catch {
    return; // каталога может не быть (напр. be отсутствует) — тихо выходим
  }
  for (const it of items) {
    const p = join(dir, it.name);
    if (it.isDirectory()) yield* htmlFiles(p);
    else if (it.isFile() && it.name.endsWith('.html')) yield p;
  }
}

let count = 0;
for await (const file of htmlFiles(BE_DIR)) {
  const html = await readFile(file, 'utf8');
  if (html.includes('<html lang="ru"')) {
    await writeFile(file, html.replace('<html lang="ru"', '<html lang="be"'), 'utf8');
    count++;
  }
}
// out/be.html — белорусская главная (лежит рядом с be/, не внутри)
const beHome = join(OUT, 'be.html');
try {
  const html = await readFile(beHome, 'utf8');
  if (html.includes('<html lang="ru"')) {
    await writeFile(beHome, html.replace('<html lang="ru"', '<html lang="be"'), 'utf8');
    count++;
  }
} catch {
  /* нет файла — ок */
}

console.log(`[seo-postexport] set <html lang="be"> in ${count} file(s)`);
