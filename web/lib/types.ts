/** Тип точки данных: c - перепись, e - оценка, r - ретроспективная
 *  реконструкция, m - вычислено (сумма городских НП). */
export type DType = 'c' | 'e' | 'r' | 'm';

export type Series = Record<string, [number, DType]>;

export type Level = 'country' | 'oblast' | 'raion' | 'city';

export interface Territory {
  id: string;
  level: Level;
  ru: string;
  be: string;
  parent: string | null;
  area?: number;
  lon?: number | null;
  lat?: number | null;
  flags: string[];
  center?: string[];
  raion?: string;
  pop: Series;
  popAdmin?: Series;
  popNoCenter?: Series;
  urban?: Series;
  note?: string;
}

export interface PanelRow {
  year: number;
  pop: number | null;
  popType?: string | null;
  urban?: number;
  urbanType?: string;
  minsk?: number;
  oblCenters?: number;
  top7?: number;
}

export interface DataFile {
  censusYears: number[];
  yearRange: [number, number];
  territories: Record<string, Territory>;
  panel: PanelRow[];
}

export type Metric = 'pop' | 'density' | 'change';
export type MapLevel = 'oblast' | 'raion' | 'city';
export type RaionMode = 'total' | 'noCenter';
