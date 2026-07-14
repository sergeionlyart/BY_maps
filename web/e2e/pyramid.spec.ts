import { test, expect, type Page } from '@playwright/test';

/**
 * Страница /pyramid (INF-11): загрузка без ошибок, deep-link,
 * «найди себя» с границами, сценарии и призраки после 2026,
 * аннотации, «рассказ», BE-паритет, мобильный без горизонтального
 * скролла (приёмка §6.3–6.4).
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

test('загрузка: пирамида, слайдер, тип кадра, без ошибок', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto('/pyramid');
  await expect(page.locator('.pyr-row')).toHaveCount(17);
  await expect(page.locator('.pyr-year')).toContainText('1959');
  await expect(page.locator('.pyr-badge').first()).toContainText('перепись');
  await expect(page.locator('.pyr-slider input')).toBeVisible();
  await page.waitForTimeout(600);
  expect(errors).toEqual([]);
});

test('deep-link ?born=&year=&scenario= восстанавливает состояние', async ({ page }) => {
  await page.goto('/pyramid?born=1985&year=2050&scenario=negative');
  await expect(page.locator('.pyr-year')).toContainText('2050');
  await expect(page.locator('.pyr-find-label')).toContainText('вам 65');
  await expect(page.locator('.pyr-find-label')).toContainText('негативный');
  await expect(page.locator('.pyr-row-cohort')).toHaveCount(1);
});

test('«найди себя» на границах: до рождения и 2075', async ({ page }) => {
  await page.goto('/pyramid?year=1959');
  await page.locator('#pyr-born').fill('1985');
  await expect(page.locator('.pyr-notyet')).toBeVisible();
  await expect(page.locator('.pyr-row-cohort')).toHaveCount(0);
  // 1890-е: когорта в 80+ пока жива по данным, в 1980-х уже за верхом
  await page.locator('#pyr-born').fill('1890');
  await expect(page.locator('.pyr-row-cohort')).toHaveCount(1);
  await page.goto('/pyramid?year=2075&born=1985');
  await expect(page.locator('.pyr-year')).toContainText('2075');
  await expect(page.locator('.pyr-find-label')).toContainText('вам 90');
});

test('после 2026: сценарии, стартовый ряд, призраки', async ({ page }) => {
  await page.goto('/pyramid?year=2075');
  await expect(page.locator('.pyr-ghost').first()).toBeVisible();
  expect(await page.locator('.pyr-ghost').count()).toBe(17 * 2 * 2);
  await page.getByRole('button', { name: 'негативный' }).click();
  expect(page.url()).toContain('scenario=negative');
  await page.getByRole('button', { name: 'скорректированный' }).click();
  expect(page.url()).toContain('jumpoff=adjusted');
  await expect(page.locator('.pyr-badge').first()).toContainText('модель');
  // на истории переключателей нет
  await page.goto('/pyramid?year=2009');
  await expect(page.getByRole('button', { name: 'негативный' })).toHaveCount(0);
});

test('аннотации всплывают на якорных годах и закрываются', async ({ page }) => {
  await page.goto('/pyramid?year=2009');
  await expect(page.locator('.pyr-ann-title')).toContainText('Шрам войны');
  // на 2009 две аннотации: закрытие первой показывает вторую
  await page.locator('.pyr-ann-card .nlv3-card-close').click();
  await expect(page.locator('.pyr-ann-title')).toContainText('Эхо войны');
  await page.goto('/pyramid?year=2075');
  await expect(page.locator('.pyr-ann-title')).toContainText('Пирамида или гриб');
});

test('«рассказ» продвигает год', async ({ page }) => {
  await page.goto('/pyramid?year=2060');
  await page.locator('.play-btn').click();
  await expect(page.locator('.pyr-year')).not.toContainText('2060',
    { timeout: 5000 });
  await page.locator('.play-btn').click();
  const y = await page.locator('.pyr-year').textContent();
  await page.waitForTimeout(1200);
  expect(await page.locator('.pyr-year').textContent()).toBe(y);
});

test('тултип бара: численности и тип кадра', async ({ page }) => {
  await page.goto('/pyramid?year=2019');
  await page.locator('.pyr-row').nth(0).click();    // верхний ряд = 80+
  await expect(page.locator('.pyr-tip')).toContainText('80+');
  await expect(page.locator('.pyr-tip')).toContainText('f/m');
  await expect(page.locator('.pyr-tip')).toContainText('перепись');
});

test('BE-паритет: /be/pyramid', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto('/be/pyramid?year=2009&born=1985');
  await expect(page.locator('h1')).toContainText('Піраміда');
  await expect(page.locator('.pyr-ann-title')).toContainText('Шрам вайны');
  await expect(page.locator('.pyr-find-label')).toContainText('кагорта');
  await page.waitForTimeout(500);
  expect(errors).toEqual([]);
});

test('mobile: без горизонтального скролла, слайдер снизу',
  async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/pyramid?year=2026');
    await expect(page.locator('.pyr-row')).toHaveCount(17);
    const hscroll = await page.evaluate(
      () => document.body.scrollWidth > window.innerWidth);
    expect(hscroll).toBe(false);
    const pos = await page.evaluate(() => getComputedStyle(
      document.querySelector('.pyr-slider')!).position);
    expect(pos).toBe('sticky');
  });
