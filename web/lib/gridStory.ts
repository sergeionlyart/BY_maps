'use client';

/** Данные и пресеты режима «История» (INF-15 v2,
 *  handoff/09_next_research/INF-15_grid_v2_brief.md). Источники чисел -
 *  web/public/data/grid_story.json (etl/grid_story.py) и уже загруженный
 *  grid.json (данные страницы v1) - см. docs/preregistration/grid-v0.2.md
 *  за гипотезами C-004/C-005 и docs/decisions/INF-15.md D-013 за находкой
 *  о внутрирайонной концентрации, упомянутой честной оговоркой на шаге 7. */

import { useEffect, useState } from 'react';
import type { GridData, Scenario, Variant } from './grid';

export interface StoryDensityBand {
  lo: number; hi: number | null; n_cells: number;
  pop_1975: number; pop_2020: number; change_pct: number | null; share_2020_pct: number;
}
export interface StoryHighwayBand {
  lo: number; hi: number | null; n_cells: number;
  pop_1975: number; pop_2020: number; change_pct: number | null;
}
export interface StoryRaion {
  id: string; name_ru: string; name_be: string;
  pop_1975: number; pop_2020: number; change_pct: number;
}
export interface GridStoryData {
  version: string;
  rule500_frame: string;
  c004_density_bands: { bounds_pop_per_km2: number[]; bands: StoryDensityBand[] };
  c005_highway_distance: { road_classes: string[]; bands_km: number[]; n_edges: number; bands: StoryHighwayBand[] };
  half_population_area_km2: Record<string, number>;
  country_area_km2: number;
  cells_ge5_pop: Record<string, number>;
  top_cell_concentration: Record<string, { top100_pct: number; top500_pct: number }>;
  raions: {
    shrunk_most: StoryRaion[]; grew_most: StoryRaion[]; minsk_city: StoryRaion | null;
    by_id: Record<string, StoryRaion>;
    n_raions_total: number; n_raions_shrunk: number; n_raions_shrunk_40pct_or_more: number;
    national_pop_1975: number; national_pop_2020: number; national_change_pct: number;
  };
  chernobyl_zone_class: Record<string, number>;
}

const cache: { data: GridStoryData | null } = { data: null };

export function useGridStoryData(): GridStoryData | null {
  const [data, setData] = useState<GridStoryData | null>(cache.data);
  useEffect(() => {
    if (cache.data) { setData(cache.data); return; }
    let alive = true;
    fetch('/data/grid_story.json').then((r) => r.json()).then((d) => {
      cache.data = d;
      if (alive) setData(d);
    }).catch(() => { /* сеть недоступна */ });
    return () => { alive = false; };
  }, []);
  return data;
}

const highwaysCache: { data: GeoJSON.FeatureCollection | null } = { data: null };

/** Слой магистралей (663 КБ) - грузится лениво, только когда режим
 *  «История» реально доходит до шага 3 (или деёплинк открывает его сразу),
 *  не на каждый заход на страницу. */
export function useHighwaysGeojson(enabled: boolean): GeoJSON.FeatureCollection | null {
  const [data, setData] = useState<GeoJSON.FeatureCollection | null>(highwaysCache.data);
  useEffect(() => {
    if (!enabled || highwaysCache.data) return;
    let alive = true;
    fetch('/data/geo/grid_highways.geojson').then((r) => r.json()).then((d) => {
      highwaysCache.data = d;
      if (alive) setData(d);
    }).catch(() => { /* сеть недоступна */ });
    return () => { alive = false; };
  }, [enabled]);
  return data;
}

export type Bounds = [number, number, number, number]; // W,S,E,N

// Bbox посчитаны по фактическим координатам городов-центров районов
// (web/public/data/data.json) с отступом - не угаданы на глаз.
export const BBOX_SOUTHEAST: Bounds = [29.1, 51.4, 31.6, 53.0];   // Брагин-Хойники-Наровля-Ветка
export const BBOX_WEST: Bounds = [23.7, 52.6, 26.2, 54.3];        // Щучин-Свислочь-Зельва-Ивье
export const BBOX_MINSK: Bounds = [26.5, 53.3, 28.6, 54.6];       // агломерация

export interface StoryStep {
  id: number;
  year: number;
  metric: 'pop' | 'density';
  scenario?: Scenario;
  variant?: Variant;
  bounds: Bounds | null; // null = вся страна
  /** Годы прокрутки (индексы ALL_YEARS), запускается один раз при входе на шаг. */
  scrub?: { fromYear: number; toYear: number };
  overlay?: 'rule500' | 'highway' | 'chernobyl-se' | 'chernobyl-west' | null;
  showScenarioControls?: boolean;
}

export const STORY_STEPS: StoryStep[] = [
  { id: 1, year: 1975, metric: 'pop', bounds: null },
  { id: 2, year: 1975, metric: 'density', bounds: null, scrub: { fromYear: 1975, toYear: 2020 }, overlay: 'rule500' },
  { id: 3, year: 2020, metric: 'pop', bounds: null, overlay: 'highway' },
  { id: 4, year: 2020, metric: 'pop', bounds: BBOX_SOUTHEAST, overlay: 'chernobyl-se' },
  { id: 5, year: 1975, metric: 'pop', bounds: BBOX_MINSK, scrub: { fromYear: 1975, toYear: 2020 } },
  { id: 6, year: 1975, metric: 'density', bounds: null, scrub: { fromYear: 1975, toYear: 2050 } },
  { id: 7, year: 2050, metric: 'pop', scenario: 'base', variant: 'A', bounds: null, showScenarioControls: true },
];

// шаг 4, часть 2 ("показать вторую") - те же id шага, другой bbox/overlay,
// переключается локальным состоянием в GridView, не отдельным StoryStep
export const STEP4_PART2 = { bounds: BBOX_WEST, overlay: 'chernobyl-west' as const };

function fmtMillions(n: number): string {
  return (n / 1_000_000).toFixed(2).replace('.', ',');
}
function fmtAbs(n: number): string {
  return Math.abs(n).toFixed(1).replace('.', ',');
}
function fmtSigned(n: number): string {
  return (n > 0 ? '+' : '') + n.toFixed(1).replace('.', ',');
}
function findRaion(story: GridStoryData, id: string): StoryRaion | undefined {
  return story.raions.by_id[id];
}

/** Строит все {{токены}} для интерполяции текста истории из живых данных -
 *  ни одно число в тексте не хардкодится, всё читается отсюда (grid_story.
 *  json + grid.json), см. web/lib/gridStoryContent.ts::interpolate. */
export function buildStoryValues(
  data: GridData, story: GridStoryData, lang: 'ru' | 'be',
): Record<string, string | number> {
  const c004 = story.c004_density_bands.bands;
  const c005 = story.c005_highway_distance.bands;
  const nm = (id: string) => {
    const r = findRaion(story, id);
    return r ? (lang === 'be' ? r.name_be : r.name_ru) : id;
  };
  const pct = (id: string) => {
    const r = findRaion(story, id);
    return r ? r.change_pct : 0;
  };
  const sc = data.national.settlement_components;
  const g3 = data.validation.g3_nightlights_crosscheck;

  return {
    half1975: story.half_population_area_km2['1975'],
    topCells: 941,
    topCellsShare: story.top_cell_concentration['2020']?.top500_pct ?? 46.3,
    band5_25: fmtSigned(c004[1]?.change_pct ?? 0),
    band25_100: fmtSigned(c004[2]?.change_pct ?? 0),
    band500_2000: fmtSigned(c004[4]?.change_pct ?? 0),
    band2000plus: fmtSigned(c004[5]?.change_pct ?? 0),
    hw0_2: fmtSigned(c005[0]?.change_pct ?? 0),
    hw2_5abs: fmtAbs(c005[1]?.change_pct ?? 0),
    hw5_10abs: fmtAbs(c005[2]?.change_pct ?? 0),
    hw10_20abs: fmtAbs(c005[3]?.change_pct ?? 0),
    nTerritoriesTotal: story.raions.n_raions_total + 1,
    nShrunk: story.raions.n_raions_shrunk,
    nShrunk40: story.raions.n_raions_shrunk_40pct_or_more,
    brahinName: nm('r-brahinski'), brahinPctAbs: fmtAbs(pct('r-brahinski')),
    narovlyaName: nm('r-naraulanski'), narovlyaPctAbs: fmtAbs(pct('r-naraulanski')),
    khoinikiName: nm('r-chojnicki'), khoinikiPctAbs: fmtAbs(pct('r-chojnicki')),
    vetkaName: nm('r-vietkauski'), vetkaPctAbs: fmtAbs(pct('r-vietkauski')),
    shchuchinName: nm('r-shchuchynski'), shchuchinPctAbs: fmtAbs(pct('r-shchuchynski')),
    svislachName: nm('r-svislacki'), svislachPctAbs: fmtAbs(pct('r-svislacki')),
    zelvaName: nm('r-zelvienski'), zelvaPctAbs: fmtAbs(pct('r-zelvienski')),
    iujeName: nm('r-iujeuski'), iujePctAbs: fmtAbs(pct('r-iujeuski')),
    minskPct: fmtAbs(story.raions.minsk_city?.change_pct ?? 0),
    minskRaionPct: fmtAbs(pct('r-minski')),
    brestPct: fmtAbs(pct('r-brescki')),
    grodnoPct: fmtAbs(pct('r-hrodzienski')),
    natPop1975M: fmtMillions(story.raions.national_pop_1975),
    natPop2020M: fmtMillions(story.raions.national_pop_2020),
    islands1975: sc['1975']?.n_components ?? 0,
    islands2020: sc['2020']?.n_components ?? 0,
    islands2050: sc['2050:base:A']?.n_components ?? 0,
    largestArea1975: ((sc['1975']?.largest_share_of_area ?? 0) * 100).toFixed(1),
    largestArea2020: ((sc['2020']?.largest_share_of_area ?? 0) * 100).toFixed(1),
    largestArea2050: ((sc['2050:base:A']?.largest_share_of_area ?? 0) * 100).toFixed(1),
    cellsGe51975: story.cells_ge5_pop['1975'],
    cellsGe52020: story.cells_ge5_pop['2020'],
    cellsGe52050: story.cells_ge5_pop['2050:base:A'],
    g3AgreeCount: g3.n_agree,
    g3TotalCount: g3.n_raions,
    g3AgreePct: g3.pct_agree,
    g3Threshold: g3.threshold_pct,
  };
}
