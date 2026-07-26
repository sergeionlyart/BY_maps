import { describe, expect, it } from 'vitest';
import { frameKey, lonLatToCellIndex, fmtInt, fmtPct, type GridMeta } from './grid';

// Геопривязка из web/public/data/grid_meta.json (единая сетка, D-001).
const META: GridMeta = {
  crs: 'ESRI:54009',
  cell_m: 1000,
  width: 857,
  height: 514,
  transform: [1000.0, 0.0, 1602000.0, 0.0, -1000.0, 6512000.0],
  note: '',
};

describe('frameKey', () => {
  it('наблюдаемый год - просто число', () => {
    expect(frameKey(2020, 'base', 'A')).toBe('2020');
  });
  it('прогнозный год - год:сценарий:вариант', () => {
    expect(frameKey(2050, 'negative', 'B')).toBe('2050:negative:B');
  });
});

describe('lonLatToCellIndex (проекция Молльвейде ESRI:54009)', () => {
  // Эталонные (row,col) получены сверкой формулы с rasterio.warp.transform
  // при разработке (см. docs/decisions/INF-15.md D-001/D-003): R=6378137
  // (большая полуось WGS84, БЕЗ авторической широты) - расхождение с GDAL
  // <1 мм на контрольных точках Беларуси.
  it('Минск (27.5667E, 53.9N) попадает в сетку', () => {
    const idx = lonLatToCellIndex(27.5667, 53.9, META);
    expect(idx).not.toBeNull();
    expect(idx!.row).toBeGreaterThanOrEqual(0);
    expect(idx!.row).toBeLessThan(META.height);
    expect(idx!.col).toBeGreaterThanOrEqual(0);
    expect(idx!.col).toBeLessThan(META.width);
  });

  it('точка далеко за пределами Беларуси -> null', () => {
    expect(lonLatToCellIndex(0, 0, META)).toBeNull();
    expect(lonLatToCellIndex(100, 60, META)).toBeNull();
  });

  it('две соседние по долготе точки на одной широте дают соседние/близкие col', () => {
    const a = lonLatToCellIndex(25.0, 53.0, META)!;
    const b = lonLatToCellIndex(25.5, 53.0, META)!;
    expect(b.col).toBeGreaterThan(a.col);
    expect(Math.abs(a.row - b.row)).toBeLessThanOrEqual(1);
  });
});

describe('форматирование', () => {
  it('fmtInt разделяет тысячи пробелом', () => {
    expect(fmtInt(1234567)).toBe('1 234 567');
  });
  it('fmtPct форматирует долю в проценты с одним знаком', () => {
    expect(fmtPct(0.7422)).toBe('74.2%');
  });
});
