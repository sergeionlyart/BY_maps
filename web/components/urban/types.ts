/** INF-12 «Цена пустеющей карты»: типы story-JSON (web/public/data/urban_overhang.json)
 *  и пер-городских сеток (web/public/data/urban/city_<id>.json).
 *  Схему производит etl/urban.py + etl/urban_webgrids.py. */

export interface CityYearPoint {
  year: number;
  pop: number | null;
  popStatus: 'census' | 'estimate' | 'interpolated' | 'missing';
  built: number | null;       // км², фикс-рамка (MORPH_FIXED_FRAME)
  builtCore: number | null;   // км², ядро (контур 1975)
  builtEdge: number | null;   // км², край (вошло в фонд после 1975)
  footprint: number | null;   // км², динамический морфологический контур
  bpc: number | null;         // м² застройки на жителя
}

export interface VnlPoint {
  year: number;
  total: number;              // сумма радианса, фикс-рамка
  core: number;
  edge: number;
  share: number | null;       // доля города в национальном свете
}

export interface CityMain {
  pgr: number;                // лог-годовой темп населения 1990-2020
  bgr: number;                // лог-годовой темп фонда
  mor: number;                // MOR = BGR - PGR
  morLo: number; morHi: number;   // размах по 9 сценариям границ
  morAdmin: number | null;    // MOR в административной рамке OSM
  mdc: number;                // минимально обнаружимое изменение
  robust: boolean;
  timeSensitive: boolean;
  ees: number | null;         // доля новой застройки за прежним контуром
  p1990: number; p2020: number;
  b1990: number; b2020: number;   // км²
  bpc1990: number; bpc2020: number;
}

export interface StoryCity {
  id: string;
  ru: string;
  be: string;
  region: string;             // BY-BR|BY-HO|BY-HR|BY-HM|BY-MA|BY-MI|BY-VI
  lat: number;
  lon: number;
  flags: string[];
  quality: 'A' | 'B' | 'C';
  qualityReasons: string;
  type: 'T1' | 'T2' | 'T3' | 'T4' | 'T5' | 'T6' | 'TX';
  agreement: number;          // доля сценариев с тем же типом
  merged: string | null;
  series: CityYearPoint[];
  vnl: VnlPoint[];
  main: CityMain | null;
  lightMetrics: {
    sug: number | null;
    sug_share: number | null;
    ihs: number | null;
    ubi_2023?: number | null;   // свет на м² фонда, поздн. окно [MODEL]
  };
  roads: {
    per1000: { all: number | null; major: number | null; local: number | null };
    km: { all: number | null; major: number | null; local: number | null };
  };
  poi: Record<string, { count: number | null; per10k: number | null }>;
  popNow: number | null;
}

export interface StoryCase {
  role: 'satellite' | 'monotown' | 'small_center' | 'northeast' | 'cluster' | 'counterexample';
  city_id: string;
  cluster_with?: string;
  strict?: boolean;           // counterexample: строгий или «слабейший навес»
}

export interface StoryNational {
  n_cities: number;
  n_declining: number;
  n_growing: number;
  n_stable: number;
  median_mor_declining: number | null;
  median_mor_growing: number | null;
  n_overhang_robust: number;
  share_declining_with_overhang: number | null;
  type_counts: Record<string, number>;
  pop_share_in_overhang: number | null;
  median_bpc_1990: number | null;
  median_bpc_2020: number | null;
  matching: {
    n_pairs: number;
    median_mor_gap: number | null;
    sign_test_p?: number | null;
    n_gap_positive?: number;
    balance?: Record<string, { smd_before: number | null; smd_after: number | null }>;
  };
  n_quality_c?: number;
}

export interface StoryPair {
  treated: string;
  control: string;
  distance: number;
  mor_treated: number;
  mor_control: number;
}

export interface Story {
  research_id: 'INF-12';
  version: string;
  data_cutoff: string;
  mainInterval: [number, number];
  epochs: number[];
  national: StoryNational;
  cases: StoryCase[];
  pairs: StoryPair[];
  cities: Record<string, StoryCity>;
}

/** Пер-городская сетка для канвы «физический след». */
export interface CityGrid {
  id: string;
  w: number;
  h: number;
  cellM: number;              // 100
  epochs: number[];
  grids: Record<string, string>;   // эпоха -> base64 PNG (доля застройки 0..255)
  entry: string;              // base64 PNG: 255 вне рамки, 0 буфер, 1..10 эпоха входа
  light: Record<string, string>;   // vnl2013/vnl2024 -> base64 PNG (лог-шкала)
  lightNote: string;
}

export const TYPE_LABELS: Record<string, string> = {
  T1: 'Компактный рост',
  T2: 'Периферийное расползание',
  T3: 'Стабильная оболочка при депопуляции',
  T4: 'Расширение при депопуляции',
  T5: 'Сокращение без надёжного сигнала фонда',
  T6: 'Агломерационный перераспределитель',
  TX: 'Неопределённая траектория',
};

/** Цвета типов - существующие токены проекта (не красный/зелёный код). */
export const TYPE_COLORS: Record<string, string> = {
  T1: 'var(--accent)',        // рост - синий (данные)
  T2: 'var(--chip-model)',    // фиолетовый
  T3: 'var(--accent-2)',      // медь
  T4: 'var(--neg)',           // терракота
  T5: 'var(--muted)',
  T6: 'var(--viz-urban)',
  TX: 'var(--muted)',
};

export const REGION_LABELS: Record<string, string> = {
  'BY-BR': 'Брестская', 'BY-HO': 'Гомельская', 'BY-HR': 'Гродненская',
  'BY-HM': 'Минск', 'BY-MA': 'Могилёвская', 'BY-MI': 'Минская',
  'BY-VI': 'Витебская',
};

/** Декодирует base64-PNG в массив значений (канал R). */
export async function decodePng(b64: string): Promise<{ w: number; h: number; data: Uint8Array }> {
  const img = new Image();
  img.src = `data:image/png;base64,${b64}`;
  await img.decode();
  const canvas = document.createElement('canvas');
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext('2d', { willReadFrequently: true })!;
  ctx.drawImage(img, 0, 0);
  const rgba = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
  const data = new Uint8Array(canvas.width * canvas.height);
  for (let i = 0; i < data.length; i++) data[i] = rgba[i * 4];
  return { w: canvas.width, h: canvas.height, data };
}

export function fmtNum(v: number | null | undefined, digits = 1): string {
  if (v == null) return '—';
  return v.toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

/** Годовой лог-темп -> проценты за период, строкой со знаком. */
export function ratePct(rate: number | null | undefined, years: number, digits = 0): string {
  if (rate == null) return '—';
  const pct = (Math.exp(rate * years) - 1) * 100;
  const s = pct.toLocaleString('ru-RU', { maximumFractionDigits: digits });
  if (s === '0' || s === '-0') return '0%';   // не показывать «-0%»
  return pct > 0 ? `+${s}%` : `${s}%`;
}
