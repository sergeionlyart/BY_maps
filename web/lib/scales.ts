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
/** Сельская плотность (район без городских центров) заметно ниже средней -
 *  шкала с лучшим разрешением в диапазоне 5-35 чел/км². */
const DENSITY_BREAKS_NOCENTER = [5, 8, 12, 16, 20, 25, 35, 60];
const POP_BREAKS: Record<MapLevel, number[]> = {
  raion: [15_000, 25_000, 35_000, 50_000, 75_000, 120_000, 250_000, 500_000],
  oblast: [1_000_000, 1_100_000, 1_200_000, 1_300_000, 1_400_000, 1_500_000, 1_700_000, 2_000_000],
  city: [],
};
/** Изменение, % к базовому году. */
const CHANGE_BREAKS = [-0.5, -0.3, -0.15, -0.05, 0.05, 0.15, 0.3, 0.5];

export function colorFor(metric: Metric, level: MapLevel, value: number | null, noCenter = false): string {
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
  const breaks = metric === 'density'
    ? (noCenter && level === 'raion' ? DENSITY_BREAKS_NOCENTER : DENSITY_BREAKS[level])
    : POP_BREAKS[level];
  let i = 0;
  while (i < breaks.length && value >= breaks[i]) i++;
  return SEQ[Math.min(i, SEQ.length - 1)];
}

export function legendStops(metric: Metric, level: MapLevel, noCenter = false): { color: string; label: string }[] {
  if (metric === 'change') {
    const labels = ['< −50', '−50…−30', '−30…−15', '−15…−5', '±5', '+5…15', '+15…30', '+30…50', '> +50'];
    const colors = [DIV_NEG[3], DIV_NEG[2], DIV_NEG[1], DIV_NEG[0], DIV_MID, DIV_POS[0], DIV_POS[1], DIV_POS[2], DIV_POS[3]];
    return colors.map((c, i) => ({ color: c, label: labels[i] }));
  }
  const breaks = metric === 'density'
    ? (noCenter && level === 'raion' ? DENSITY_BREAKS_NOCENTER : DENSITY_BREAKS[level])
    : POP_BREAKS[level];
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

/** Города: размер и интенсивность цвета растут с населением (и падают при
 *  убыли). Цвет - относительная красная шкала, нормированная на исторический
 *  максимум по всем городам за весь период (пик Минска, ~2,02 млн): город на
 *  пике максимума - ярко-красный, остальные - пропорционально бледнее.
 *
 *  Пропорция сжимается степенью 0.35: населения городов различаются в сотни
 *  раз, и при линейной шкале все города, кроме Минска, оставались бы почти
 *  белыми. Монотонность сохраняется: больше населения - всегда краснее. */
const CITY_STOPS: Record<'light' | 'dark', [number, [number, number, number]][]> = {
  light: [[0, [246, 224, 205]], [0.45, [240, 138, 92]], [0.75, [230, 72, 41]], [1, [217, 14, 7]]],
  dark: [[0, [122, 92, 74]], [0.45, [204, 106, 60]], [0.75, [240, 78, 40]], [1, [255, 42, 24]]],
};

export function cityColor(pop: number | null, maxPop: number, dark: boolean): string {
  if (pop == null || pop <= 0 || maxPop <= 0) return 'transparent';
  const t = Math.pow(Math.min(pop / maxPop, 1), 0.35);
  const stops = CITY_STOPS[dark ? 'dark' : 'light'];
  let i = 1;
  while (i < stops.length - 1 && t > stops[i][0]) i++;
  const [t0, c0] = stops[i - 1];
  const [t1, c1] = stops[i];
  const k = (t - t0) / (t1 - t0 || 1);
  const rgb = c0.map((v, j) => Math.round(v + (c1[j] - v) * Math.max(0, Math.min(1, k))));
  return `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
}

/** Радиус круга города, px. Сжатая степенная шкала r ∝ pop^0.4: населения
 *  городов различаются в сотни раз (5 тыс. - 2 млн), и при r ∝ √pop малые
 *  города упираются в минимальный радиус и выглядят статичными. Показатель
 *  0.4 укладывает весь диапазон в 2-17 px: рост райцентра с 10 до 20 тыс.
 *  виден так же ясно, как рост Минска (важно для периода до 1970 г.). */
export function cityRadius(pop: number | null, overlay: boolean): number {
  if (pop == null || pop <= 0) return 0;
  const k = overlay ? 0.0514 : 0.062;
  return Math.max(overlay ? 1.8 : 2.1, k * Math.pow(pop, 0.4));
}
