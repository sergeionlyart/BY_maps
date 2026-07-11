import { describe, expect, it } from 'vitest';
import { raionBreakdown, cityDensity } from './metrics';
import type { DataFile, Territory } from './types';

const city: Territory = {
  id: 'c-x', level: 'city', ru: 'Икс', be: 'Ікс', parent: 'BY-HR',
  area: 50, flags: [], pop: { '2019': [100_000, 'c'] },
};
const raion: Territory = {
  id: 'r-x', level: 'raion', ru: 'Иксский район', be: 'Ікскі', parent: 'BY-HR',
  area: 1050, flags: [], center: ['c-x'],
  pop: { '2019': [150_000, 'c'] },
  popNoCenter: { '2019': [50_000, 'c'] },
};
const data = {
  censusYears: [2019], yearRange: [1897, 2026],
  territories: { 'c-x': city, 'r-x': raion },
  panel: [],
} as unknown as DataFile;

describe('raionBreakdown', () => {
  const b = raionBreakdown(data, raion, 2019)!;
  it('раскладывает население на центр и периферию', () => {
    expect(b.whole).toBe(150_000);
    expect(b.centersPop).toBe(100_000);
    expect(b.noCenter).toBe(50_000);
    expect(b.centersShare).toBeCloseTo(2 / 3);
  });
  it('плотности: центр много плотнее периферии', () => {
    expect(b.densityWhole).toBeCloseTo(150_000 / 1050);
    expect(b.densityNoCenter).toBeCloseTo(50_000 / 1000); // площадь минус город
    expect(b.densityCenters).toBeCloseTo(100_000 / 50);
    expect(b.densityCenters!).toBeGreaterThan(b.densityNoCenter! * 10);
  });
  it('город без площади: сельская плотность считается по полной площади', () => {
    const noAreaCity = { ...city, area: undefined };
    const d2 = { ...data, territories: { 'c-x': noAreaCity, 'r-x': raion } } as DataFile;
    const b2 = raionBreakdown(d2, raion, 2019)!;
    expect(b2.densityNoCenter).toBeCloseTo(50_000 / 1050);
    expect(b2.densityCenters).toBeNull();
  });
  it('не район -> null', () => {
    expect(raionBreakdown(data, city, 2019)).toBeNull();
  });
});

describe('cityDensity', () => {
  it('считает плотность города по площади Wikidata', () => {
    expect(cityDensity(city, 2019)).toBeCloseTo(2000);
  });
  it('без площади -> null', () => {
    expect(cityDensity({ ...city, area: undefined }, 2019)).toBeNull();
  });
});
