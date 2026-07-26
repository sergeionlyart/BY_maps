/** INF-13 «Кто кого содержит»: дивергентная цветовая шкала коэффициента
 *  поддержки (SR), середина зафиксирована на пороге 1,5 (ТЗ §3, Приложение А
 *  «дивергентная шкала SR с серединой на 1,5»). Переиспользует уже принятую
 *  в проекте дивергентную палитру (red-grey-blue) из lib/scales.ts вместо
 *  новых hex-значений — тот же приём, что и в choropleth изменения
 *  населения (MapView) и остатка CCR (MLChallengerView). */

import { DIV_NEG, DIV_MID, DIV_POS } from '@/lib/scales';

/** Пороги совпадают, где возможно, с публикуемыми порогами перехода
 *  (1,0 и 2,0), чтобы легенду было легко сопоставить с карточкой района. */
export const SR_BREAKS = [1.0, 1.17, 1.33, 1.45, 1.55, 1.75, 2.0, 2.5];

export function srColor(v: number | null | undefined): string {
  if (v == null) return 'var(--surface-2)';
  const b = SR_BREAKS;
  if (v < b[0]) return DIV_NEG[3];
  if (v < b[1]) return DIV_NEG[2];
  if (v < b[2]) return DIV_NEG[1];
  if (v < b[3]) return DIV_NEG[0];
  if (v <= b[4]) return DIV_MID;
  if (v <= b[5]) return DIV_POS[0];
  if (v <= b[6]) return DIV_POS[1];
  if (v <= b[7]) return DIV_POS[2];
  return DIV_POS[3];
}

export const SR_LEGEND: { color: string; label: string }[] = [
  { color: DIV_NEG[3], label: '< 1,0' },
  { color: DIV_NEG[2], label: '1,0–1,17' },
  { color: DIV_NEG[1], label: '1,17–1,33' },
  { color: DIV_NEG[0], label: '1,33–1,45' },
  { color: DIV_MID, label: '≈ 1,5 (порог)' },
  { color: DIV_POS[0], label: '1,55–1,75' },
  { color: DIV_POS[1], label: '1,75–2,0' },
  { color: DIV_POS[2], label: '2,0–2,5' },
  { color: DIV_POS[3], label: '> 2,5' },
];
