import { describe, expect, it } from 'vitest';
import { valueAt, seriesPoints, nearestPoint, formatCompact } from './series';
import {
  colorFor, legendStops, cityColor, cityRadius,
  SEQ, DIV_NEG, DIV_POS, DIV_MID,
} from './scales';
import type { Series } from './types';

const s: Series = {
  '1970': [100_000, 'c'],
  '1979': [90_000, 'c'],
  '1999': [70_000, 'c'],
  '2019': [50_000, 'c'],
};

describe('valueAt', () => {
  it('возвращает точное значение в известный год', () => {
    expect(valueAt(s, 1979)).toEqual({ value: 90_000, interpolated: false });
  });
  it('линейно интерполирует между точками', () => {
    expect(valueAt(s, 1989)).toEqual({ value: 80_000, interpolated: true });
  });
  it('не экстраполирует за пределы серии', () => {
    expect(valueAt(s, 1960)).toBeNull();
    expect(valueAt(s, 2025)).toBeNull();
  });
  it('пустая серия -> null', () => {
    expect(valueAt({}, 2000)).toBeNull();
    expect(valueAt(undefined, 2000)).toBeNull();
  });
});

describe('seriesPoints / nearestPoint', () => {
  it('сортирует по годам и хранит тип', () => {
    const pts = seriesPoints(s);
    expect(pts[0]).toEqual({ year: 1970, value: 100_000, dtype: 'c' });
    expect(pts).toHaveLength(4);
  });
  it('находит ближайшую точку', () => {
    expect(nearestPoint(s, 1985)?.year).toBe(1979);
    expect(nearestPoint(s, 2010)?.year).toBe(2019);
  });
});

describe('шкалы карты', () => {
  it('численность: монотонная секвенциальная шкала', () => {
    const c1 = colorFor('pop', 'raion', 10_000);
    const c2 = colorFor('pop', 'raion', 400_000);
    expect(c1).toBe(SEQ[0]);
    expect(c2).toBe(SEQ[7]);
  });
  it('изменение: убыль красная, рост синий, около нуля нейтрально', () => {
    expect(DIV_NEG).toContain(colorFor('change', 'raion', -0.6));
    expect(colorFor('change', 'raion', 0)).toBe(DIV_MID);
    expect(DIV_POS).toContain(colorFor('change', 'raion', 0.4));
  });
  it('нет данных -> прозрачный', () => {
    expect(colorFor('pop', 'raion', null)).toBe('transparent');
  });
  it('легенда согласована со шкалой', () => {
    expect(legendStops('pop', 'raion')).toHaveLength(SEQ.length);
    expect(legendStops('change', 'raion')).toHaveLength(9);
  });
});

describe('маркеры городов', () => {
  it('радиус монотонно растёт с населением (и падает при убыли)', () => {
    const pops = [10_000, 50_000, 200_000, 1_000_000, 2_000_000];
    const radii = pops.map((p) => cityRadius(p, true));
    for (let i = 1; i < radii.length; i++) expect(radii[i]).toBeGreaterThan(radii[i - 1]);
    expect(cityRadius(null, true)).toBe(0);
    // весь диапазон умещается в разумные пиксели
    expect(radii[0]).toBeGreaterThanOrEqual(1.8);
    expect(radii[radii.length - 1]).toBeLessThan(20);
  });
  it('рост малого города заметен (не съеден минимальным радиусом)', () => {
    // при r ∝ √pop оба значения упирались в пол и город выглядел статичным
    const d = cityRadius(20_000, true) - cityRadius(10_000, true);
    expect(d).toBeGreaterThan(0.5);
  });
  it('красная шкала относительна: пик = ярко-красный, монотонно краснеет', () => {
    const MAX = 2_018_281; // пик Минска
    const rgb = (s: string) => s.match(/\d+/g)!.map(Number);
    // на пике - ярко-красный (канал R доминирует, G/B малы)
    const peak = rgb(cityColor(MAX, MAX, false));
    expect(peak[0]).toBeGreaterThan(200);
    expect(peak[1]).toBeLessThan(40);
    // интенсивность (краснота = R - G) монотонно растёт с населением
    const pops = [5_000, 20_000, 100_000, 500_000, 2_000_000];
    const redness = pops.map((p) => { const [r, g] = rgb(cityColor(p, MAX, false)); return r - g; });
    for (let i = 1; i < redness.length; i++) expect(redness[i]).toBeGreaterThan(redness[i - 1]);
    // убыль возвращает цвет назад (та же функция - симметрично)
    expect(cityColor(80_000, MAX, false)).not.toBe(cityColor(120_000, MAX, false));
    expect(cityColor(0, MAX, false)).toBe('transparent');
  });
  it('тёмная тема использует собственные опорные цвета', () => {
    const MAX = 2_018_281;
    expect(cityColor(MAX, MAX, true)).not.toBe(cityColor(MAX, MAX, false));
  });
});

describe('форматирование', () => {
  it('компактные числа по-русски', () => {
    expect(formatCompact(1_500_000)).toContain('млн');
    expect(formatCompact(45_000)).toContain('тыс.');
  });
});
