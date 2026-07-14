/**
 * INF-08 v3: типы и загрузка данных интерактива «Беларусь из космоса».
 *
 * Аналитический слой (nightlights_v2.json) — единственный источник чисел,
 * рейтингов и событий; визуальный слой (manifest) — кадры карты; события
 * и адаптивные длительности — nightlights_events.json; ручные причинные
 * аннотации — nightlights_annotations.json.
 */
import { useEffect, useState } from 'react';

export interface ModelPoint { l: number; ls: number; ps: number }
export interface AnalyticRow {
  id: string;
  lshare: Record<string, number>;
  pshare: Record<string, number>;
  light: Record<string, number>;
  lightRatio: number | null;
  popRatio: number | null;
  div: number | null;
  model: Record<string, Record<string, Record<string, ModelPoint>>>;
}
export interface Analytic {
  version: string;
  segments: { dmsp: [number, number]; vnl: [number, number]; model: [number, number] };
  yearsObs: number[];
  nodes: number[];
  scenarios: string[];
  jumpoffs: string[];
  mapping: { aBar: number; b: number; f18: number; r2: number };
  natLight: Record<string, number>;
  natPop: Record<string, number>;
  natModel: Record<string, Record<string, Record<string, number>>>;
  rows: AnalyticRow[];
}

export interface FrameEntry {
  year: number;
  scenario?: string;
  jumpoff?: string;
  asset: string;
  sourceType: 'reconstructed_viirs_like' | 'observed_viirs' | 'modeled_forecast';
  analyticalSource: string;
  comparableToPrevious: boolean;
  qualityFlags: string[];
  referenceYear: number | null;
}
export interface DeltaItem {
  kind: string;
  asset: string;
  year?: number;
  refYear?: number;
  scenario?: string;
  jumpoff?: string;
  crossSource?: boolean;
}
export interface Manifest {
  version: string;
  grid: { width: number; height: number; bounds: [number, number, number, number] };
  sourceTypeLabels: Record<string, Record<string, string>>;
  reconstruction: { caveat: string };
  frames: FrameEntry[];
  deltas: { threshold: number; cap: number; analysisBases: number[]; items: DeltaItem[] };
}

export interface EventRegion {
  id: string;
  direction: 'rise' | 'fall';
  annualizedChange: number;
  nationalShareDelta: number;
  confidence: string;
  annotationKey: string | null;
}
export interface NlEvent {
  year: number;
  kind: 'regional_change' | 'national_change' | 'source_transition' | 'quality_note' | 'forecast_boundary';
  score?: number;
  durationMs: number;
  pauseAfterMs?: number;
  quality: string;
  direction?: string;
  annualizedChange?: number;
  annotationKey?: string;
  scenarioScope?: string | null;
  regions: EventRegion[];
}
export interface EventsFile {
  events: NlEvent[];
  durationsMs: Record<string, number>;
}
export type Annotations = Record<string, { ru: string; be: string; source: string; sourceTitle: string }>;

export interface GeoFeature {
  properties: { id: string };
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][] };
}

export interface ExternalCheck {
  metric: string;
  zone: string;
  value: number | null;
  unit: string;
  detail?: string;
  note?: string;
  source: string;
  verdict: 'consistent' | 'inconsistent' | 'context';
  rule?: string;
}

export interface ExternalCase {
  caseId: string;
  period: [number, number];
  lightResidualPct: number;
  direction: string;
  checks: ExternalCheck[];
}

export interface NlData {
  night: Analytic;
  manifest: Manifest;
  events: EventsFile;
  annotations: Annotations;
  candidates: ResearchCandidate[];
  externalChecks: Record<string, ExternalCase>;
  geo: GeoFeature[];
  names: Record<string, string>;
}

export function useNlData(lang: string): NlData | null {
  const [data, setData] = useState<NlData | null>(null);
  useEffect(() => {
    let alive = true;
    Promise.all([
      fetch('/data/nightlights_v2.json').then((r) => r.json()),
      fetch('/data/nightlights/nightlights_manifest.json').then((r) => r.json()),
      fetch('/data/nightlights/nightlights_events.json').then((r) => r.json()),
      fetch('/data/nightlights/nightlights_annotations.json').then((r) => r.json()),
      fetch('/data/nightlights/research_candidates.json').then((r) => r.json()),
      fetch('/data/nightlights/external_checks.json').then((r) => r.json()),
      fetch('/data/geo/adm2.geojson').then((r) => r.json()),
      fetch('/data/geo/adm1.geojson').then((r) => r.json()),
      fetch('/data/data.json').then((r) => r.json()),
    ]).then(([night, manifest, events, annotations, cands, ext, g2, g1, d]) => {
      if (!alive) return;
      const geo = [
        ...g2.features.filter((f: GeoFeature) => f.properties.id.startsWith('r-')),
        ...g1.features.filter((f: GeoFeature) => f.properties.id === 'BY-HM'),
      ];
      const names: Record<string, string> = {};
      for (const t of Object.values(d.territories) as { id: string; ru: string; be?: string }[]) {
        names[t.id] = lang === 'be' && t.be ? t.be : t.ru;
      }
      const externalChecks: Record<string, ExternalCase> = {};
      for (const cs of (ext.cases ?? []) as ExternalCase[]) externalChecks[cs.caseId] = cs;
      setData({ night, manifest, events, annotations,
        candidates: cands.candidates ?? [], externalChecks, geo, names });
    });
    return () => { alive = false; };
  }, [lang]);
  return data;
}

/** Остановки таймлайна: 33 наблюдаемых года + узлы модели. */
export function stopsOf(night: Analytic): number[] {
  return [...night.yearsObs, ...night.nodes];
}

export function frameAsset(year: number, night: Analytic, scn: string, jmp: string,
  demo = false): string {
  if (year > 2024) {
    return demo
      ? `/data/nightlights/visual/demographic/${year}_${scn}_${jmp}.png`
      : `/data/nightlights/visual/modeled/${year}_${scn}_${jmp}.png`;
  }
  if (year >= 2012) return `/data/nightlights/visual/observed/${year}.png`;
  return `/data/nightlights/visual/reconstructed/${year}.png`;
}

export interface ResearchCandidate {
  id: string;
  titleRu: string;
  titleBe: string;
  status: string;
  direction: string;
  directionConfirmedByRecompute: boolean;
  period: [number, number];
  zones: string[];
  zonesNote: string;
  metrics: {
    metric: string; lightResidualPct: number; populationChange: number;
    lightChange: number; altMetric: string; altResidualPct: number;
  };
  hypotheses: string[];
  checkRu: string;
  qualityFlags: string[];
  evidenceLevel: string;
  releaseApproved: boolean;
}

export type DeltaMode = 'prev' | 'base2024' | 'scenario' | number; // number = базовый год анализа

export function deltaAsset(year: number, mode: DeltaMode, night: Analytic,
  scn: string, jmp: string): string | null {
  const isModel = year > 2024;
  if (mode === 'prev') {
    if (isModel) {
      if (year === night.nodes[0]) return `/data/nightlights/delta/base_2024/b24_${year}_${scn}_${jmp}.png`;
      return `/data/nightlights/delta/previous_year/pym_${year}_${scn}_${jmp}.png`;
    }
    if (year === 1992 || year === 2012) return null; // нет сопоставимой базы
    return `/data/nightlights/delta/previous_year/py_${year}.png`;
  }
  if (mode === 'base2024') {
    return isModel ? `/data/nightlights/delta/base_2024/b24_${year}_${scn}_${jmp}.png` : null;
  }
  if (mode === 'scenario') {
    if (!isModel || scn === 'base') return null;
    return `/data/nightlights/delta/scenarios/sc_${year}_${scn}_${jmp}.png`;
  }
  // базовый год режима «Анализ»
  if (isModel || year === mode) return null;
  return `/data/nightlights/delta/base_${mode}/ab_${year}.png`;
}

export function sourceTypeOf(year: number): FrameEntry['sourceType'] {
  if (year > 2024) return 'modeled_forecast';
  if (year >= 2012) return 'observed_viirs';
  return 'reconstructed_viirs_like';
}

/** Кросс-источниковая ли пара лет (для флага несопоставимости). */
export function crossSource(a: number, b: number): boolean {
  return sourceTypeOf(a) !== sourceTypeOf(b);
}

export function fmtPct(x: number, digits = 0): string {
  const v = x * 100;
  return `${v > 0 ? '+' : ''}${v.toFixed(digits)}%`;
}
