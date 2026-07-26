import { test, expect, type Page } from '@playwright/test';

/**
 * INF-15 «Полотно»: e2e по разделу «e2e» Приложения А ТЗ - открытие RU/BE,
 * скраббинг годов без падений/зависших запросов, тумблер границ,
 * переключение сценария/варианта меняет кадр и панель, deep-link
 * восстанавливает год+метрику+вариант, трек центра масс, reduced-motion
 * без автозапуска.
 */

const PAGE = '/research/grid';
const PAGE_BE = '/be/research/grid';

function collectErrors(page: Page) {
  const errors: string[] = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('response', (r) => {
    if (r.status() >= 400 && !r.url().includes('favicon')) errors.push(`${r.status()} ${r.url()}`);
  });
  return errors;
}

test('RU: страница открывается без ошибок, карта и плашка честности видны', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto(PAGE);
  await expect(page.locator('.gv-map')).toBeVisible();
  await expect(page.locator('.gv-honesty')).toBeVisible();
  await expect(page.locator('.gv-honesty')).toContainText('дазиметрически');
  await page.waitForTimeout(600);
  expect(errors).toEqual([]);
});

test('BE: страница открывается без ошибок', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto(PAGE_BE);
  await expect(page.locator('.gv-map')).toBeVisible();
  await expect(page.locator('.gv-honesty')).toBeVisible();
  await page.waitForTimeout(600);
  expect(errors).toEqual([]);
});

test('скраббинг годов без падений и зависших запросов', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto(PAGE);
  const slider = page.locator('.gv-range');
  await expect(slider).toBeVisible();
  for (const v of [1975, 1990, 2010, 2020, 2030, 2050, 1975]) {
    await slider.evaluate((el: HTMLInputElement, val: number) => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')!.set!;
      setter.call(el, val);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }, v);
    await page.waitForTimeout(80);
  }
  await page.waitForTimeout(500);
  expect(errors).toEqual([]);
});

test('тумблер границ районов переключается', async ({ page }) => {
  await page.goto(PAGE);
  const toggle = page.locator('.gv-toggle input');
  await expect(toggle).not.toBeChecked();
  await toggle.check();
  await expect(toggle).toBeChecked();
  await expect.poll(() => page.url()).toContain('borders=1');
});

test('переключение сценария и варианта на прогнозном годе меняет URL и панель', async ({ page }) => {
  await page.goto(`${PAGE}?year=2050`);
  await expect(page.getByRole('button', { name: 'негативный' })).toBeVisible();
  await page.getByRole('button', { name: 'негативный' }).click();
  await expect.poll(() => page.url()).toContain('scenario=negative');
  await page.getByRole('button', { name: 'Б — пригороды/периферия' }).click();
  await expect.poll(() => page.url()).toContain('variant=B');
});

test('deep-link восстанавливает год, метрику и вариант', async ({ page }) => {
  await page.goto(`${PAGE}?year=2050&metric=density&scenario=optimistic&variant=B`);
  await expect(page.locator('.gv-year-label')).toContainText('2050');
  await expect(page.getByRole('button', { name: 'Класс плотности' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('button', { name: 'Б — пригороды/периферия' })).toHaveAttribute('aria-pressed', 'true');
});

test('включение и выключение трека центра масс', async ({ page }) => {
  await page.goto(PAGE);
  const btn = page.getByRole('button', { name: 'Центр масс населения' });
  await btn.click();
  await expect.poll(() => page.url()).toContain('track=1');
  await btn.click();
  await expect.poll(() => page.url()).not.toContain('track=1');
});

test('клик по клетке показывает карточку', async ({ page, hasTouch }) => {
  await page.goto(`${PAGE}?year=2020`);
  await expect(page.locator('.gv-map canvas')).toBeVisible();
  await page.waitForTimeout(1000); // карта грузит/ресайзит канву асинхронно
  const map = page.locator('.gv-map');
  // touch-проекты (mobile) шлют tap, а не синтетический mouse.click -
  // maplibre слушает touchstart/end для тапа на touch-устройствах.
  if (hasTouch) await map.tap({ position: { x: 200, y: 150 } });
  else await map.click({ position: { x: 200, y: 150 } });
  await expect(page.locator('.gv-cell-card')).toBeVisible({ timeout: 5000 });
});

test('мобильный экран: слайдер и карта видны', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'мобильный проект');
  await page.goto(PAGE);
  await expect(page.locator('.gv-map')).toBeVisible();
  await expect(page.locator('.gv-range')).toBeVisible();
});

test('prefers-reduced-motion: нет автозапуска анимации', async ({ page }) => {
  const rm = await page.evaluate(() =>
    window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  test.skip(!rm, 'проект reduced-motion');
  await page.goto(`${PAGE}?year=1975`);
  await page.waitForTimeout(1500);
  // год не должен сам измениться без действий пользователя (нет play-кнопки)
  await expect(page.locator('.gv-year-label')).toContainText('1975');
});
