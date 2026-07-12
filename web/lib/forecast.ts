/** Прогноз населения (WP-F6, этапы 3, 5 и WP-F3): загрузка forecast.json
 *  и доступ к траекториям. */

export type ScenarioId = 'base' | 'optimistic' | 'negative';
/** Стартовый ряд (WP-F3): официальный или скорректированный на
 *  незарегистрированную эмиграцию 2020+. */
export type JumpoffId = 'official' | 'adjusted';

export interface ForecastEntry {
  years: number[];
  pop: number[];
  /** Веер вероятностного слоя (base): квантили q05…q95 Монте-Карло СКР/ОПЖ
   *  (полосы 80% = q10–q90 и 90% = q05–q95). */
  q05?: number[];
  q10?: number[];
  q25?: number[];
  q75?: number[];
  q90?: number[];
  q95?: number[];
}

export type FanKey = 'q05' | 'q10' | 'q25' | 'q75' | 'q90' | 'q95';

/** Вероятностный слой (этап 3): калиброванный Монте-Карло-веер вместо
 *  пропорционального переноса 80% PI WPP. */
export interface ProbabilisticBlock {
  calibration: { aTfr: number; aE0: number; growth: number; seed: number };
  stats: {
    n: number;
    start2026: number;
    pBelow8M_2041: number;
    pBelow7M_2051: number;
    pBelow6M_2075: number;
    pDecline2051: number;
    pGrowthAny: number;
  };
  wppValidation: Record<string, { sim80: number; wpp80: number }>;
  fanQuantiles: FanKey[];
}

export interface ForecastFile {
  version: string;
  horizon: [number, number];
  scenarios: ScenarioId[];
  scenarioMeta: Record<ScenarioId, { name: string; description: string }>;
  jumpoff: string[];
  /** Пояснение к ряду adjusted (интервал поправки, источник). */
  adjustedMeta?: { note: string };
  dtype: 'f';
  /** Вероятностный слой: калибровка, статистика, валидация по WPP. */
  probabilistic?: ProbabilisticBlock;
  territories: Record<string, Record<ScenarioId, ForecastEntry>>;
  /** Ряд adjusted: только уровни 0-1 (страна, области, Минск) - поправка
   *  территориально обоснована лишь до уровня областей. */
  adjusted?: Record<string, Record<ScenarioId, ForecastEntry>>;
}

export const FORECAST_START = 2026;

/** Есть ли у территории скорректированный ряд. */
export function hasAdjusted(f: ForecastFile | null, terr: string): boolean {
  return !!f?.adjusted?.[terr];
}

/** Прогнозное значение на год (линейная интерполяция между точками).
 *  При jumpoff='adjusted' берётся скорректированный ряд, если он есть
 *  для территории; иначе - официальный (районы и города). */
export function forecastAt(
  f: ForecastFile | null, terr: string, scenario: ScenarioId, year: number,
  key: 'pop' | FanKey = 'pop', jumpoff: JumpoffId = 'official',
): number | null {
  if (!f) return null;
  const entry = (jumpoff === 'adjusted' ? f.adjusted?.[terr]?.[scenario] : undefined)
    ?? f.territories[terr]?.[scenario];
  if (!entry) return null;
  const arr = entry[key];
  if (!arr) return null;
  const ys = entry.years;
  if (year < ys[0] || year > ys[ys.length - 1]) return null;
  for (let i = 0; i < ys.length - 1; i++) {
    if (year === ys[i]) return arr[i];
    if (year > ys[i] && year <= ys[i + 1]) {
      const k = (year - ys[i]) / (ys[i + 1] - ys[i]);
      return Math.round(arr[i] + k * (arr[i + 1] - arr[i]));
    }
  }
  return arr[arr.length - 1];
}

export const SCENARIO_LABEL: Record<ScenarioId, string> = {
  base: 'базовый',
  optimistic: 'оптимистический',
  negative: 'негативный',
};

export const JUMPOFF_LABEL: Record<JumpoffId, string> = {
  official: 'официальный',
  adjusted: 'скорректированный',
};
