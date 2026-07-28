import { test, expect, type Page } from '@playwright/test';

/**
 * INF-15 «Полотно»: иллюстрированная статья /article/grid (+BE-двойник),
 * см. handoff/09_next_research/INF-15_article_site_publish_order.md.
 * Покрывает приёмку раздела 6 распоряжения: открытие RU/BE без ошибок,
 * 20 figure с подписями и alt, первая картинка не lazy, остальные lazy,
 * отсутствие битых изображений, обратные ссылки с /research/grid.
 */

const PAGE = '/article/grid';
const PAGE_BE = '/be/article/grid';
const N_IMAGES = 20;

function collectErrors(page: Page) {
  const errors: string[] = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('response', (r) => {
    if (r.status() >= 400 && !r.url().includes('favicon')) errors.push(`${r.status()} ${r.url()}`);
  });
  return errors;
}

test('RU: страница открывается без ошибок, оглавление и 20 иллюстраций на месте', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto(PAGE);
  await expect(page.locator('h1')).toContainText('Страна не вымирает');
  await expect(page.locator('.content-toc li')).toHaveCount(16);
  const figures = page.locator('.md-figure');
  await expect(figures).toHaveCount(N_IMAGES);
  for (let i = 0; i < N_IMAGES; i++) {
    await expect(figures.nth(i).locator('img')).toHaveAttribute('alt', /.+/);
  }
  expect(errors).toEqual([]);
});

test('BE: страница открывается без ошибок, заголовок и оглавление переведены', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto(PAGE_BE);
  await expect(page.locator('h1')).toContainText('Краіна не вымірае');
  await expect(page.locator('.content-toc li')).toHaveCount(16);
  await expect(page.locator('.md-figure')).toHaveCount(N_IMAGES);
  expect(errors).toEqual([]);
});

test('первая иллюстрация грузится сразу, остальные - lazy, у всех заданы width/height', async ({ page }) => {
  await page.goto(PAGE);
  const imgs = page.locator('.md-figure img');
  await expect(imgs).toHaveCount(N_IMAGES);
  await expect(imgs.first()).not.toHaveAttribute('loading', 'lazy');
  for (let i = 1; i < N_IMAGES; i++) {
    await expect(imgs.nth(i)).toHaveAttribute('loading', 'lazy');
  }
  for (let i = 0; i < N_IMAGES; i++) {
    await expect(imgs.nth(i)).toHaveAttribute('width', '1600');
    await expect(imgs.nth(i)).toHaveAttribute('height', '900');
  }
});

test('подписи рендерятся как figcaption, без литеральных ** или *', async ({ page }) => {
  await page.goto(PAGE);
  const bodyText = await page.locator('.content').innerText();
  expect(bodyText).not.toMatch(/\*\*[^\n]+\*\*/);
  expect(bodyText).not.toMatch(/(?<!\d)\*[^\n*]+\*(?!\d)/);
  const firstCaption = page.locator('.md-figure').first().locator('figcaption');
  await expect(firstCaption).toContainText('Каждая светлая точка');
});

test('ни одно изображение статьи не битое (все ответы 200 image/webp)', async ({ page }) => {
  const badImages: string[] = [];
  page.on('response', (r) => {
    if (r.url().includes('/content/img/grid/') && r.status() !== 200) badImages.push(`${r.status()} ${r.url()}`);
  });
  await page.goto(PAGE);
  // прогоняем все картинки через фактическую загрузку (без lazy-задержки)
  const results = await page.locator('.md-figure img').evaluateAll((els) =>
    Promise.all((els as HTMLImageElement[]).map((el) => new Promise((resolve) => {
      if (el.complete) return resolve({ src: el.src, ok: el.naturalWidth > 0 });
      el.addEventListener('load', () => resolve({ src: el.src, ok: el.naturalWidth > 0 }));
      el.addEventListener('error', () => resolve({ src: el.src, ok: false }));
      el.loading = 'eager';
      // eslint-disable-next-line no-self-assign
      el.src = el.src;
    }))),
  );
  expect(badImages).toEqual([]);
  const broken = (results as { src: string; ok: boolean }[]).filter((r) => !r.ok);
  expect(broken).toEqual([]);
});

test('обратная ссылка ведёт на /research/grid, есть ссылка на пакет артефактов', async ({ page }) => {
  await page.goto(PAGE);
  await expect(page.locator('a[href="/research/grid"]').first()).toBeVisible();
  await expect(page.locator('a[href="/artifacts/grid"]').first()).toBeVisible();
});

test('карточка статьи на /research/grid ведёт на /article/grid первой строкой блока', async ({ page }) => {
  await page.goto('/research/grid?year=2020');
  const next = page.locator('.gv-next');
  await expect(next).toBeVisible();
  await expect(next.locator('a').first()).toHaveAttribute('href', '/article/grid');
});

test('BE: карточка статьи ведёт на /be/article/grid', async ({ page }) => {
  await page.goto('/be/research/grid?year=2020');
  const next = page.locator('.gv-next');
  await expect(next).toBeVisible();
  await expect(next.locator('a').first()).toHaveAttribute('href', '/be/article/grid');
});

test('og:image и hreflang заданы верно', async ({ page }) => {
  await page.goto(PAGE);
  const ogImage = await page.locator('meta[property="og:image"]').getAttribute('content');
  expect(ogImage).toContain('/content/img/grid/cover.webp');
  const hreflangBe = await page.locator('link[rel="alternate"][hreflang="be"]').getAttribute('href');
  expect(hreflangBe).toContain('/be/article/grid');
});

test('мобильный: нет горизонтальной прокрутки', async ({ page }) => {
  await page.goto(PAGE);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
