/** INF-13 «Кто кого содержит»: типы web/public/data/pension.json и
 *  клиентские помощники (год выхода на пенсию, отображение года перехода,
 *  ключ серии сценарий:стартовый_ряд). Схему производит etl/pension.py. */

export type PolicyId = 'as_is' | '65_60' | '67_62';
export type ScenarioId = 'base' | 'optimistic' | 'negative';
export type JumpoffId = 'official' | 'adjusted';
export type SeriesKey = `${ScenarioId}:${JumpoffId}`;
export type ThresholdKey = '2.0' | '1.5' | '1.0';

export const THRESHOLDS: ThresholdKey[] = ['2.0', '1.5', '1.0'];
export const SCENARIOS: ScenarioId[] = ['base', 'optimistic', 'negative'];
export const JUMPOFFS: JumpoffId[] = ['official', 'adjusted'];
export const POLICIES: PolicyId[] = ['as_is', '65_60', '67_62'];

export function seriesKey(scenario: ScenarioId, jumpoff: JumpoffId): SeriesKey {
  return `${scenario}:${jumpoff}`;
}

export interface RetirementAge {
  m: number;
  f: number;
}

export interface DispersionEntry {
  n: number;
  mean: number | null;
  sd: number | null;
  cv: number | null;
  min: number | null;
  max: number | null;
  range: number | null;
}

type SeriesMap<T> = Partial<Record<SeriesKey, T>>;
type PolicySeriesArrays = Partial<Record<PolicyId, SeriesMap<(number | null)[]>>>;
type PolicySeriesCrossing = Partial<Record<PolicyId, SeriesMap<Record<ThresholdKey, number | null>>>>;
type PolicySeriesCrossingInterval = Partial<Record<PolicyId, SeriesMap<Record<ThresholdKey, string | null>>>>;
type PolicyDeltaBlock = Record<ThresholdKey, Record<'65_60' | '67_62', SeriesMap<number | null>>>;

export interface TerritoryEntry {
  name: string;
  oblast: string;
  commute_zone_45min: boolean;
  sr: PolicySeriesArrays;
  tdr: PolicySeriesArrays;
  crossing: PolicySeriesCrossing;
  /** Не null только если гейт G-3 не пройден (районный бэктест) - тогда
   *  crossing (точный год) на странице НЕ показывается, только интервал. */
  crossing_interval: PolicySeriesCrossingInterval | null;
  policy_delta: PolicyDeltaBlock;
  cg: SeriesMap<Record<string, number | null>> | null;
  cg_suppressed: boolean;
}

export interface NationalBlock {
  sr: PolicySeriesArrays;
  tdr: PolicySeriesArrays;
  crossing: PolicySeriesCrossing;
  policy_delta: PolicyDeltaBlock;
  dispersion_sr?: Record<string, DispersionEntry>;
}

export interface PensionFile {
  version: string;
  forecast_version: string;
  generated: string;
  retirement_schedule: Record<string, RetirementAge>;
  policy_variants: PolicyId[];
  policy_ages: Record<PolicyId, RetirementAge | null>;
  policy_applies_from: number;
  contribution_rate: number;
  series_keys: SeriesKey[];
  thresholds: number[];
  years: { national: number[]; territory: number[] };
  dtype: { national: Record<string, string>; territory: Record<string, string> };
  national: NationalBlock;
  territories: Record<string, TerritoryEntry>;
  meta: {
    claims: string[];
    artifact: string;
    validation: {
      G1_national_shares: boolean;
      G2_raion_sum_oblast: boolean;
      G3_backtest: boolean;
      G4_wpp_check: boolean;
      G5_sensitivity: boolean;
      G7_commute_bias: string;
      note: string;
    };
  };
}

/** Значение показателя (sr/tdr) территории на конкретный год. */
export function valueAt(
  block: PolicySeriesArrays,
  years: number[],
  policy: PolicyId,
  key: SeriesKey,
  year: number
): number | null {
  const arr = block[policy]?.[key];
  if (!arr) return null;
  const i = years.indexOf(year);
  return i < 0 ? null : arr[i] ?? null;
}

/** Год перехода: если у территории задан crossing_interval (G-3 не
 *  пройдена), возвращает текстовый интервал; иначе точный год. */
export function crossingDisplay(
  entry: TerritoryEntry,
  policy: PolicyId,
  key: SeriesKey,
  threshold: ThresholdKey
): { kind: 'year'; value: number } | { kind: 'interval'; value: string } | { kind: 'none' } {
  if (entry.crossing_interval) {
    const v = entry.crossing_interval[policy]?.[key]?.[threshold];
    return v ? { kind: 'interval', value: v } : { kind: 'none' };
  }
  const v = entry.crossing[policy]?.[key]?.[threshold];
  return v != null ? { kind: 'year', value: v } : { kind: 'none' };
}

/** Законная граница трудоспособного возраста в году `year` для пола `sex`
 *  при варианте `policy` - зеркало etl.pension.age_boundary на клиенте
 *  (единый источник данных - pf.retirement_schedule/policy_ages, без
 *  дублирования констант 60/55 / 63/58 в коде). */
export function ageBoundary(pf: PensionFile, year: number, sex: 'm' | 'f', policy: PolicyId): number {
  if (policy !== 'as_is' && year >= pf.policy_applies_from) {
    const alt = pf.policy_ages[policy];
    if (alt) return alt[sex];
  }
  const years = Object.keys(pf.retirement_schedule)
    .map(Number)
    .sort((a, b) => a - b);
  const clamped = Math.min(Math.max(year, years[0]), years[years.length - 1]);
  return pf.retirement_schedule[String(clamped)][sex];
}

/** «Найди себя»: год выхода на пенсию для человека, родившегося в
 *  birthYear, по действующему (или гипотетическому) графику - первый год
 *  t >= birthYear, для которого возраст (t - birthYear) достиг границы A(t). */
export function findRetirementYear(pf: PensionFile, birthYear: number, sex: 'm' | 'f', policy: PolicyId = 'as_is'): number {
  const lastYear = Math.max(...pf.years.territory, ...pf.years.national, 2100);
  for (let t = birthYear; t <= lastYear; t++) {
    const age = t - birthYear;
    if (age >= ageBoundary(pf, t, sex, policy)) return t;
  }
  return lastYear;
}

/** Ближайший опубликованный год ряда территории <= заданному (для карточки
 *  «в этот год у вас в районе будет N работающих на пенсионера»). */
export function nearestTerritoryYear(pf: PensionFile, year: number): number {
  const years = pf.years.territory;
  let best = years[0];
  for (const y of years) {
    if (Math.abs(y - year) < Math.abs(best - year)) best = y;
  }
  return best;
}

export const SCENARIO_LABEL: Record<ScenarioId, string> = {
  base: 'базовый',
  optimistic: 'оптимистичный',
  negative: 'негативный',
};

export const JUMPOFF_LABEL: Record<JumpoffId, string> = {
  official: 'официальный',
  adjusted: 'скорректированный',
};

export const POLICY_LABEL: Record<PolicyId, string> = {
  as_is: 'как сейчас (63 / 58)',
  '65_60': '65 / 60',
  '67_62': '67 / 62',
};

export const THRESHOLD_LABEL: Record<ThresholdKey, string> = {
  '2.0': '2 к 1',
  '1.5': '1,5 к 1',
  '1.0': '1 к 1',
};
