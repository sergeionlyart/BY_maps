import { test, expect, type Page } from '@playwright/test';

/**
 * INF-20 «Шов на карте»: иллюстрированная статья /article/seam (+BE-двойник).
 * Открытие RU/BE без ошибок, все иллюстрации с alt и без битых ссылок,
 * ссылки на страницу исследования и пакет, пункт в меню «Статьи».
 */

const PAGE = '/article/seam';
const PAGE_BE = '/be/article/seam';
const N_IMAGES = 7;
const N_H2 = 10;

function collectErrors(page: Page) {
  const errors: string[] = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('response', (r) => {
    if (r.status() >= 400 && !r.url().includes('favicon')) errors.push(`${r.status()} ${r.url()}`);
  });
  return errors;
}

test('RU: статья открывается без ошибок, оглавление и иллюстрации на месте', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto(PAGE);
  await expect(page.locator('h1')).toContainText('Шов на карте');
  await expect(page.locator('.content-toc-headings li')).toHaveCount(N_H2);
  const figures = page.locator('.md-figure');
  await expect(figures).toHaveCount(N_IMAGES);
  for (let i = 0; i < N_IMAGES; i++) {
    await expect(figures.nth(i).locator('img')).toHaveAttribute('alt', /.+/);
  }
  expect(errors).toEqual([]);
});

test('BE: двойник открывается без ошибок, структура совпадает с RU', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto(PAGE_BE);
  await expect(page.locator('html')).toHaveAttribute('lang', 'be');
  await expect(page.locator('h1')).not.toBeEmpty();
  await expect(page.locator('.content-toc-headings li')).toHaveCount(N_H2);
  await expect(page.locator('.md-figure')).toHaveCount(N_IMAGES);
  expect(errors).toEqual([]);
});

test('все иллюстрации загружаются (natural width > 0)', async ({ page }) => {
  await page.goto(PAGE);
  const imgs = page.locator('.md-figure img');
  await expect(imgs).toHaveCount(N_IMAGES);
  for (let i = 0; i < N_IMAGES; i++) {
    const img = imgs.nth(i);
    await img.scrollIntoViewIfNeeded();
    await expect.poll(async () => img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth)).toBeGreaterThan(0);
  }
});

test('ссылки на исследование и пакет, пункт в меню статей', async ({ page }) => {
  await page.goto(PAGE);
  await expect(page.locator('a[href="/research/seam"]').first()).toBeVisible();
  await expect(page.locator('a[href="/artifacts/seam"]').first()).toBeAttached();
  await expect(page.locator('.content-toc-articles .content-toc-current')).toContainText('Шов на карте');
  await page.goto('/article/grid');
  await expect(page.locator('.content-toc-articles a[href="/article/seam"]')).toBeAttached();
});

test('BE: внутренние ссылки ведут на BE-страницы', async ({ page }) => {
  await page.goto(PAGE_BE);
  await expect(page.locator('a[href="/be/research/seam"]').first()).toBeAttached();
  await expect(page.locator('a[href="/research/seam"]')).toHaveCount(0);
});
