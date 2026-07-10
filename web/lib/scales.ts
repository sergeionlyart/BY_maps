import type { Metric, MapLevel } from './types';

/** Секвенциальная шкала (один тон, синий) - численность и плотность.
 *  Шаги 100-700 референсной палитры dataviz. */
export const SEQ = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#1c5cab', '#104281', '#0d366b'];

/** Дивергентная шкала (синий - серый - красный) для изменения населения:
 *  убыль - красная ветвь, рост - синяя. */
export const DIV_NEG = ['#f0b9b9', '#e57f7e', '#d03b3b', '#a02222'];
export const DIV_MID = '#f0efec';
export const DIV_POS = ['#b7d3f6', '#6da7ec', '#2a78d6', '#184f95'];

/** Фиксированные пороги, единые для всех лет - чтобы цвет был сопоставим
 *  при движении слайдера. Плотность: чел/км². Население: человек. */
const DENSITY_BREAKS: Record<MapLevel, number[]> = {
  raion: [10, 15, 20, 25, 30, 40, 60, 100],
  oblast: [35, 40, 45, 50, 55, 60, 80, 1000],
  city: [],
};
const POP_BREAKS: Record<MapLevel, number[]> = {
  raion: [15_000, 25_000, 35_000, 50_000, 75_000, 120_000, 250_000, 500_000],
  oblast: [1_000_000, 1_100_000, 1_200_000, 1_300_000, 1_400_000, 1_500_000, 1_700_000, 2_000_000],
  city: [],
};
/** Изменение, % к базовому году. */
const CHANGE_BREAKS = [-0.5, -0.3, -0.15, -0.05, 0.05, 0.15, 0.3, 0.5];

export function colorFor(metric: Metric, level: MapLevel, value: number | null): string {
  if (value == null) return 'transparent';
  if (metric === 'change') {
    const b = CHANGE_BREAKS;
    if (value < b[0]) return DIV_NEG[3];
    if (value < b[1]) return DIV_NEG[2];
    if (value < b[2]) return DIV_NEG[1];
    if (value < b[3]) return DIV_NEG[0];
    if (value <= b[4]) return DIV_MID;
    if (value <= b[5]) return DIV_POS[0];
    if (value <= b[6]) return DIV_POS[1];
    if (value <= b[7]) return DIV_POS[2];
    return DIV_POS[3];
  }
  const breaks = metric === 'density' ? DENSITY_BREAKS[level] : POP_BREAKS[level];
  let i = 0;
  while (i < breaks.length && value >= breaks[i]) i++;
  return SEQ[Math.min(i, SEQ.length - 1)];
}

export function legendStops(metric: Metric, level: MapLevel): { color: string; label: string }[] {
  if (metric === 'change') {
    const labels = ['< −50', '−50…−30', '−30…−15', '−15…−5', '±5', '+5…15', '+15…30', '+30…50', '> +50'];
    const colors = [DIV_NEG[3], DIV_NEG[2], DIV_NEG[1], DIV_NEG[0], DIV_MID, DIV_POS[0], DIV_POS[1], DIV_POS[2], DIV_POS[3]];
    return colors.map((c, i) => ({ color: c, label: labels[i] }));
  }
  const breaks = metric === 'density' ? DENSITY_BREAKS[level] : POP_BREAKS[level];
  const fmt = (n: number) => metric === 'density' ? String(n) : n >= 1_000_000 ? (n / 1_000_000).toLocaleString('ru-RU') + ' млн' : (n / 1000) + ' тыс.';
  return SEQ.map((c, i) => {
    let label: string;
    if (i === 0) label = `< ${fmt(breaks[0])}`;
    else if (i >= breaks.length) label = `≥ ${fmt(breaks[breaks.length - 1])}`;
    else label = `${fmt(breaks[i - 1])}–${fmt(breaks[i])}`;
    return { color: c, label };
  });
}

/** Категориальная палитра для сравнения территорий (референсная, слоты 1-4). */
export const CAT = ['#2a78d6', '#1baf7a', '#eda100', '#4a3aa7'];
export const CAT_DARK = ['#3987e5', '#199e70', '#c98500', '#9085e9'];
