import { test, expect, type Page, type Locator } from '@playwright/test';

/**
 * INF-15 «Полотно» v2 (handoff/09_next_research/INF-15_grid_v2_brief.md):
 * режим «История» (7 шагов, по умолчанию) + режим «Свободно» (инструмент
 * v1). e2e покрывает: переключение режимов, переходы по шагам, deep-link
 * ?story=N, прокрутку внутри шага, а также весь набор v1 (B-1…B-8) на
 * переработанной разметке (слитый слайдер .gv-range-overlay вместо
 * .gv-range, ▶ вынесена из тулбара).
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

/** ?year=... в адресе гарантированно открывает «Свободно» (см. GridView.tsx
 *  логику чтения deep-link) - без этого бэйр-навигация даёт «Историю». */
async function gotoFree(page: Page, qs = 'year=2020') {
  await page.goto(`${PAGE}?${qs}`);
  await expect(page.locator('.gv-range-overlay')).toBeVisible();
}

// ---------------------------------------------------------------------
// Общие открытия
// ---------------------------------------------------------------------

test('RU: страница открывается без ошибок в режиме «История» по умолчанию', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto(PAGE);
  await expect(page.locator('.gv-map')).toBeVisible();
  await expect(page.locator('.gv-honesty')).toBeVisible();
  await expect(page.locator('.gv-honesty')).toContainText('независимый подсчёт');
  await expect(page.locator('.gv-mode-switch button.on')).toContainText('История');
  await expect(page.locator('.gv-story-panel')).toBeVisible();
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

test('BE-паритет: режим «История» переведён, ?story=N deep-link и переключатель работают', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto(`${PAGE_BE}?story=4`);
  await expect(page.locator('.gv-mode-switch button.on')).toContainText('Гісторыя');
  await expect(page.locator('.gv-story-step-no')).toContainText('4');
  // step1.title в grid-story.be.md - "1975 год. Палатно яшчэ амаль суцэльнае."
  // (перевод отдельного контент-файла, не be-dict) - шаг 4 здесь ссылается
  // на реальных, переведённых районов, не на id
  await expect(page.locator('.gv-story-body')).toContainText('Брагінскі');
  await expect(page.locator('.gv-story-body')).not.toContainText('{{');
  await page.locator('.gv-mode-switch button', { hasText: 'Свабодна' }).click();
  await expect(page.locator('.gv-range-overlay')).toBeVisible();
  await expect(page.locator('.gv-story-panel')).toHaveCount(0);
  await page.waitForTimeout(300);
  expect(errors).toEqual([]);
});

// ---------------------------------------------------------------------
// Режим «История»
// ---------------------------------------------------------------------

test('История: шаг 1 показывает заголовок и текст, переход «дальше» работает', async ({ page }) => {
  await page.goto(PAGE);
  await expect(page.locator('.gv-story-step-no')).toContainText('1');
  await expect(page.locator('.gv-story-title')).not.toBeEmpty();
  await expect(page.locator('.gv-story-body')).not.toBeEmpty();
  await page.getByRole('button', { name: /дальше/ }).click();
  await expect(page.locator('.gv-story-step-no')).toContainText('2');
});

test('История: deep-link ?story=N открывает шаг N напрямую', async ({ page }) => {
  await page.goto(`${PAGE}?story=4`);
  await expect(page.locator('.gv-story-step-no')).toContainText('4');
  await expect(page.locator('.gv-story-title')).toContainText('пустот');
});

test('История: шаг 2 - прокрутка запускается сама и останавливается на 2020', async ({ page }) => {
  test.setTimeout(20_000);
  // на проекте reduced-motion прокрутка НЕ должна стартовать сама - это
  // отдельно проверено ниже ("prefers-reduced-motion: прокрутка шага 2
  // не стартует сама"), здесь же ждать автостарта было бы неверно.
  const rm = await page.evaluate(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  test.skip(rm, 'проверяется отдельным тестом на reduced-motion');
  await page.goto(`${PAGE}?story=2`);
  await expect(page.locator('.gv-story-play-row')).toBeVisible();
  // прокрутка стартует сама (500 мс задержка) - проверяем, что играет
  await expect(page.locator('.gv-play-big')).toContainText('❚❚', { timeout: 3000 });
  // и останавливается сама на 2020 (не доходит до 2050)
  await expect(page.locator('.gv-play-big')).toContainText('▶', { timeout: 15_000 });
  await expect(page.locator('.gv-story-play-row .gv-year-label')).toContainText('2020');
});

test('История: шаг 2 - таблица правила пятисот заполнена реальными числами', async ({ page }) => {
  await page.goto(`${PAGE}?story=2`);
  // таблица рендерится только после загрузки контент-файла и grid_story.json
  // (оба - асинхронный fetch) - ждём появления строк, а не читаем сразу
  await expect(page.locator('.gv-story-table tr')).toHaveCount(4);
  const rows = await page.locator('.gv-story-table tr').allInnerTexts();
  expect(rows.length).toBe(4);
  for (const r of rows) {
    expect(r).toMatch(/-?\d+[.,]\d%/); // не прочерк и не пустой токен {{...}}
    expect(r).not.toContain('{{');
  }
});

test('История: шаг 3 показывает оговорку про дазиметрию без сокращений', async ({ page }) => {
  await page.goto(`${PAGE}?story=3`);
  const caveat = await page.locator('.gv-story-caveat').innerText();
  expect(caveat).toContain('заложена в самом методе');
  expect(caveat).toContain('независимому источнику');
  expect(caveat).toContain('не как закон');
});

test('История: шаг 4 - кнопка «показать вторую» подставляет имена без {{токенов}} (регресс by_id)', async ({ page }) => {
  await page.goto(`${PAGE}?story=4`);
  const paras = page.locator('.gv-story-body p');
  const part1 = await paras.last().innerText();
  expect(part1).not.toContain('{{');
  await page.getByRole('button', { name: /вторую/ }).click();
  const part2 = await paras.last().innerText();
  expect(part2).not.toContain('{{');
  expect(part2).toContain('Свислочский');
  expect(part2).not.toBe(part1);
});

test('История: шаг 7 - переключение сценария/варианта и переход в «Свободно»', async ({ page }) => {
  await page.goto(`${PAGE}?story=7`);
  const negBtn = page.locator('.gv-story-step7-controls').getByRole('button', { name: 'негативный' });
  await negBtn.click();
  await expect(negBtn).toHaveAttribute('aria-pressed', 'true');
  await page.locator('.gv-story-freemode-btn').click();
  await expect(page.locator('.gv-mode-switch button.on')).toContainText('Свободно');
  await expect(page.locator('.gv-toolbar')).toBeVisible();
});

test('История: переключатель режима «Свободно» ↔ «История» работает вручную', async ({ page }) => {
  await page.goto(PAGE);
  await page.getByRole('tab', { name: 'Свободно' }).click();
  await expect(page.locator('.gv-toolbar')).toBeVisible();
  await expect(page.locator('.gv-story-panel')).toHaveCount(0);
  await page.getByRole('tab', { name: 'История' }).click();
  await expect(page.locator('.gv-story-panel')).toBeVisible();
});

test('prefers-reduced-motion: прокрутка шага 2 не стартует сама', async ({ page }) => {
  const rm = await page.evaluate(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  test.skip(!rm, 'проект reduced-motion');
  await page.goto(`${PAGE}?story=2`);
  await page.waitForTimeout(1500);
  await expect(page.locator('.gv-play-big')).toContainText('▶');
  await expect(page.locator('.gv-story-play-row .gv-year-label')).toContainText('1975');
});

// ---------------------------------------------------------------------
// Режим «Свободно» (v1, на переработанной разметке)
// ---------------------------------------------------------------------

test('Свободно: скраббинг по узлам данных без падений и зависших запросов', async ({ page }) => {
  const errors = collectErrors(page);
  await gotoFree(page);
  const slider = page.locator('.gv-range-overlay');
  for (const idx of [0, 5, 9, 10, 15, 0]) {
    await setSliderIndex(slider, idx);
    await page.waitForTimeout(80);
  }
  await page.waitForTimeout(500);
  expect(errors).toEqual([]);
});

test('Свободно: на каждом из 16 узлов ползунка панель показателей заполнена (без прочерков)', async ({ page }) => {
  await gotoFree(page);
  const slider = page.locator('.gv-range-overlay');
  const values = page.locator('.gv-stat-value');
  for (let idx = 0; idx <= 15; idx++) {
    await setSliderIndex(slider, idx);
    await page.waitForTimeout(70);
    const texts = await values.allInnerTexts();
    expect(texts.length).toBeGreaterThan(0);
    for (const v of texts) expect(v.trim().charAt(0)).not.toBe('—');
  }
});

test('Свободно: тумблер границ районов переключается', async ({ page }) => {
  await gotoFree(page);
  const toggle = page.locator('.gv-toggle input');
  await expect(toggle).not.toBeChecked();
  await toggle.check();
  await expect(toggle).toBeChecked();
  await expect.poll(() => page.url()).toContain('borders=1');
});

test('Свободно: подсказка под тулбаром меняется по наведённой кнопке (этап 1 v2, §5.3)', async ({ page }) => {
  await gotoFree(page);
  const hint = page.locator('.gv-toolbar-hint');
  const before = await hint.innerText();
  await page.getByRole('button', { name: 'Метры сети на жителя' }).hover();
  await expect(hint).not.toHaveText(before);
});

test('Свободно: смена метрики «класс плотности» запрашивает кадр density_* (B-2, B-7.1)', async ({ page }) => {
  await gotoFree(page);
  const reqPromise = page.waitForRequest((r) => r.url().includes('/grid_frames/density_2020'));
  await page.getByRole('button', { name: 'Класс плотности' }).click();
  const req = await reqPromise;
  expect(req.url()).toContain('density_2020');
  await expect(page.locator('.gv-legend')).toContainText('густо');
});

test('Свободно: режим «метры сети на жителя» блокирует ползунок и красит хороплет (B-2)', async ({ page }) => {
  await gotoFree(page);
  await page.getByRole('button', { name: 'Метры сети на жителя' }).click();
  await expect(page.locator('.gv-range-overlay')).toBeDisabled();
  await expect(page.locator('.gv-legend')).toContainText('OpenStreetMap');
  await expect(page.locator('.gv-network-note')).toBeVisible();
});

test('Свободно: переключение сценария и варианта на 2050 меняет и кадр, и числа в плитках (B-7.2)', async ({ page }) => {
  await gotoFree(page, 'year=2050');
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

test('Свободно: deep-link ?year=1993 снапает к ближайшему узлу данных с подписью (B-1, B-7.4)', async ({ page }) => {
  await gotoFree(page, 'year=1993');
  await expect(page.locator('.gv-year-label')).toContainText('1995');
  await expect(page.locator('.gv-snap-notice')).toBeVisible();
  const texts = await page.locator('.gv-stat-value').allInnerTexts();
  for (const v of texts) expect(v.trim().charAt(0)).not.toBe('—');
});

test('Свободно: deep-link восстанавливает год, метрику и вариант', async ({ page }) => {
  await gotoFree(page, 'year=2050&metric=density&scenario=optimistic&variant=B');
  await expect(page.locator('.gv-year-label')).toContainText('2050');
  await expect(page.getByRole('button', { name: 'Класс плотности' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('button', { name: 'Б — пригороды/периферия' })).toHaveAttribute('aria-pressed', 'true');
});

test('Свободно: включение и выключение трека центра масс', async ({ page }) => {
  await gotoFree(page);
  const btn = page.getByRole('button', { name: 'Центр масс населения' });
  await btn.click();
  await expect.poll(() => page.url()).toContain('track=1');
  await btn.click();
  await expect.poll(() => page.url()).not.toContain('track=1');
});

test('Свободно: клик по клетке в 1975 и 2020 даёт разные числа (регресс B-3)', async ({ page, hasTouch }) => {
  await gotoFree(page, 'year=1975');
  await expect(page.locator('.gv-map canvas')).toBeVisible();
  await page.waitForTimeout(1000); // карта грузит/ресайзит канву асинхронно
  const map = page.locator('.gv-map');
  const box = (await map.boundingBox())!;
  const tapOrClick = (pos: { x: number; y: number }) =>
    hasTouch ? map.tap({ position: pos }) : map.click({ position: pos });

  const candidates = [
    { x: 0.48, y: 0.47 }, { x: 0.5, y: 0.5 }, { x: 0.45, y: 0.5 },
    { x: 0.52, y: 0.45 }, { x: 0.5, y: 0.42 }, { x: 0.55, y: 0.5 },
  ].map((f) => ({ x: box.width * f.x, y: box.height * f.y }));

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

  await setSliderIndex(page.locator('.gv-range-overlay'), 9); // индекс 9 = 2020
  await expect(page.locator('.gv-year-label')).toContainText('2020');
  await page.waitForTimeout(300);
  await tapOrClick(hit!);
  await expect(page.locator('.gv-cell-card')).toContainText('человек в клетке', { timeout: 5000 });
  const card2020 = await page.locator('.gv-cell-card').innerText();

  expect(card2020).not.toBe(card1975);
});

test('мобильный экран: карта и слайдер видны (История и Свободно)', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'мобильный проект');
  await page.goto(PAGE);
  await expect(page.locator('.gv-map')).toBeVisible();
  await expect(page.locator('.gv-story-panel')).toBeVisible();
  await gotoFree(page);
  await expect(page.locator('.gv-range-overlay')).toBeVisible();
});

test('Свободно: ▶ автовоспроизведение проходит от узла к узлу и останавливается на 2050 (B-4, B-7.6)', async ({ page }) => {
  test.setTimeout(30_000);
  await gotoFree(page, 'year=1975');
  await page.getByRole('button', { name: 'воспроизвести' }).click();
  await expect(page.getByRole('button', { name: 'пауза' })).toBeVisible();
  await expect(page.locator('.gv-year-label')).toContainText('2050', { timeout: 20_000 });
  await expect(page.getByRole('button', { name: 'воспроизвести' })).toBeVisible();
});

test('Свободно: prefers-reduced-motion - ▶ не стартует сам, доступна вручную (B-7.6)', async ({ page }) => {
  const rm = await page.evaluate(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  test.skip(!rm, 'проект reduced-motion');
  await gotoFree(page, 'year=1975');
  await page.waitForTimeout(1500);
  await expect(page.locator('.gv-year-label')).toContainText('1975');
  await expect(page.getByRole('button', { name: 'воспроизвести' })).toBeVisible();
});

test('Свободно: тренд-стрелки плиток появляются при движении ползунка (этап 1 v2, §3.3)', async ({ page }) => {
  await gotoFree(page, 'year=1975');
  await expect(page.locator('.gv-trend')).toHaveCount(0); // 1975 - первый узел, стрелок нет
  await setSliderIndex(page.locator('.gv-range-overlay'), 3);
  await page.waitForTimeout(150);
  await expect(page.locator('.gv-trend').first()).toBeVisible();
});

test('Свободно: «Смотреть историю с начала» возвращает в шаг 1', async ({ page }) => {
  await gotoFree(page);
  await page.getByRole('button', { name: /историю с начала/ }).click();
  await expect(page.locator('.gv-story-step-no')).toContainText('1');
});
