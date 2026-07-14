'use client';

/** Данные раздела «Пирамида» (INF-11): типы, загрузка, разрешение
 *  кадров. Источник — web/public/data/pyramids.json (etl/pyramids.py):
 *  128 серий, каждая с типом достоверности. */

import { useEffect, useState } from 'react';

export type FrameType = 'census' | 'estimate' | 'interpolated' | 'model';
export type Scenario = 'base' | 'optimistic' | 'negative';
export type Jumpoff = 'official' | 'adjusted';

export interface PyramidFrame {
  type: FrameType;
  source: string;
  m: number[];
  f: number[];
  unknown?: number;
}

export interface PyramidAnnotation {
  id: string;
  year: number;
  cohort?: [number, number];
  groups?: string[];
  title: string;
}

export interface PyramidData {
  version: string;
  age_groups: string[];
  annotations: PyramidAnnotation[];
  series: Record<string, PyramidFrame>;
}

export function usePyramidData(): PyramidData | null {
  const [data, setData] = useState<PyramidData | null>(null);
  useEffect(() => {
    let alive = true;
    fetch('/data/pyramids.json')
      .then((r) => r.json())
      .then((d) => { if (alive) setData(d); });
    return () => { alive = false; };
  }, []);
  return data;
}

/** Остановки слайдера: 1959–2026 погодно, дальше модельная сетка. */
export function stopsOf(data: PyramidData): number[] {
  const hist: number[] = [];
  for (let y = 1959; y <= 2026; y++) {
    if (data.series[String(y)]) hist.push(y);
  }
  const future: number[] = [];
  for (let y = 2030; y <= 2075; y += 5) future.push(y);
  return [...hist, ...future];
}

export const CENSUS_YEARS = [1959, 1970, 1979, 1989, 2009, 2019];

export function frameKey(year: number, scn: Scenario, jo: Jumpoff): string {
  if (year <= 2026) return String(year);
  return jo === 'official' ? `${year}:${scn}` : `${year}:${scn}:adjusted`;
}

export function frameOf(data: PyramidData, year: number, scn: Scenario,
  jo: Jumpoff): PyramidFrame | null {
  return data.series[frameKey(year, scn, jo)] ?? null;
}

export const TYPE_RU: Record<FrameType, string> = {
  census: 'перепись',
  estimate: 'оценка Белстата',
  interpolated: 'интерполяция',
  model: 'модель',
};

export function fmtK(n: number): string {
  return `${Math.round(n / 1000)}`;
}

export function fmt(n: number): string {
  return n.toLocaleString('ru-RU').replace(/ /g, ' ');
}

/** Индекс группы для когорты born в год year (или null, если когорта
 *  ещё не родилась / вне ряда). */
export function cohortGroup(born: number, year: number): number | null {
  const age = year - born;
  if (age < 0 || age > 120) return null;
  return Math.min(Math.floor(age / 5), 16);
}
