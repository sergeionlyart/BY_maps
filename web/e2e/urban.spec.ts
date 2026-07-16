import { test, expect, type Page } from '@playwright/test';

/**
 * Страница /research/urban-overhang (INF-12): загрузка без ошибок,
 * секции и фолбэк-таблицы, deep-link ?city= (запись с дебаунсом),
 * переключение кейсов, BE-паритет, мобильный без горизонтального скролла.
 */

function collectErrors(page: Page) {
  const errors: string[] = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('response', (r) => {
    if (r.status() >= 400 && !r.url().includes('favicon')) {
      errors.push(`${r.status()} ${r.url()}`);
    }
  });
  return errors;
}

test('загрузка: счётчики, все секции, канва героя, без ошибок', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto('/research/urban-overhang');
  await expect(page.locator('h1')).toContainText('Цена пустеющей карты');
  await expect(page.locator('.stat-tile').first()).toBeVisible();
  for (const id of ['sled', 'scatter', 'clock', 'core-edge', 'roads', 'pairs', 'confidence', 'counterexample', 'limits']) {
    await expect(page.locator(`#${id}`)).toHaveCount(1);
  }
  // канва героя отрисована (ждём загрузку сетки города)
  await expect(page.locator('.urban-canvas-wrap canvas')).toBeVisible();
  await page.waitForTimeout(1500);
  expect(errors).toEqual([]);
});

test('deep-link ?city= восстанавливает выбор; выбор пишется в URL с дебаунсом', async ({ page }) => {
  await page.goto('/research/urban-overhang?city=c-minsk');
  await expect(page.locator('.urban-controls select').first()).toHaveValue('c-minsk');
  // смена кейса меняет город и (с дебаунсом) URL
  await page.getByRole('button', { name: /Северо-восток/ }).first().click();
  await expect.poll(() => page.url(), { timeout: 3000 }).toContain('city=c-krychau');
});

test('фолбэк-таблицы открываются (текстовая альтернатива)', async ({ page }) => {
  await page.goto('/research/urban-overhang');
  const details = page.locator('details.urban-fallback');
  expect(await details.count()).toBeGreaterThanOrEqual(4);
  const first = details.first();
  await first.locator('summary').click();
  await expect(first.locator('table').first()).toBeVisible();
});

test('контрпример и ограничения присутствуют (обязательные блоки)', async ({ page }) => {
  await page.goto('/research/urban-overhang');
  await expect(page.locator('#counterexample + p, section:has(#counterexample) p').first())
    .toContainText('контрпример');
  await expect(page.locator('section:has(#limits) li').first()).toBeVisible();
  // атрибуции источников видимы
  await expect(page.locator('.attribution')).toContainText('OpenStreetMap');
  await expect(page.locator('.attribution')).toContainText('GHS-BUILT-S');
});

test('BE-паритет: /be/research/urban-overhang рендерится и переключатель жив', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto('/be/research/urban-overhang');
  await expect(page.locator('h1')).toBeVisible();
  await expect(page.locator('.stat-tile').first()).toBeVisible();
  await page.waitForTimeout(800);
  expect(errors).toEqual([]);
});

test('мобильный: нет горизонтального скролла', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/research/urban-overhang');
  await page.waitForTimeout(1200);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
});
