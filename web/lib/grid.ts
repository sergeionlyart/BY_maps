'use client';

/** Данные раздела «Полотно» (INF-15): типы, загрузка, чтение значения
 *  клетки. Источник — web/public/data/grid.json (etl/grid_project.py) +
 *  ленивые бинарные срезы web/public/data/grid_cells/pop_<epoch>.bin
 *  (см. docs/decisions/INF-15.md D-003 за форматом). */

import { useEffect, useState } from 'react';

export type Scenario = 'base' | 'optimistic' | 'negative';
export type Variant = 'A' | 'B';

export const OBSERVED_YEARS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020];
export const FORECAST_YEARS = [2026, 2031, 2036, 2041, 2046, 2050];
export const ALL_YEARS = [...OBSERVED_YEARS, ...FORECAST_YEARS];

export interface GridMeta {
  crs: string;
  cell_m: number;
  width: number;
  height: number;
  transform: number[];
  note: string;
}

export interface CentroidPoint {
  year: number;
  lat: number;
  lon: number;
  err_km: number;
  dtype: string;
}

export interface SettlementComponents {
  n_components: number;
  largest_area_km2?: number;
  largest_pop?: number;
  largest_share_of_pop: number;
  largest_share_of_area: number;
}

export interface TerritoryEntry {
  pop_grid_sum: Record<string, number>;
  area_share_below: { '5': Record<string, number> };
  network_per_capita?: {
    road_km_per_1000: number | null;
    road_km_per_km2: number | null;
    road_km_total: number | null;
  };
}

export interface GridData {
  version: string;
  forecast_version: string;
  grid: GridMeta;
  years: { observed: number[]; forecast: number[] };
  frames: Record<string, string>;
  national: {
    area_share_below: { '5': Record<string, number>; '1': Record<string, number>; '25': Record<string, number> };
    arithmetic_density: Record<string, number>;
    population_weighted_density: Record<string, number>;
    settlement_components: Record<string, SettlementComponents>;
    centroid_track: CentroidPoint[];
  };
  territories: Record<string, TerritoryEntry>;
  validation: {
    g1_reconciliation_summary: {
      n_raions_checked: number;
      n_failed_raions_ever: number;
      per_epoch_fail: Record<string, { failed: number; total: number }>;
      drop_raw_raion_numbers: boolean;
      calibration_applied: string;
    };
    g2_summary: { max_pct_diff: number; n_checks: number };
    g3_nightlights_crosscheck: {
      pct_agree: number;
      threshold_pct: number;
      pass: boolean;
      n_agree: number;
      n_raions: number;
      city_host_raions: { pct_agree: number | null };
      non_host_raions: { pct_agree: number | null };
    };
    g4_g5: {
      g4_polesye_chernobyl: { growth_1975_2020: number; still_monotonic_nondecreasing: boolean };
      g5_centroid_sensitivity: { max_shift_km: number; pass: boolean };
    };
    g6_network: { osm_total_km: number; official_total_km: number; delta_pct: number; passed: boolean } | null;
    c3_correlation: { spearman_rho: number; p_value: number; supports_c3: boolean } | null;
  };
  meta: {
    claims: string[];
    claims_status: Record<string, string>;
    artifact: string;
    honesty: string;
  };
}

export function useGridData(): GridData | null {
  const [data, setData] = useState<GridData | null>(null);
  useEffect(() => {
    let alive = true;
    fetch('/data/grid.json')
      .then((r) => r.json())
      .then((d) => { if (alive) setData(d); })
      .catch(() => { /* сеть недоступна - страница остаётся в состоянии загрузки */ });
    return () => { alive = false; };
  }, []);
  return data;
}

/** Ключ кадра/значения для года: наблюдаемый год - просто число строкой;
 *  прогнозный - "год:сценарий:вариант". */
export function frameKey(year: number, scenario: Scenario, variant: Variant): string {
  return year <= 2020 ? String(year) : `${year}:${scenario}:${variant}`;
}

const CELL_FILES: Record<string, string> = Object.fromEntries([
  ...OBSERVED_YEARS.map((y) => [String(y), `/data/grid_cells/pop_${y}.bin`]),
  ['2050:base:A', '/data/grid_cells/pop_2050_base_A.bin'],
  ['2050:base:B', '/data/grid_cells/pop_2050_base_B.bin'],
]);

const cellCache = new Map<string, Uint16Array>();

/** Ленивая подгрузка бинарного среза клеток на конкретный год/сценарий/
 *  вариант (D-003) - только для year/scenario/variant, для которых есть
 *  файл (10 наблюдаемых + 2050:base:A/Б); для прочих прогнозных
 *  комбинаций точное число клетки не показывается (см. GridView). */
export async function loadCellGrid(key: string): Promise<Uint16Array | null> {
  const url = CELL_FILES[key];
  if (!url) return null;
  const cached = cellCache.get(key);
  if (cached) return cached;
  const buf = await fetch(url).then((r) => (r.ok ? r.arrayBuffer() : Promise.reject()));
  const arr = new Uint16Array(buf);
  cellCache.set(key, arr);
  return arr;
}

export function cellHasBinary(key: string): boolean {
  return key in CELL_FILES;
}

/** lon/lat -> индекс клетки (D-003): репроекция в Молльвейде (ESRI:54009)
 *  средствами сферической формулы Молльвейде (без внешней библиотеки на
 *  клиенте - точность достаточна для попадания в клетку 1 км). */
export function lonLatToCellIndex(
  lon: number, lat: number, meta: GridMeta,
): { row: number; col: number } | null {
  // ESRI:54009 (World Mollweide) в реализации PROJ/GDAL - псевдосферическая
  // проекция с радиусом R = большая полуось WGS84 (6378137 м), БЕЗ перевода
  // в авторическую широту (проверено сверкой с rasterio.warp.transform:
  // с R=6378137 и geodetic-широтой напрямую расхождение <1 мм; с
  // авторической широтой или R=6371007 расхождение ~7-20 км - см.
  // расследование при разработке этапа 6).
  const R = 6378137.0;
  const lonRad = (lon * Math.PI) / 180;
  const latRad = (lat * Math.PI) / 180;
  let theta = latRad;
  for (let i = 0; i < 10; i++) {
    const d = theta + Math.sin(theta) - Math.PI * Math.sin(latRad);
    const dPrime = 1 + Math.cos(theta);
    if (Math.abs(dPrime) < 1e-12) break;
    theta -= d / dPrime;
  }
  const x = ((R * Math.SQRT2 * 2) / Math.PI) * lonRad * Math.cos(theta / 2);
  const y = R * Math.SQRT2 * Math.sin(theta / 2);

  const [a, , c, , e, f] = meta.transform;
  const col = Math.floor((x - c) / a);
  const row = Math.floor((f - y) / Math.abs(e));
  if (col < 0 || col >= meta.width || row < 0 || row >= meta.height) return null;
  return { row, col };
}

export function cellValue(arr: Uint16Array, row: number, col: number, meta: GridMeta): number {
  return arr[row * meta.width + col];
}

export function fmtInt(n: number): string {
  return Math.round(n).toLocaleString('ru-RU').replace(/ /g, ' ');
}

export function fmtPct(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}
