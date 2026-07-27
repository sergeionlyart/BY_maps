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

// На мобильном (<=640px) сценарий/стартовый ряд свёрнуты в аккордеон
// (.pen-settings-acc), а карточка района - шторка, закрытая по умолчанию
// (.pen-card-sheet). На десктопе оба переключателя - no-op (уже открыто).
// В обоих хелперах сперва ждём отрисовки счётчика - до этого данные/контент
// ещё не загружены, а .pen-settings-toggle/.pen-sheet-handle физически нет
// в DOM (isVisible() тихо вернёт false, и переключатель останется скрытым).
async function openSettingsAccordion(page: Page) {
  await page.locator('.pen-counter-value').waitFor();
  const toggle = page.locator('.pen-settings-toggle');
  if (await toggle.isVisible()) await toggle.click();
}
async function openCardSheet(page: Page) {
  await page.locator('.pen-counter-value').waitFor();
  const handle = page.locator('.pen-sheet-handle');
  if (await handle.isVisible()) {
    const sheet = page.locator('.pen-card-sheet');
    if (!(await sheet.evaluate((el) => el.classList.contains('open')))) await handle.click();
  }
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
  await openSettingsAccordion(page);
  await page.getByRole('button', { name: 'негативный' }).click();
  await expect.poll(() => page.locator('.pen-counter-value').textContent()).toBe('2 из 118');
});

test('переключатель стартового ряда меняет счётчик (2046, as_is: официальный=1 -> скорректированный=2)', async ({ page }) => {
  await page.goto('/research/pension?year=2046');
  await expect(page.locator('.pen-counter-value')).toHaveText('1 из 118');
  await openSettingsAccordion(page);
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
  await openCardSheet(page); // мобильный: <select> лежит внутри шторки, .controls скрыт пока она свёрнута
  await page.selectOption('select[aria-label="район"], select[aria-label="раён"]', 'r-karelicki');
  await expect(page.locator('.terr-title')).toContainText('Кореличск');
  // район с активным crossing_interval (гейт G-3): значение — интервал, не год
  const kinds = await page.locator('.pen-crossing-value').evaluateAll(
    (els) => els.map((e) => e.getAttribute('data-kind')));
  expect(kinds).toContain('interval');
});

test('«найди себя»: результат для нескольких годов рождения (слой «Просто»)', async ({ page }) => {
  await page.goto('/research/pension?sel=r-karelicki');
  const input = page.locator('#pen-birth');
  for (const year of [1965, 1990, 2010]) {
    await input.fill(String(year));
    await expect(page.locator('.pen-find-result')).toContainText('выходите на пенсию');
  }
});

test('«найди себя»: результат в слое «Профессионально»', async ({ page }) => {
  await page.goto('/research/pension?sel=r-karelicki&copy=pro');
  await page.locator('#pen-birth').fill('1990');
  await expect(page.locator('.pen-find-result')).toContainText('Выход на пенсию:');
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

// ---------------------------------------------------------------
// INF-13 UX (handoff/10_pension_ux_copy): два слоя текста, новая
// компоновка, мобильные аккордеон/шторка - раздел 10 ТЗ (чеклист приёмки).
// ---------------------------------------------------------------

test('слой «Просто» включён по умолчанию, переключатель меняет URL и текст', async ({ page }) => {
  await page.goto('/research/pension');
  await expect(page.getByRole('button', { name: 'Просто' })).toHaveAttribute('aria-pressed', 'true');
  expect(page.url()).not.toContain('copy=');
  await page.getByRole('button', { name: 'Профессионально' }).click();
  await expect.poll(() => page.url()).toContain('copy=pro');
  await expect(page.locator('h1')).toContainText('коэффициент поддержки');
  await page.reload();
  await expect(page.getByRole('button', { name: 'Профессионально' })).toHaveAttribute('aria-pressed', 'true');
});

test('слой «Просто»: аббревиатуры SR и CG не встречаются на странице', async ({ page }) => {
  await page.goto('/research/pension?sel=r-karelicki');
  await page.locator('#pen-birth').fill('1990');
  const text = await page.locator('.pen-view').innerText();
  expect(text).not.toMatch(/\bSR\b/);
  expect(text).not.toMatch(/\bCG\b/);
});

test('слой «Просто»: денежный блок содержит оговорку «не бюджет района»', async ({ page }) => {
  await page.goto('/research/pension?sel=r-karelicki');
  await expect(page.locator('.prob-panel')).toContainText('не бюджет района');
});

test('раздел 9 ТЗ: все семь оговорок присутствуют в слое «Просто»', async ({ page }) => {
  await page.goto('/research/pension?sel=r-karelicki');
  await openCardSheet(page); // мобильный: пояснение к CG и год-перехода лежат внутри свёрнутой шторки
  const text = await page.locator('.pen-view').innerText();
  expect(text).toContain('не бюджет района'); // п.1
  expect(text).toContain('не является независимым подтверждением'); // п.2
  expect(text).toMatch(/промежуток.{0,20}а не дата/); // п.3
  expect(text).toContain('измеренные, а не рассчитанные'); // п.4 (измерено/рассчитано)
  expect(text).toContain('Кореличский'); // п.5а
  expect(text).toContain('сокращается почти на четверть'); // п.5б (абсолютный разброс)
  expect(text).toContain('27 районов из 93'); // п.5в
  // п.6: фраза «...решает проблему» разрешена только внутри отказа от неё
  // (raзд. 7.10: «Формулировка «повышение возраста решает проблему» из
  // этого не следует, и мы её не используем.») - как голое утверждение
  // (без отрицания в пределах ~60 символов после) быть не должно.
  const solvesIdx = text.indexOf('решает проблему');
  if (solvesIdx >= 0) {
    const after = text.slice(solvesIdx, solvesIdx + 80);
    expect(after).toMatch(/не следует|не используем/);
  }
  expect(text.toLowerCase()).not.toContain('вымира'); // п.7 (нейтральный тон)
  expect(text.toLowerCase()).not.toContain('катастроф');
});

test('карта идёт до графика по стране; строка времени с ▶ - сразу под картой', async ({ page }) => {
  // порядок блоков проверяем по DOM (compareDocumentPosition), а не по
  // экранным Y-координатам: .pen-timebar - position:sticky и на мобильном
  // визуально «прилипает» к низу вьюпорта уже при scrollY=0 (ожидаемо для
  // sticky-bottom без верхней границы прилипания в длинном контейнере),
  // так что bounding-box Y не отражает порядок в разметке.
  await page.goto('/research/pension');
  await page.getByText('Вся страна:').waitFor(); // дождаться полной загрузки данных/контента, не только каркаса
  const order = await page.evaluate(() => {
    const map = document.querySelector('.pen-map-block')!;
    const timebar = document.querySelector('.pen-timebar')!;
    const chartCountry = [...document.querySelectorAll('.chart-title')]
      .find((el) => el.textContent?.includes('Вся страна:'))!.closest('.chart-block')!;
    const before = (a: Element, b: Element) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
    return { mapBeforeTimebar: before(map, timebar), timebarBeforeChart: before(timebar, chartCountry) };
  });
  expect(order.mapBeforeTimebar).toBe(true);
  expect(order.timebarBeforeChart).toBe(true);
  await expect(page.locator('.pen-timebar').getByRole('button', { name: /Посмотреть, как менялось/ })).toBeVisible();
});

test('легенда: словесные подписи на краях и у критической отметки (слой «Просто»)', async ({ page }) => {
  await page.goto('/research/pension');
  const legend = await page.locator('.pen-legend').innerText();
  expect(legend).toContain('меньше одного работающего на пожилого');
  expect(legend).toContain('критическая отметка');
  expect(legend).toContain('запас есть');
});

test('«как читать эту карту» показывается новому посетителю и сворачивается после клика по району', async ({ page }) => {
  await page.goto('/research/pension');
  await expect(page.locator('.pen-howto-steps')).toBeVisible();
  await page.locator('.chart-svg-wrap svg path').first().click();
  await expect(page.locator('.pen-howto-steps')).toBeHidden();
});

test('мобильный: настройки в аккордеоне закрыты по умолчанию, пенсионный возраст - снаружи', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/research/pension');
  await expect(page.locator('.pen-settings-toggle')).toBeVisible();
  await expect(page.locator('.pen-policy-primary .control-label')).toHaveText('Если поднять пенсионный возраст');
  await expect(page.getByRole('button', { name: 'негативный' })).toBeHidden();
  await page.locator('.pen-settings-toggle').click();
  await expect(page.getByRole('button', { name: 'негативный' })).toBeVisible();
});

test('мобильный: карточка района открывается шторкой по тапу на район', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/research/pension');
  await page.locator('.chart-svg-wrap svg path').first().click();
  const sheet = page.locator('.pen-card-sheet');
  await expect(sheet).toHaveClass(/open/);
  await expect(page.locator('.pen-sheet-body')).toBeVisible();
  await page.locator('.pen-sheet-handle').click();
  await expect(sheet).not.toHaveClass(/open/);
});

test('мобильный: кнопка ▶ находится в липкой панели времени вместе со слайдером', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/research/pension');
  const timebar = page.locator('.pen-timebar');
  await expect(timebar).toHaveCSS('position', 'sticky');
  await expect(timebar.getByRole('button', { name: /Посмотреть, как менялось/ })).toBeVisible();
  await expect(timebar.locator('.pyr-slider input')).toBeVisible();
});

test('prefers-reduced-motion: кнопка ▶ остаётся рабочей, показана подпись об отключённой анимации', async ({ page }) => {
  const rm = await page.evaluate(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  test.skip(!rm, 'проект reduced-motion');
  await page.goto('/research/pension?year=2009');
  const btn = page.getByRole('button', { name: /Посмотреть, как менялось/ });
  await expect(btn).toBeEnabled();
  await expect(page.locator('.pen-reduced-motion-note')).toBeVisible();
});

test('BE: слой «Просто» переведён, тот же переключатель работает', async ({ page }) => {
  await page.goto('/be/research/pension');
  await expect(page.locator('h1')).toContainText('Хто каго ўтрымлівае');
  await expect(page.getByRole('button', { name: 'Проста' })).toHaveAttribute('aria-pressed', 'true');
});

test('архив: скачивание не изменилось (кнопка ведёт на тот же ZIP)', async ({ page }) => {
  await page.goto('/research/pension');
  await expect(page.getByRole('link', { name: /Скачать данные и код/ })).toHaveAttribute('href', '/artifacts/by-maps-pension-v1.0.0.zip');
});
