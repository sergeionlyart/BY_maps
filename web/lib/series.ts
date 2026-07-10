import type { Series, DType } from './types';

export interface Point {
  year: number;
  value: number;
  dtype: DType;
}

export function seriesPoints(s: Series | undefined): Point[] {
  if (!s) return [];
  return Object.entries(s)
    .map(([y, [v, t]]) => ({ year: +y, value: v, dtype: t }))
    .sort((a, b) => a.year - b.year);
}

/** Значение на произвольный год: точное или линейная интерполяция между
 *  соседними известными точками. Вне диапазона - null (не экстраполируем). */
export function valueAt(s: Series | undefined, year: number): { value: number; interpolated: boolean } | null {
  const pts = seriesPoints(s);
  if (!pts.length) return null;
  if (year < pts[0].year || year > pts[pts.length - 1].year) return null;
  let lo = pts[0];
  for (const p of pts) {
    if (p.year === year) return { value: p.value, interpolated: false };
    if (p.year < year) lo = p;
    else {
      const t = (year - lo.year) / (p.year - lo.year);
      return { value: Math.round(lo.value + t * (p.value - lo.value)), interpolated: true };
    }
  }
  return { value: pts[pts.length - 1].value, interpolated: false };
}

/** Ближайший к году переписной/известный год серии (для подписи источника). */
export function nearestPoint(s: Series | undefined, year: number): Point | null {
  const pts = seriesPoints(s);
  if (!pts.length) return null;
  let best = pts[0];
  for (const p of pts) if (Math.abs(p.year - year) < Math.abs(best.year - year)) best = p;
  return best;
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat('ru-RU').format(Math.round(n));
}

export function formatCompact(n: number): string {
  if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toLocaleString('ru-RU', { maximumFractionDigits: 2 }) + ' млн';
  if (Math.abs(n) >= 1_000) return (n / 1_000).toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' тыс.';
  return formatNumber(n);
}

export function formatPct(x: number, digits = 1): string {
  return (x * 100).toLocaleString('ru-RU', { maximumFractionDigits: digits }) + '%';
}

export const DTYPE_LABEL: Record<DType, string> = {
  c: 'перепись',
  e: 'оценка',
  r: 'ретроспективная оценка',
  m: 'вычислено (сумма городов)',
};
