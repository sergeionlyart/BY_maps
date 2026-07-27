import { test, expect, type Page, type Locator } from '@playwright/test';

/**
 * INF-15 «Полотно»: e2e по разделу «e2e» Приложения А ТЗ + доработка B-7
 * (docs/notes/grid_ux_audit_2026-07-27.md) - открытие RU/BE, скраббинг по
 * узлам данных без падений/зависших запросов, тумблер границ, смена
 * метрики меняет кадр карты, смена сценария/варианта на 2050 меняет кадр И
 * панель, панель без прочерков на всех 16 узлах, deep-link со снапом года,
 * клик по клетке в разные годы даёт разные числа (регресс B-3), режим сети
 * блокирует ползунок и красит хороплет, ▶ проходит до 2050 и останавливается,
 * reduced-motion без автозапуска.
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

function setSliderIndex(slider: Locator, idx: number) {
  return slider.evaluate((el: HTMLInputElement, val: number) => {
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')!.set!;
    setter.call(el, val);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }, idx);
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

test('скраббинг по узлам данных без падений и зависших запросов', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto(PAGE);
  const slider = page.locator('.gv-range');
  await expect(slider).toBeVisible();
  for (const idx of [0, 5, 9, 10, 15, 0]) {
    await setSliderIndex(slider, idx);
    await page.waitForTimeout(80);
  }
  await page.waitForTimeout(500);
  expect(errors).toEqual([]);
});

test('на каждом из 16 узлов ползунка панель показателей заполнена (без прочерков)', async ({ page }) => {
  await page.goto(PAGE);
  const slider = page.locator('.gv-range');
  const values = page.locator('.gv-stat-value');
  for (let idx = 0; idx <= 15; idx++) {
    await setSliderIndex(slider, idx);
    await page.waitForTimeout(70);
    const texts = await values.allInnerTexts();
    expect(texts.length).toBeGreaterThan(0);
    for (const v of texts) expect(v.trim()).not.toBe('—');
  }
});

test('тумблер границ районов переключается', async ({ page }) => {
  await page.goto(PAGE);
  const toggle = page.locator('.gv-toggle input');
  await expect(toggle).not.toBeChecked();
  await toggle.check();
  await expect(toggle).toBeChecked();
  await expect.poll(() => page.url()).toContain('borders=1');
});

test('смена метрики «класс плотности» запрашивает кадр density_* (B-2, B-7.1)', async ({ page }) => {
  await page.goto(`${PAGE}?year=2020`);
  const reqPromise = page.waitForRequest((r) => r.url().includes('/grid_frames/density_2020'));
  await page.getByRole('button', { name: 'Класс плотности' }).click();
  const req = await reqPromise;
  expect(req.url()).toContain('density_2020');
  await expect(page.locator('.gv-legend')).toContainText('густо');
});

test('режим «метры сети на жителя» блокирует ползунок и красит хороплет (B-2)', async ({ page }) => {
  await page.goto(PAGE);
  await page.getByRole('button', { name: 'Метры сети на жителя' }).click();
  await expect(page.locator('.gv-range')).toBeDisabled();
  await expect(page.locator('.gv-legend')).toContainText('OpenStreetMap');
  await expect(page.locator('.gv-network-note')).toBeVisible();
});

test('переключение сценария и варианта на 2050 меняет и кадр, и числа в плитках (B-7.2)', async ({ page }) => {
  await page.goto(`${PAGE}?year=2050`);
  await expect(page.getByRole('button', { name: 'негативный' })).toBeVisible();
  const before = await page.locator('.gv-panel').innerText();
  const reqPromise = page.waitForRequest((r) => r.url().includes('pop_2050_negative'));
  await page.getByRole('button', { name: 'негативный' }).click();
  await expect.poll(() => page.url()).toContain('scenario=negative');
  await reqPromise;
  await page.waitForTimeout(150);
  const after = await page.locator('.gv-panel').innerText();
  expect(after).not.toBe(before);
  await page.getByRole('button', { name: 'Б — пригороды/периферия' }).click();
  await expect.poll(() => page.url()).toContain('variant=B');
});

test('deep-link ?year=1993 снапает к ближайшему узлу данных с подписью (B-1, B-7.4)', async ({ page }) => {
  await page.goto(`${PAGE}?year=1993`);
  await expect(page.locator('.gv-year-label')).toContainText('1995');
  await expect(page.locator('.gv-snap-notice')).toBeVisible();
  const texts = await page.locator('.gv-stat-value').allInnerTexts();
  for (const v of texts) expect(v.trim()).not.toBe('—');
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

test('клик по клетке в 1975 и 2020 даёт разные числа (регресс B-3)', async ({ page, hasTouch }) => {
  await page.goto(`${PAGE}?year=1975`);
  await expect(page.locator('.gv-map canvas')).toBeVisible();
  await page.waitForTimeout(1000); // карта грузит/ресайзит канву асинхронно
  const map = page.locator('.gv-map');
  const box = (await map.boundingBox())!;
  const tapOrClick = (pos: { x: number; y: number }) =>
    hasTouch ? map.tap({ position: pos }) : map.click({ position: pos });

  // Минск (плотнейшая точка страны в любую эпоху) лежит у геометрического
  // центра BOUNDS карты (GridMap.tsx) - но точное пиксельное положение
  // всё же плывёт между окружениями (масштаб канвы, скроллбар), поэтому
  // перебираем несколько точек у центра, пока клик не попадёт в клетку с
  // данными (а не за границу сетки - см. docs/decisions/INF-15.md).
  const candidates = [
    { x: 0.48, y: 0.47 }, { x: 0.5, y: 0.5 }, { x: 0.45, y: 0.5 },
    { x: 0.52, y: 0.45 }, { x: 0.5, y: 0.42 }, { x: 0.55, y: 0.5 },
  ].map((f) => ({ x: box.width * f.x, y: box.height * f.y }));

  // карточка появляется сразу (toBeVisible), но число подгружается
  // асинхронно (fetch .bin) - ждём именно текст «человек в клетке» через
  // автоповторяющийся toContainText, иначе innerText() рискует поймать
  // промежуточное «не подгружено» состояние из handleMapClick.
  let hit: { x: number; y: number } | null = null;
  for (const pos of candidates) {
    await tapOrClick(pos);
    const ok = await expect(page.locator('.gv-cell-card'))
      .toContainText('человек в клетке', { timeout: 1500 }).then(() => true).catch(() => false);
    if (ok) { hit = pos; break; }
  }
  expect(hit, 'ни одна из пробных точек у центра карты не попала в клетку с данными').not.toBeNull();
  const card1975 = await page.locator('.gv-cell-card').innerText();
  expect(card1975).toContain('человек в клетке');

  await setSliderIndex(page.locator('.gv-range'), 9); // индекс 9 = 2020
  await expect(page.locator('.gv-year-label')).toContainText('2020');
  await page.waitForTimeout(300);
  await tapOrClick(hit!);
  await expect(page.locator('.gv-cell-card')).toContainText('человек в клетке', { timeout: 5000 });
  const card2020 = await page.locator('.gv-cell-card').innerText();

  expect(card2020).not.toBe(card1975);
});

test('мобильный экран: слайдер и карта видны', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'мобильный проект');
  await page.goto(PAGE);
  await expect(page.locator('.gv-map')).toBeVisible();
  await expect(page.locator('.gv-range')).toBeVisible();
});

test('▶ автовоспроизведение проходит от узла к узлу и останавливается на 2050 (B-4, B-7.6)', async ({ page }) => {
  test.setTimeout(30_000);
  await page.goto(PAGE);
  await page.getByRole('button', { name: 'воспроизвести' }).click();
  await expect(page.getByRole('button', { name: 'пауза' })).toBeVisible();
  await expect(page.locator('.gv-year-label')).toContainText('2050', { timeout: 20_000 });
  await expect(page.getByRole('button', { name: 'воспроизвести' })).toBeVisible();
});

test('prefers-reduced-motion: ▶ не стартует сам, доступна вручную (B-7.6)', async ({ page }) => {
  const rm = await page.evaluate(() =>
    window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  test.skip(!rm, 'проект reduced-motion');
  await page.goto(`${PAGE}?year=1975`);
  await page.waitForTimeout(1500);
  // год не должен сам измениться без действий пользователя (кнопка ▶ не нажата)
  await expect(page.locator('.gv-year-label')).toContainText('1975');
  await expect(page.getByRole('button', { name: 'воспроизвести' })).toBeVisible();
});
