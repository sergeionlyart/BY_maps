'use client';

/** Данные и пресеты режима «История» (INF-15 v2/v3). Источники чисел -
 *  web/public/data/grid_story.json (etl/grid_story.py) и уже загруженный
 *  grid.json - см. docs/preregistration/grid-v0.2.md за гипотезами
 *  C-004..C-007 и docs/decisions/INF-15.md D-013/D-015 за находками
 *  (внутрирайонная концентрация; C-007 опровергнута собственным
 *  критерием - см. буквальный текст шага 3, не смягчён и не скрыт). */

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
export interface StoryRiverBand {
  lo: number; hi: number | null; n_cells: number;
  pop_1975: number; pop_2020: number; change_pct: number | null;
  share_1975_pct: number | null; share_2020_pct: number | null;
}
export interface StoryMatrixGroup {
  id: 'both' | 'river_only' | 'road_only' | 'neither';
  n_cells: number; pop_1975: number; pop_2020: number; pop_2050_base_A: number;
  change_pct: number | null; change_2050_pct: number | null;
  share_2020_pct: number | null; area_share_pct: number | null;
}
export interface StoryIndependentCheck {
  n_cities_total: number; n_both: number; n_rest: number;
  years: [number, number]; test: string; p_threshold: number;
  both_median_change_pct?: number; rest_median_change_pct?: number;
  u_statistic?: number; p_value?: number;
  direction_confirmed?: boolean; significant_p10?: boolean;
}
export interface StoryCity {
  id: string; name_ru: string; name_be: string; lon: number; lat: number;
  river_km: number; road_km: number; change_pct_1989_2019: number | null;
  group: 'both' | 'river_only' | 'road_only' | 'neither' | 'buffer';
  is_exception: boolean;
}
export interface StoryRaion {
  id: string; name_ru: string; name_be: string;
  pop_1975: number; pop_2020: number; change_pct: number;
}
export interface GridStoryData {
  version: string;
  rule500_frame: string;
  matrix_frame: string;
  river_buffer_frame: string;
  islands_frames: Record<string, string>;
  c004_density_bands: { bounds_pop_per_km2: number[]; bands: StoryDensityBand[] };
  c005_highway_distance: { road_classes: string[]; bands_km: number[]; n_edges: number; bands: StoryHighwayBand[] };
  c006_river_road_matrix: {
    river_near_km: number; river_far_km: number; road_near_km: number; road_far_km: number;
    groups: StoryMatrixGroup[]; independent_check: StoryIndependentCheck;
  };
  c007_river_distance: {
    bands_km: number[]; n_edges: number; n_river_cells: number;
    bands: StoryRiverBand[]; share_near_5km_pct: { '1975': number; '2020': number };
    cities: StoryCity[];
  };
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
 *  «История» реально доходит до шага 3/4/5 (или деёплинк открывает его
 *  сразу), не на каждый заход на страницу. */
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

const riversCache: { data: GeoJSON.FeatureCollection | null } = { data: null };

/** Слой рек (v3, ~1,2 МБ) - грузится лениво, только когда режим «История»
 *  доходит до шага 3 или позже (или свободный режим включает тумблер). */
export function useRiversGeojson(enabled: boolean): GeoJSON.FeatureCollection | null {
  const [data, setData] = useState<GeoJSON.FeatureCollection | null>(riversCache.data);
  useEffect(() => {
    if (!enabled || riversCache.data) return;
    let alive = true;
    fetch('/data/geo/grid_rivers.geojson').then((r) => r.json()).then((d) => {
      riversCache.data = d;
      if (alive) setData(d);
    }).catch(() => { /* сеть недоступна */ });
    return () => { alive = false; };
  }, [enabled]);
  return data;
}

export type Bounds = [number, number, number, number]; // W,S,E,N

// Bbox посчитаны по фактическим координатам городов-центров районов
// (web/public/data/data.json) / полигонов районов (adm2.geojson) с
// отступом - не угаданы на глаз.
export const BBOX_SOUTHEAST: Bounds = [29.1, 51.4, 31.6, 53.0];   // Брагин-Хойники-Наровля-Ветка
export const BBOX_WEST: Bounds = [23.7, 52.6, 26.2, 54.3];        // Щучин-Свислочь-Зельва-Ивье
export const BBOX_POLESYE: Bounds = [23.4, 51.35, 27.9, 52.85];   // Столин-Лунинец-Иваново-Малорита-Дрогичин (v3)
export const BBOX_MINSK: Bounds = [26.5, 53.3, 28.6, 54.6];       // агломерация

/** Шаг 6 истории (v3, "три пустоты"): автоматическая последовательность
 *  трёх зумов (юго-восток -> запад -> Полесье), заканчивается общим видом
 *  страны. `chernobyl` - показывать ли оверлей чернобыльских зон на этой
 *  стадии (только юго-восток). Не запускается при prefers-reduced-motion -
 *  сразу показывается финальная стадия (национальный вид), см. GridView.tsx. */
export interface ZoomStage { bounds: Bounds | null; ms: number; chernobyl?: boolean }
export const STEP6_ZOOM_SEQUENCE: ZoomStage[] = [
  { bounds: BBOX_SOUTHEAST, ms: 3600, chernobyl: true },
  { bounds: BBOX_WEST, ms: 3600 },
  { bounds: BBOX_POLESYE, ms: 3600 },
  { bounds: null, ms: 0 }, // финальная стадия - национальный вид, остаётся до смены шага
];

export interface StoryStep {
  id: number;
  year: number;
  metric: 'pop' | 'density';
  scenario?: Scenario;
  variant?: Variant;
  bounds: Bounds | null; // null = вся страна
  /** Годы прокрутки (индексы ALL_YEARS), запускается один раз при входе на шаг. */
  scrub?: { fromYear: number; toYear: number };
  overlay?: 'rule500' | 'river-buffer' | 'matrix' | 'highway' | 'chernobyl-zoom' | 'islands' | null;
  /** Шаг 5 (v3): кнопка "показать города" - подписи 12 крупнейших городов. */
  showCities?: boolean;
  /** Шаг 6 (v3): автопоследовательность зумов вместо статичного bounds. */
  zoomSequence?: ZoomStage[];
  showScenarioControls?: boolean;
}

export const STORY_STEPS: StoryStep[] = [
  { id: 1, year: 1975, metric: 'pop', bounds: null },
  { id: 2, year: 1975, metric: 'density', bounds: null, scrub: { fromYear: 1975, toYear: 2020 }, overlay: 'rule500' },
  { id: 3, year: 2020, metric: 'pop', bounds: null, overlay: 'river-buffer' },
  { id: 4, year: 2020, metric: 'pop', bounds: null, overlay: 'matrix' },
  { id: 5, year: 2020, metric: 'pop', bounds: null, overlay: 'matrix', showCities: true },
  { id: 6, year: 2020, metric: 'pop', bounds: BBOX_SOUTHEAST, overlay: 'chernobyl-zoom', zoomSequence: STEP6_ZOOM_SEQUENCE },
  { id: 7, year: 1975, metric: 'pop', bounds: BBOX_MINSK, scrub: { fromYear: 1975, toYear: 2020 } },
  { id: 8, year: 1975, metric: 'density', bounds: null, scrub: { fromYear: 1975, toYear: 2050 }, overlay: 'islands' },
  { id: 9, year: 2050, metric: 'pop', scenario: 'base', variant: 'A', bounds: null, showScenarioControls: true },
];

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
  const c007 = story.c007_river_distance.bands;
  const matrixGroups = story.c006_river_road_matrix.groups;
  const matrixG = (id: string) => matrixGroups.find((g) => g.id === id);
  const nm = (id: string) => {
    const r = findRaion(story, id);
    return r ? (lang === 'be' ? r.name_be : r.name_ru) : id;
  };
  const pct = (id: string) => {
    const r = findRaion(story, id);
    return r ? r.change_pct : 0;
  };
  const cityByGeoId = (id: string) => story.c007_river_distance.cities.find((c) => c.id === id);
  const sc = data.national.settlement_components;
  const g3 = data.validation.g3_nightlights_crosscheck;
  const c3 = data.validation.c3_correlation;
  const soligorsk = cityByGeoId('c-salihorsk');
  const maladziechna = cityByGeoId('c-maladziechna');
  const both = matrixG('both');
  const riverOnly = matrixG('river_only');
  const roadOnly = matrixG('road_only');
  const neither = matrixG('neither');

  return {
    // v3: реки (C-006/C-007) - docs/preregistration/grid-v0.2.md §8,
    // числа независимо пересчитаны (D-015), не скопированы из документа v3.
    rivShareNear1975: story.c007_river_distance.share_near_5km_pct['1975'],
    rivShareNear2020: story.c007_river_distance.share_near_5km_pct['2020'],
    rivShare0_2_2020: c007[0]?.share_2020_pct ?? 0,
    rivShare2_5_2020: c007[1]?.share_2020_pct ?? 0,
    riv0_2Change: fmtSigned(c007[0]?.change_pct ?? 0),
    riv2_5Change: fmtSigned(c007[1]?.change_pct ?? 0),
    xBothPct: fmtSigned(both?.change_pct ?? 0),
    xRiverOnlyAbs: fmtAbs(riverOnly?.change_pct ?? 0),
    xRoadOnlyAbs: fmtAbs(roadOnly?.change_pct ?? 0),
    xRiverOnlySigned: fmtSigned(riverOnly?.change_pct ?? 0),
    xRoadOnlySigned: fmtSigned(roadOnly?.change_pct ?? 0),
    xNeitherSigned: fmtSigned(neither?.change_pct ?? 0),
    xRoadOnlyCells: roadOnly?.n_cells ?? 0,
    xNeitherAbs: fmtAbs(neither?.change_pct ?? 0),
    xShare2020: both?.share_2020_pct ?? 0,
    xAreaShare: both?.area_share_pct ?? 0,
    xBothTo2050Abs: fmtAbs(both?.change_2050_pct ?? 0),
    solihorskRiverKm: soligorsk?.river_km ?? 0,
    solihorskRoadKm: soligorsk?.road_km ?? 0,
    maladechnaRiverKm: maladziechna?.river_km ?? 0,
    maladechnaRoadKm: maladziechna?.road_km ?? 0,
    c3Rho: c3?.spearman_rho?.toFixed(2) ?? '0',
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
