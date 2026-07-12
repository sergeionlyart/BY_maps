/** Слаг заголовка для якорей оглавления. Сохраняет кириллицу (\p{L}),
 *  прочее — в дефис. Один и тот же слаг используется в Markdown (id) и в
 *  оглавлении (href), чтобы ссылки совпадали. */
export function slugify(s: string): string {
  return s
    .toLowerCase()
    .trim()
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/^-+|-+$/g, '');
}
