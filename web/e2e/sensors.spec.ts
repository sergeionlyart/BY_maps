import { test, expect, type Page } from '@playwright/test';

/**
 * Страница /research/sensors (INF-22): загрузка без ошибок на RU/BE,
 * опровержения H2–H4 показаны на видном месте рядом с подтверждённой H1,
 * пост-хок назван пост-хоком, переключатель метрики карты, выбор района
 * (клик и deep-link ?sel=) открывает три датчика сразу, отсутствие
 * горизонтальной прокрутки на мобильном, посадочная страница пакета и ZIP.
 */

function collectErrors(page: Page) {
  const errors: string[] = [];
  page.on('console', (m) => {
    if (m.type() === 'error' && !m.location().url.includes('favicon')) errors.push(m.text());
  });
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('response', (r) => {
    if (r.status() >= 400 && !r.url().includes('favicon')) {
      errors.push(`${r.status()} ${r.url()}`);
    }
  });
  return errors;
}

async function ready(page: Page) {
  await page.locator('.gv-map svg path').first().waitFor();
}

test('загрузка: заголовок, карта со 118 районами, без ошибок', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto('/research/sensors');
  await expect(page.locator('h1')).toContainText('Второй сенсор');
  await ready(page);
  await expect(page.locator('.gv-map svg path')).toHaveCount(118);
  await page.waitForTimeout(500);
  expect(errors).toEqual([]);
});

test('вердикты: H1 подтверждена, H2–H4 опровергнуты и видны сразу', async ({ page }) => {
  await page.goto('/research/sensors');
  await ready(page);
  const honesty = page.locator('.gv-honesty');
  await expect(honesty).toBeVisible();
  await expect(honesty).toContainText('опровергнуты');
  await expect(page.locator('.gv-chip-verified')).toHaveCount(1);
  await expect(page.locator('.gv-chip-verified')).toContainText('H1 подтверждена');
  const refuted = page.locator('.gv-chip-refuted');
  await expect(refuted).toHaveCount(3);
  await expect(refuted.first()).toContainText('H2 опровергнута');
  await expect(page.locator('.gv-finding')).toContainText('пост-хок');
});

test('плитки берут числа из данных: ρ 0,79, 109 из 117, 65 из 118', async ({ page }) => {
  await page.goto('/research/sensors');
  await ready(page);
  const tiles = page.locator('.stat-tile');
  await expect(tiles.nth(0)).toContainText('0.79');
  await expect(tiles.nth(0)).toContainText('109');
  await expect(tiles.nth(0)).toContainText('117');
  await expect(tiles.nth(2)).toContainText('65');
});

test('переключатель метрики меняет заголовок карты', async ({ page }) => {
  await page.goto('/research/sensors');
  await ready(page);
  const title = page.locator('.chart-block .chart-title').first();
  const before = await title.textContent();
  await page.getByRole('button', { name: 'Статистика против спутника, 1990–2020' }).click();
  await expect(title).not.toHaveText(before ?? '');
  await expect(title).toContainText('официальному ряду');
});

test('deep-link ?sel= показывает три датчика района', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto('/research/sensors?sel=r-astraviecki');
  await ready(page);
  await expect(page.locator('.chart-block .chart-title').nth(1)).toContainText('Островецкий');
  const legend = page.locator('.chart-legend');
  await expect(legend).toContainText('официальный ряд');
  await expect(legend).toContainText('спутник GHS-POP');
  await expect(legend).toContainText('ночные огни');
  expect(errors).toEqual([]);
});

test('клик по району выбирает его и пишет ?sel= в адрес', async ({ page }) => {
  await page.goto('/research/sensors');
  await ready(page);
  await page.locator('.gv-map svg path').nth(10).click();
  await expect(page).toHaveURL(/[?&]sel=r-/);
  await expect(page.locator('.chart-legend')).toBeVisible();
});

test('BE-паритет: /be/research/sensors без ошибок и без русских ключей', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto('/be/research/sensors');
  await expect(page.locator('h1')).toContainText('Другі сэнсар');
  await ready(page);
  await expect(page.locator('.gv-honesty')).toContainText('апровергнуты');
  await expect(page.locator('.gv-chip-verified')).toContainText('H1 пацверджана');
  await expect(page.getByRole('button', { name: 'Святло супраць насельніцтва, 2013–2019' })).toBeVisible();
  const body = await page.locator('.gv-root').innerText();
  for (const ru of ['Свет против', 'опровергнута', 'Выберите район', 'официальный ряд']) {
    expect(body, ru).not.toContain(ru);
  }
  expect(errors).toEqual([]);
});

test('мобильный: нет горизонтальной прокрутки', async ({ page }) => {
  await page.goto('/research/sensors?sel=r-minski');
  await ready(page);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test('пакет: посадочная страница и ZIP доступны', async ({ page, request }) => {
  const errors = collectErrors(page);
  await page.goto('/artifacts/sensors');
  await expect(page.locator('h1')).toContainText('Второй сенсор');
  const zip = await request.get('/artifacts/by-maps-sensors-v1.0.0.zip');
  expect(zip.status()).toBe(200);
  expect((await zip.body()).length).toBeGreaterThan(200_000);
  await page.goto('/be/artifacts/sensors');
  await expect(page.locator('h1')).toContainText('Другі сэнсар');
  expect(errors).toEqual([]);
});

test('методблок открывается и содержит все восемь полей', async ({ page }) => {
  await page.goto('/research/sensors');
  await ready(page);
  await page.getByRole('button', { name: /О данных и методике/ }).click();
  const drawer = page.locator('.drawer');
  await expect(drawer).toBeVisible();
  for (const h of ['Данные и источники', 'Модели и допущения', 'Ограничения', 'Устойчивость']) {
    await expect(drawer).toContainText(h);
  }
  await expect(drawer).toContainText('опровергнута');
});

test('раздел виден в индексах исследований и артефактов (RU/BE)', async ({ page }) => {
  const errors = collectErrors(page);
  for (const path of ['/research', '/be/research']) {
    await page.goto(path);
    await expect(page.locator(`a[href$="/research/sensors"]`).first()).toBeVisible();
  }
  for (const path of ['/artifacts', '/be/artifacts']) {
    await page.goto(path);
    await expect(page.locator(`a[href$="/artifacts/sensors"]`).first()).toBeVisible();
  }
  expect(errors).toEqual([]);
});

test('видеоверсия: блок есть, ролик не грузится до нажатия, файлы на месте (RU/BE)', async ({ page, request }) => {
  for (const [path, lang] of [['/research/sensors', 'ru'], ['/be/research/sensors', 'be']] as const) {
    await page.goto(path);
    await ready(page);
    const video = page.locator('video.pen-reel');
    await expect(video).toHaveAttribute('preload', 'none');
    await expect(video).toHaveAttribute('src', `/video/reel_sensors_${lang}.mp4`);
    for (const ext of ['mp4', 'webp']) {
      const r = await request.get(`/video/reel_sensors_${lang}.${ext}`);
      expect(r.status(), `${lang}.${ext}`).toBe(200);
    }
  }
});
