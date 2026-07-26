import { test, expect, type Page } from '@playwright/test';

/**
 * Страница /research/pension (INF-13): загрузка без ошибок на RU/BE,
 * скраббинг слайдера без сбоев и мусорного состояния, три переключателя
 * (сценарий/стартовый ряд/пенсионный возраст) меняют счётчик, deep-link
 * восстанавливает состояние, карточка района (Кореличский — активный
 * crossing_interval, гейт G-3), «найди себя», reduced-motion без автозапуска.
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

test('загрузка: заголовок, счётчик, карта, слайдер, без ошибок', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto('/research/pension');
  await expect(page.locator('h1')).toContainText('Кто кого содержит');
  await expect(page.locator('.pen-counter-value')).toBeVisible();
  await expect(page.locator('.chart-svg-wrap svg').first()).toBeVisible();
  await expect(page.locator('.pyr-slider input')).toBeVisible();
  await page.waitForTimeout(600);
  expect(errors).toEqual([]);
});

test('BE-паритет: /be/research/pension рендерится без ошибок', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto('/be/research/pension');
  await expect(page.locator('h1')).toBeVisible();
  await expect(page.locator('.pen-counter-value')).toBeVisible();
  await page.waitForTimeout(600);
  expect(errors).toEqual([]);
});

// Годы/комбинации ниже подобраны по факту из pension.json (независимо
// пересчитано: 118 районов, порог 1,0, base:official если не указано иное),
// чтобы каждый переключатель гарантированно менял счётчик в отдельности -
// последовательное накопление переключателей на одном годе ненадёжно
// (пороговый счётчик грубый, соседние переключатели иногда не меняют его
// на КОНКРЕТНОМ году даже если легенда карты меняется).
test('переключатель пенсионного возраста меняет счётчик (2056: as_is=5 -> 65/60=1)', async ({ page }) => {
  await page.goto('/research/pension?year=2056');
  await expect(page.locator('.pen-counter-value')).toHaveText('5 из 118');
  await page.getByRole('button', { name: '65 / 60' }).click();
  await expect.poll(() => page.locator('.pen-counter-value').textContent()).toBe('1 из 118');
});

test('переключатель сценария меняет счётчик (2056, as_is: базовый=5 -> негативный=2)', async ({ page }) => {
  await page.goto('/research/pension?year=2056');
  await expect(page.locator('.pen-counter-value')).toHaveText('5 из 118');
  await page.getByRole('button', { name: 'негативный' }).click();
  await expect.poll(() => page.locator('.pen-counter-value').textContent()).toBe('2 из 118');
});

test('переключатель стартового ряда меняет счётчик (2046, as_is: официальный=1 -> скорректированный=2)', async ({ page }) => {
  await page.goto('/research/pension?year=2046');
  await expect(page.locator('.pen-counter-value')).toHaveText('1 из 118');
  await page.getByRole('button', { name: 'скорректированный' }).click();
  await expect.poll(() => page.locator('.pen-counter-value').textContent()).toBe('2 из 118');
});

test('слайдер: скраббинг не роняет страницу, URL пишется с дебаунсом', async ({ page }) => {
  await page.goto('/research/pension?year=2009');
  await expect(page.locator('.pen-counter-value')).toBeVisible();
  const stateCalls = await page.evaluate(async () => {
    let calls = 0;
    const orig = history.replaceState.bind(history);
    history.replaceState = (...a) => { calls += 1; return orig(...a); };
    const slider = document.querySelector('.pyr-slider input') as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype, 'value')!.set!;
    const max = parseInt(slider.max, 10);
    for (let i = 0; i < 80; i++) {
      setter.call(slider, String(i % (max + 1)));
      slider.dispatchEvent(new Event('input', { bubbles: true }));
      await new Promise((r) => setTimeout(r, 5));
    }
    await new Promise((r) => setTimeout(r, 600));
    return calls;
  });
  expect(stateCalls).toBeLessThan(20);
  await expect(page.locator('.pen-counter-value')).toBeVisible();
  expect(page.url()).toContain('year=');
});

test('deep-link восстанавливает год/сценарий/район на перезагрузке', async ({ page }) => {
  await page.goto('/research/pension?year=2046&scenario=negative&policy=65_60&sel=r-karelicki');
  await expect(page.locator('.year-display, .pen-year').first()).toContainText('2046');
  await expect(page.locator('.terr-title')).toContainText('Кореличск');
  await page.reload();
  await expect(page.locator('.terr-title')).toContainText('Кореличск');
  await expect(page.locator('.year-display, .pen-year').first()).toContainText('2046');
});

test('карточка района: клик по строке селектора открывает Кореличский с интервалом перехода', async ({ page }) => {
  await page.goto('/research/pension');
  await page.selectOption('select[aria-label="район"], select[aria-label="раён"]', 'r-karelicki');
  await expect(page.locator('.terr-title')).toContainText('Кореличск');
  // район с активным crossing_interval (гейт G-3): значение — интервал, не год
  const kinds = await page.locator('.pen-crossing-value').evaluateAll(
    (els) => els.map((e) => e.getAttribute('data-kind')));
  expect(kinds).toContain('interval');
});

test('«найди себя»: результат для нескольких годов рождения', async ({ page }) => {
  await page.goto('/research/pension?sel=r-karelicki');
  const input = page.locator('#pen-birth');
  for (const year of [1965, 1990, 2010]) {
    await input.fill(String(year));
    await expect(page.locator('.pen-find-result')).toContainText('Выход на пенсию');
  }
});

test('prefers-reduced-motion: слайдер не проигрывается автоматически', async ({ page }) => {
  const rm = await page.evaluate(() =>
    window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  test.skip(!rm, 'проект reduced-motion');
  await page.goto('/research/pension?year=2009');
  const before = await page.locator('.year-display, .pen-year').first().textContent();
  await page.waitForTimeout(2000);
  const after = await page.locator('.year-display, .pen-year').first().textContent();
  expect(after).toBe(before);
});

test('мобильный: нет горизонтального скролла', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/research/pension');
  await page.waitForTimeout(800);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
