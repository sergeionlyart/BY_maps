import { describe, expect, it } from 'vitest';
import { valueAt, seriesPoints, nearestPoint, formatCompact } from './series';
import { colorFor, legendStops, SEQ, DIV_NEG, DIV_POS, DIV_MID } from './scales';
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

describe('форматирование', () => {
  it('компактные числа по-русски', () => {
    expect(formatCompact(1_500_000)).toContain('млн');
    expect(formatCompact(45_000)).toContain('тыс.');
  });
});
