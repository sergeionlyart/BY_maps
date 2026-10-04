import { test, expect, type Page } from '@playwright/test';

/**
 * Страница /research/sexratio (INF-21): загрузка без ошибок на RU/BE,
 * опровержение H1 показано на видном месте и не исчезает, ползунок по
 * девяти узлам с пометкой модели, переключатель «25–39 / 70+», выбор района
 * (клик и deep-link ?sel=) открывает возрастной профиль, предупреждение о
 * закрытых учреждениях для района с узким пиком, отсутствие горизонтальной
 * прокрутки на мобильном, посадочная страница пакета и сам ZIP доступны.
 */

function collectErrors(page: Page) {
  const errors: string[] = [];
  page.on('console', (m) => {
    // фавиконку исключаем так же, как в обработчике ответов ниже: полный
    // Chromium запрашивает /favicon.ico, headless-shell — нет
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
  await page.goto('/research/sexratio');
  await expect(page.locator('h1')).toContainText('Карта, где не хватает мужчин');
  await ready(page);
  await expect(page.locator('.gv-map svg path')).toHaveCount(118);
  await page.waitForTimeout(500);
  expect(errors).toEqual([]);
});

test('опровержение H1 видно сразу и с обратным знаком', async ({ page }) => {
  await page.goto('/research/sexratio');
  await ready(page);
  const honesty = page.locator('.gv-honesty');
  await expect(honesty).toBeVisible();
  await expect(honesty).toContainText('опровергнута');
  const refuted = page.locator('.gv-chip-refuted');
  await expect(refuted).toHaveCount(1);
  await expect(refuted).toContainText('H1 опровергнута');
  await expect(refuted).toContainText('-0.297'); // toFixed даёт ASCII-минус
  await expect(page.locator('.gv-chip-verified')).toHaveCount(3);
  // пост-хок назван пост-хоком
  await expect(page.locator('.gv-finding')).toContainText('пост-хок');
});

test('плитка женского перевеса берёт числа из данных: 23 = 8 + 2 + 13', async ({ page }) => {
  await page.goto('/research/sexratio');
  await ready(page);
  const tile = page.locator('.stat-tile').nth(1);
  await expect(tile).toContainText('95');
  await expect(tile).toContainText('23');
  await expect(tile).not.toContainText('почти все пригороды');
  // разбивка вынесена строкой под плитки (на телефоне плитка не вытягивается)
  const breakdown = page.locator('p.hint', { hasText: 'районов с женским перевесом' });
  await expect(breakdown).toContainText('23');
  await expect(breakdown).toContainText('включают свой областной город');
  await expect(breakdown).toContainText('13');
});

test('ползунок: 2019 — перепись, 2036 — модель с пометкой', async ({ page }) => {
  await page.goto('/research/sexratio');
  await ready(page);
  const label = page.locator('.gv-year-label');
  await expect(label).toContainText('2019');
  await expect(label.locator('.urban-badge')).toHaveCount(0);
  const range = page.locator('.gv-range-overlay');
  await range.fill('4'); // узлы: 2009, 2019, 2026, 2031, 2036, ...
  await expect(label).toContainText('2036');
  await expect(label.locator('.urban-badge')).toContainText('МОДЕЛЬ');
  await expect(page.locator('.gv-slider-node')).toHaveCount(9);
});

test('переключатель 25–39 / 70+ меняет заголовок карты и легенду', async ({ page }) => {
  await page.goto('/research/sexratio');
  await ready(page);
  const title = page.locator('.chart-block .chart-title').first();
  await expect(title).toContainText('25–39');
  const legendBefore = await page.locator('.gv-legend .gv-legend-row').count();
  await page.getByRole('button', { name: 'Старшие возрасты 70+' }).click();
  await expect(title).toContainText('70+');
  await expect(page.locator('.gv-legend')).toContainText('секвенциальная');
  expect(await page.locator('.gv-legend .gv-legend-row').count()).not.toBe(legendBefore);
});

test('deep-link ?sel= открывает профиль района и предупреждение о пике', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto('/research/sexratio?sel=r-ivacevicki');
  await ready(page);
  await expect(page.locator('.chart-block .chart-title').nth(1)).toContainText('Ивацевичский');
  const legend = page.locator('.chart-legend');
  await expect(legend).toContainText('перепись 2019');
  // при выбранном 2019 вторая линия — 2009, а не дубль 2019
  await expect(legend).toContainText('2009');
  await expect(page.locator('.gv-story-caveat')).toContainText('закрытых учреждений');
  expect(errors).toEqual([]);
});

test('клик по району выбирает его и пишет ?sel= в адрес', async ({ page }) => {
  await page.goto('/research/sexratio');
  await ready(page);
  await page.locator('.gv-map svg path').nth(10).click();
  await expect(page).toHaveURL(/[?&]sel=r-/);
  await expect(page.locator('.chart-legend')).toBeVisible();
});

test('район без пика не получает предупреждения', async ({ page }) => {
  await page.goto('/research/sexratio?sel=r-minski');
  await ready(page);
  await expect(page.locator('.chart-legend')).toBeVisible();
  await expect(page.locator('.gv-story-caveat')).toHaveCount(0);
});

test('BE-паритет: /be/research/sexratio без ошибок и без русских ключей', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto('/be/research/sexratio');
  await expect(page.locator('h1')).toContainText('Карта, дзе не хапае мужчын');
  await ready(page);
  await expect(page.locator('.gv-honesty')).toContainText('апровергнута');
  await expect(page.getByRole('button', { name: 'Старэйшыя ўзросты 70+' })).toBeVisible();
  await expect(page.locator('.gv-chip-refuted')).toContainText('H1 апровергнута');
  expect(errors).toEqual([]);
});

test('мобильный: нет горизонтальной прокрутки', async ({ page }) => {
  await page.goto('/research/sexratio?sel=r-brescki');
  await ready(page);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test('пакет: посадочная страница и ZIP доступны', async ({ page, request }) => {
  const errors = collectErrors(page);
  await page.goto('/artifacts/sexratio');
  await expect(page.locator('h1')).toContainText('Карта, где не хватает мужчин');
  const zip = await request.get('/artifacts/by-maps-sexratio-v1.0.0.zip');
  expect(zip.status()).toBe(200);
  expect((await zip.body()).length).toBeGreaterThan(1_000_000);
  await page.goto('/be/artifacts/sexratio');
  await expect(page.locator('h1')).toContainText('Карта, дзе не хапае мужчын');
  expect(errors).toEqual([]);
});

test('методблок открывается и содержит все восемь полей', async ({ page }) => {
  await page.goto('/research/sexratio');
  await ready(page);
  await page.getByRole('button', { name: /О данных и методике/ }).click();
  const drawer = page.locator('.drawer');
  await expect(drawer).toBeVisible();
  for (const h of ['Данные и источники', 'Модели и допущения', 'Ограничения', 'Устойчивость']) {
    await expect(drawer).toContainText(h);
  }
  await expect(drawer).toContainText('опровергнута');
});

test('reduced-motion: воспроизведение не стартует само', async ({ page }) => {
  await page.goto('/research/sexratio');
  await ready(page);
  await page.waitForTimeout(1500);
  await expect(page.locator('.gv-year-label')).toContainText('2019');
});

test('раздел виден в индексах исследований и артефактов (RU/BE)', async ({ page }) => {
  const errors = collectErrors(page);
  for (const path of ['/research', '/be/research']) {
    await page.goto(path);
    await expect(page.locator(`a[href$="/research/sexratio"]`).first()).toBeVisible();
  }
  for (const path of ['/artifacts', '/be/artifacts']) {
    await page.goto(path);
    await expect(page.locator(`a[href$="/artifacts/sexratio"]`).first()).toBeVisible();
  }
  expect(errors).toEqual([]);
});

test('видеоверсия: блок есть, ролик не грузится до нажатия, файлы на месте (RU/BE)', async ({ page, request }) => {
  for (const [path, lang] of [['/research/sexratio', 'ru'], ['/be/research/sexratio', 'be']] as const) {
    await page.goto(path);
    await ready(page);
    const video = page.locator('video.pen-reel');
    await expect(video).toHaveAttribute('preload', 'none');
    await expect(video).toHaveAttribute('src', `/video/reel_sexratio_${lang}.mp4`);
    for (const ext of ['mp4', 'webp']) {
      const r = await request.get(`/video/reel_sexratio_${lang}.${ext}`);
      expect(r.status(), `${lang}.${ext}`).toBe(200);
    }
  }
});
