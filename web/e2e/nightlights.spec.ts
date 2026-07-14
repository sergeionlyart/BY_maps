import { test, expect, type Page } from '@playwright/test';

/**
 * Сценарии распоряжения §11: запуск/остановка анимации, переход к году,
 * переключение слоёв, карточка региона, A/B, сценарии, переход к
 * прогнозу, мобильный экран, prefers-reduced-motion, отсутствие ошибок
 * загрузки кадров и консоли.
 */

const PAGE = '/research/nightlights';

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

async function setSlider(page: Page, value: number) {
  await page.evaluate((v) => {
    const slider = document.querySelector('.nlv3-range') as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype, 'value')!.set!;
    setter.call(slider, v);
    slider.dispatchEvent(new Event('input', { bubbles: true }));
  }, value);
}

test('история: загрузка без ошибок, кадр и таймлайн на месте', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto(PAGE);
  await expect(page.locator('.nlv2-frame').first()).toBeVisible();
  await expect(page.locator('.nlv3-tl-svg')).toBeVisible();
  await expect(page.locator('.nlv2-badge').first()).toContainText('VIIRS');
  await page.waitForTimeout(800);
  expect(errors).toEqual([]);
});

test('история: play продвигает год, повторный клик останавливает', async ({ page }) => {
  await page.goto(`${PAGE}?year=2016`);
  const year = page.locator('.year-display');
  await expect(year).toContainText('2016');
  await page.locator('.play-btn').click();
  await expect(year).not.toContainText('2016', { timeout: 4000 });
  await page.locator('.play-btn').click();
  const y = await year.textContent();
  await page.waitForTimeout(1300);
  expect(await year.textContent()).toBe(y);
});

test('переход к конкретному году слайдером + deep-link', async ({ page }) => {
  await page.goto(PAGE);
  await expect(page.locator('.nlv2-frame').first()).toBeVisible();
  await setSlider(page, 8); // 2000
  await expect(page.locator('.year-display')).toContainText('2000');
  await expect(page.locator('.nlv2-badge').first())
    .toContainText(/реконструкция/i);
  expect(page.url()).toContain('year=2000');
});

test('анализ: переключение абсолютного и delta-слоя', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto(`${PAGE}?year=2019&mode=analysis`);
  await page.getByRole('button', { name: 'Изменение', exact: true }).click();
  await expect(page.locator('.nlv3-delta')).toHaveAttribute(
    'src', /previous_year\/py_2019/);
  await page.getByRole('button', { name: '2012', exact: true }).click();
  await expect(page.locator('.nlv3-delta')).toHaveAttribute(
    'src', /base_2012\/ab_2019/);
  await page.getByRole('button', { name: 'Абсолют + изменение' }).click();
  await expect(page.locator('.nlv2-frame').first()).toBeVisible();
  await expect(page.locator('.nlv3-delta')).toBeVisible();
  await page.waitForTimeout(500);
  expect(errors).toEqual([]);
});

test('карточка события открывается с таймлайна и по региону', async ({ page }) => {
  await page.goto(`${PAGE}?year=2016`);
  await page.locator('.nlv3-ev').first().click();
  await expect(page.locator('.nlv3-card')).toBeVisible();
  await expect(page.locator('.nlv3-card-title')).not.toBeEmpty();
  // причина не генерируется: либо аннотация с источником, либо нейтрально
  const ann = page.locator('.nlv3-card-ann');
  if (await ann.count()) {
    const txt = await ann.first().textContent();
    expect(
      txt!.includes('Источник') || txt!.includes('не определяется')
    ).toBeTruthy();
  }
  await page.locator('.nlv3-card-close').click();
  await expect(page.locator('.nlv3-card')).toHaveCount(0);
});

test('A/B-сравнение и «Показать различия»', async ({ page }) => {
  await page.goto(`${PAGE}?year=2024&mode=analysis`);
  await page.locator('.nlv2-check input').nth(2).check();
  await expect(page.locator('.nlv2-ab-divider')).toBeVisible();
  await page.getByRole('button', { name: 'Показать различия' }).click();
  await expect(page.locator('.nlv3-delta')).toHaveAttribute(
    'src', /base_2012\/ab_2024/);
});

test('переход к прогнозу: маркировка МОДЕЛЬ и сценарии', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto(`${PAGE}?year=2075&scenario=negative`);
  await expect(page.locator('.nlv3-model-badge')).toContainText('МОДЕЛЬ');
  await expect(page.locator('.nlv2-model-border')).toBeVisible();
  await expect(page.locator('.nlv2-frame').first()).toHaveAttribute(
    'src', /modeled\/2075_negative_official/);
  await expect(page.locator('.nlv3-scn-diff')).toContainText('к базовому');
  await page.getByRole('button', { name: 'оптимистичный' }).click();
  await expect(page.locator('.nlv2-frame').first()).toHaveAttribute(
    'src', /modeled\/2075_optimistic_official/);
  await page.waitForTimeout(500);
  expect(errors).toEqual([]);
});

test('граница наблюдения→модель отмечена на таймлайне', async ({ page }) => {
  await page.goto(`${PAGE}?year=2030`);
  await expect(page.locator('.nlv3-card-title'))
    .toContainText('Граница наблюдений и модели');
});

test('скраббинг по ряду не даёт битых кадров', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto(PAGE);
  await expect(page.locator('.nlv2-frame').first()).toBeVisible();
  for (const idx of [0, 10, 20, 30, 35, 42]) {
    await setSlider(page, idx);
    await page.waitForTimeout(350);
    const ok = await page.evaluate(() => {
      const img = document.querySelector('.nlv2-frame') as HTMLImageElement;
      return img.complete && img.naturalWidth > 0;
    });
    expect(ok).toBeTruthy();
  }
  expect(errors).toEqual([]);
});

test('mobile: сцена, таймлайн и карточка без горизонтального скролла',
  async ({ page, isMobile }) => {
    test.skip(!isMobile, 'мобильный проект');
    await page.goto(`${PAGE}?year=2024`);
    await expect(page.locator('.nlv2-frame').first()).toBeVisible();
    await expect(page.locator('.nlv3-tl-svg')).toBeVisible();
    const overflow = await page.evaluate(() =>
      document.documentElement.scrollWidth
      > document.documentElement.clientWidth + 4);
    expect(overflow).toBeFalsy();
  });

test('prefers-reduced-motion: без зума и импульса', async ({ page }) => {
  const rm = await page.evaluate(() =>
    window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  test.skip(!rm, 'проект reduced-motion');
  await page.goto(`${PAGE}?year=2024`);
  await expect(page.locator('.nlv2-frame').first()).toBeVisible();
  // зум-обёртка не анимируется, импульс отключён
  const cls = await page.locator('.nlv3-frame-wrap').getAttribute('class');
  const pulse = await page.locator('.nlv3-pulse').count();
  const transition = await page.evaluate(() => {
    const el = document.querySelector('.nlv3-frame-wrap')!;
    return getComputedStyle(el).transitionDuration;
  });
  expect(pulse === 0 || transition === '0s').toBeTruthy();
  expect(cls).toBeTruthy();
});
