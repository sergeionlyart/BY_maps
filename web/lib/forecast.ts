/** Прогноз населения (WP-F6, этапы 3 и 5): загрузка forecast.json и доступ к траекториям. */

export type ScenarioId = 'base' | 'optimistic' | 'negative';

export interface ForecastEntry {
  years: number[];
  pop: number[];
  q10?: number[];
  q90?: number[];
}

export interface ForecastFile {
  version: string;
  horizon: [number, number];
  scenarios: ScenarioId[];
  scenarioMeta: Record<ScenarioId, { name: string; description: string }>;
  jumpoff: string[];
  dtype: 'f';
  territories: Record<string, Record<ScenarioId, ForecastEntry>>;
}

export const FORECAST_START = 2026;

/** Прогнозное значение на год (линейная интерполяция между точками). */
export function forecastAt(
  f: ForecastFile | null, terr: string, scenario: ScenarioId, year: number,
  key: 'pop' | 'q10' | 'q90' = 'pop',
): number | null {
  if (!f) return null;
  const entry = f.territories[terr]?.[scenario];
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
