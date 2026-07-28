'use client';

/**
 * «Полотно» (INF-15 v2): режим «История» (7 остановок, по умолчанию) и
 * режим «Свободно» (инструмент, как в v1).
 * handoff/09_next_research/INF-15_grid_v2_brief.md - подробности.
 *
 * - История: панель шага сама переключает год/метрику/зум/подсветку;
 *   deep-link ?story=N; прокрутка внутри шага - автоматически один раз
 *   при входе (не при reduced-motion), повтор - вручную;
 * - Свободно: дискретный ползунок по 16 узлам (слит с дорожкой узлов в
 *   один элемент - B-1/этап1 v2), переключатель метрики, ▶ отдельной
 *   крупной кнопкой с подписью, подсказки под тулбаром по наведённой
 *   кнопке, тренд-стрелки на плитках показателей;
 * - общие для обоих режимов, внизу: чипы статуса утверждений, блок
 *   расхождения по огням, блок про дороги, смежные материалы, источники;
 * - deep-link в «Свободно» - как в v1: ?year=&metric=&scenario=&variant=
 *   &borders=&track=, дебаунс 350 мс.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useT, useLang } from '@/lib/i18n';
import MethodDrawer from './MethodDrawer';
import GridMap from './grid/GridMap';
import StoryPanel from './grid/StoryPanel';
import {
  useGridData, frameKey, loadCellGrid, cellHasBinary, lonLatToCellIndex,
  cellValue, fmtInt, fmtPct, ALL_YEARS, nearestYear, networkLegendStops,
  type Scenario, type Variant, type Metric,
} from '@/lib/grid';
import {
  useGridStoryData, useHighwaysGeojson, buildStoryValues, STORY_STEPS, STEP4_PART2,
} from '@/lib/gridStory';
import { useGridStoryContent } from '@/lib/gridStoryContent';

const SCN_RU: Record<Scenario, string> = { base: 'базовый', optimistic: 'оптимистичный', negative: 'негативный' };
const METRIC_RU: Record<Metric, string> = {
  pop: 'Люди в клетке', density: 'Класс плотности', network: 'Метры сети на жителя',
};
const METRIC_HINT_RU: Record<Metric, string> = {
  pop: 'Сколько человек живёт в каждом квадрате 1×1 км. Ярче — плотнее.',
  density: 'То же самое, но грубее: четыре ступени от «почти никого» до «густо». Так лучше видно, как расползаются пустые места.',
  network: 'Сколько километров дорог приходится на тысячу жителей района. Снимок 2026 года — истории сети у нас нет, поэтому годы здесь не переключаются.',
};
const BORDERS_HINT_RU = 'Показать привычное деление на 118 районов — чтобы понять, где вы находитесь. По умолчанию выключено: вся идея карты в том, чтобы посмотреть на страну без них.';
const TRACK_HINT_RU = 'Точка, в которой страна «уравновешена» по числу жителей. За 45 лет она сместилась к Минску на 11,7 км — меньше, чем можно надёжно измерить нашим методом, поэтому вокруг неё показан коридор погрешности.';
const SCN_HINT_RU: Record<Scenario, string> = {
  base: 'Три набора предположений о рождаемости, смертности и отъезде. Не три версии будущего, а границы, в которых оно вероятнее всего окажется.',
  optimistic: 'Три набора предположений о рождаемости, смертности и отъезде. Не три версии будущего, а границы, в которых оно вероятнее всего окажется.',
  negative: 'Три набора предположений о рождаемости, смертности и отъезде. Не три версии будущего, а границы, в которых оно вероятнее всего окажется.',
};
const VARIANT_HINT_RU: Record<Variant, string> = {
  A: 'Внутренний рисунок района сохраняется таким, каким он складывался последние полвека.',
  B: 'То же будущее, но с усилением пригородов крупных городов и ускоренным опустением дальней периферии. Это осознанное допущение, а не измеренная величина.',
};

const PLAY_FRAME_MS = 700;

const CLAIM_LABEL_RU: Record<string, string> = {
  'C-001': 'люди концентрируются быстрее, чем пустеет территория',
  'C-002': 'доля пустеющей территории растёт непрерывно с 1975 года',
  'C-003': 'дорожной сети на жителя больше там, где сильнее убыль',
  'C-004': 'изменение населения клетки зависит от того, сколько людей было в 1975 году («правило пятисот»)',
  'C-005': 'население клетки зависит от удалённости от ближайшей магистрали',
};
const CLAIM_STATUS_RU: Record<string, string> = {
  open_question: 'Открытый вопрос', verified: 'Подтверждено',
};

interface FrameMeta {
  bounds_lonlat: [number, number, number, number];
  vmax: number;
  gamma: number;
  density_classes: { min: number; max: number | null; color: string; label: string }[];
}

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  return reduced;
}

function trendArrow(cur: number | null | undefined, prev: number | null | undefined): { dir: 'up' | 'down' | 'flat'; delta: number } | null {
  if (cur == null || prev == null) return null;
  const delta = cur - prev;
  if (Math.abs(delta) < 1e-9) return { dir: 'flat', delta: 0 };
  return { dir: delta > 0 ? 'up' : 'down', delta };
}

export default function GridView() {
  const t = useT();
  const lang = useLang();
  const data = useGridData();
  const storyData = useGridStoryData();
  const storyContent = useGridStoryContent(lang);
  const geoRef = useRef<{ adm1: GeoJSON.FeatureCollection; adm2: GeoJSON.FeatureCollection } | null>(null);
  const [geoLoaded, setGeoLoaded] = useState(false);
  const reducedMotion = useReducedMotion();

  const [mode, setMode] = useState<'story' | 'free'>('story');
  const [storyStepIdx, setStoryStepIdx] = useState(0);
  const [step4Part, setStep4Part] = useState<'se' | 'west'>('se');
  const [shareCopied, setShareCopied] = useState(false);
  const autoplayedStep = useRef<number | null>(null);

  const [idx, setIdx] = useState(ALL_YEARS.indexOf(2020));
  const year = ALL_YEARS[idx];
  const [playEndIdx, setPlayEndIdx] = useState(ALL_YEARS.length - 1);
  const [metric, setMetric] = useState<Metric>('pop');
  const [scenario, setScenario] = useState<Scenario>('base');
  const [variant, setVariant] = useState<Variant>('A');
  const [showBorders, setShowBorders] = useState(false);
  const [showTrack, setShowTrack] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [hoveredHint, setHoveredHint] = useState<string | null>(null);
  const [cell, setCell] = useState<{ lon: number; lat: number; value: number | null; exact: boolean } | null>(null);
  const [territory, setTerritory] = useState<{ id: string; name: string; value: number | null } | null>(null);
  const [snapNotice, setSnapNotice] = useState<string | null>(null);
  const initDone = useRef(false);
  const territoryNames = useRef<Record<string, { ru: string; be: string }> | null>(null);

  useEffect(() => {
    Promise.all([
      fetch('/data/geo/adm1.geojson').then((r) => r.json()),
      fetch('/data/geo/adm2.geojson').then((r) => r.json()),
    ]).then(([adm1, adm2]) => { geoRef.current = { adm1, adm2 }; setGeoLoaded(true); });
  }, []);

  useEffect(() => {
    if (metric !== 'network' || territoryNames.current) return;
    fetch('/data/data.json').then((r) => r.json()).then((d) => {
      const m: Record<string, { ru: string; be: string }> = {};
      for (const [id, tr] of Object.entries(d.territories as Record<string, { ru: string; be: string }>)) {
        m[id] = { ru: tr.ru, be: tr.be };
      }
      territoryNames.current = m;
    });
  }, [metric]);

  const currentStep = mode === 'story' ? STORY_STEPS[storyStepIdx] : null;
  const highwaysNeeded = currentStep?.overlay === 'highway';
  const highwaysGeojson = useHighwaysGeojson(highwaysNeeded);

  // deep-link: чтение при монтировании - ?story=N приоритетнее v1-параметров
  useEffect(() => {
    if (!data || initDone.current) return;
    initDone.current = true;
    const p = new URLSearchParams(window.location.search);
    const storyParam = parseInt(p.get('story') ?? '', 10);
    if (storyParam >= 1 && storyParam <= STORY_STEPS.length) {
      setMode('story');
      setStoryStepIdx(storyParam - 1);
      return;
    }
    if (!p.has('year') && !p.has('metric') && !p.has('scenario') && !p.has('borders') && !p.has('track')) return;
    setMode('free');
    const yRaw = parseInt(p.get('year') ?? '', 10);
    if (Number.isFinite(yRaw)) {
      const snapped = nearestYear(yRaw);
      setIdx(ALL_YEARS.indexOf(snapped));
      if (snapped !== yRaw) {
        setSnapNotice(t('данные с шагом 5 лет — показан') + ` ${snapped}`);
      }
    }
    const m = p.get('metric');
    if (m === 'pop' || m === 'density' || m === 'network') setMetric(m);
    const s = p.get('scenario') as Scenario | null;
    if (s && ['base', 'optimistic', 'negative'].includes(s)) setScenario(s);
    const v = p.get('variant') as Variant | null;
    if (v === 'A' || v === 'B') setVariant(v);
    if (p.get('borders') === '1') setShowBorders(true);
    if (p.get('track') === '1') setShowTrack(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  // deep-link: запись, с дебаунсом 350 мс
  useEffect(() => {
    if (!data) return;
    const id = window.setTimeout(() => {
      const url = new URL(window.location.href);
      if (mode === 'story') {
        url.searchParams.set('story', String(storyStepIdx + 1));
        for (const k of ['year', 'metric', 'scenario', 'variant', 'borders', 'track']) url.searchParams.delete(k);
      } else {
        url.searchParams.delete('story');
        url.searchParams.set('year', String(year));
        url.searchParams.set('metric', metric);
        if (year > 2020) {
          url.searchParams.set('scenario', scenario);
          url.searchParams.set('variant', variant);
        } else {
          url.searchParams.delete('scenario');
          url.searchParams.delete('variant');
        }
        if (showBorders) url.searchParams.set('borders', '1'); else url.searchParams.delete('borders');
        if (showTrack) url.searchParams.set('track', '1'); else url.searchParams.delete('track');
      }
      try { window.history.replaceState(null, '', url); } catch { /* лимит истории - следующая запись догонит */ }
    }, 350);
    return () => window.clearTimeout(id);
  }, [data, mode, storyStepIdx, year, metric, scenario, variant, showBorders, showTrack]);

  // История: применить пресет шага (год/метрика/зум/подсветка), запустить
  // прокрутку один раз при входе на шаг (не при reduced-motion).
  useEffect(() => {
    if (mode !== 'story') { setPlayEndIdx(ALL_YEARS.length - 1); return; }
    const step = STORY_STEPS[storyStepIdx];
    if (!step) return;
    setPlaying(false);
    setStep4Part('se');
    setMetric(step.metric);
    if (step.scenario) setScenario(step.scenario);
    if (step.variant) setVariant(step.variant);
    if (step.scrub) {
      setIdx(ALL_YEARS.indexOf(step.scrub.fromYear));
      setPlayEndIdx(ALL_YEARS.indexOf(step.scrub.toYear));
      if (!reducedMotion && autoplayedStep.current !== storyStepIdx) {
        autoplayedStep.current = storyStepIdx;
        const timer = window.setTimeout(() => setPlaying(true), 500);
        return () => window.clearTimeout(timer);
      }
    } else {
      setIdx(ALL_YEARS.indexOf(step.year));
      setPlayEndIdx(ALL_YEARS.length - 1);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, storyStepIdx]);

  const isForecast = year > 2020;
  const key = data ? frameKey(year, scenario, variant) : null;
  const frameUrl = data && key && metric !== 'network'
    ? (data.frames[metric === 'density' ? 'density' : 'pop'][key] ?? null)
    : null;
  const [frameMeta, setFrameMeta] = useState<FrameMeta | null>(null);
  useEffect(() => {
    fetch('/data/grid_frames/meta.json').then((r) => r.json()).then((m) => setFrameMeta(m as FrameMeta));
  }, []);

  // автовоспроизведение: играет от текущего idx до playEndIdx (в «Свободно»
  // - всегда до 2050; в «Истории» - до конца прокрутки шага, если она есть)
  useEffect(() => {
    if (!playing) return;
    const id = window.setTimeout(() => {
      if (idx + 1 > playEndIdx) { setPlaying(false); return; }
      setIdx((i) => i + 1);
    }, PLAY_FRAME_MS);
    return () => window.clearTimeout(id);
  }, [playing, idx, playEndIdx]);

  useEffect(() => {
    if (!data || metric === 'network') return;
    for (let d = -2; d <= 3; d++) {
      const i = idx + d;
      if (i < 0 || i >= ALL_YEARS.length || i === idx) continue;
      const y = ALL_YEARS[i];
      const k = frameKey(y, scenario, variant);
      const url = data.frames[metric][k];
      if (url) new Image().src = url;
    }
  }, [data, idx, metric, scenario, variant]);

  const networkValues = useMemo(() => {
    if (!data) return null;
    const m: Record<string, number | null> = {};
    for (const [id, tv] of Object.entries(data.territories)) {
      m[id] = tv.network_per_capita?.road_km_per_1000 ?? null;
    }
    return m;
  }, [data]);

  function pauseUser() { setPlaying(false); }

  async function handleMapClick(lon: number, lat: number) {
    pauseUser();
    if (!data || mode === 'story') return;
    setTerritory(null);
    setCell({ lon, lat, value: null, exact: false });
    const idx2 = lonLatToCellIndex(lon, lat, data.grid);
    if (!idx2) return;
    if (cellHasBinary(key ?? '')) {
      const arr = await loadCellGrid(key!);
      if (arr) {
        const v = cellValue(arr, idx2.row, idx2.col, data.grid);
        setCell({ lon, lat, value: v, exact: true });
        return;
      }
    }
    setCell({ lon, lat, value: null, exact: false });
  }

  function handleTerritoryClick(id: string) {
    pauseUser();
    if (!data || mode === 'story') return;
    setCell(null);
    const names = territoryNames.current;
    const name = names?.[id]?.[lang] ?? names?.[id]?.ru ?? id;
    const value = data.territories[id]?.network_per_capita?.road_km_per_1000 ?? null;
    setTerritory({ id, name, value });
  }

  function handleShareStep() {
    try {
      navigator.clipboard?.writeText(window.location.href);
      setShareCopied(true);
      window.setTimeout(() => setShareCopied(false), 2000);
    } catch { /* буфер обмена недоступен - ссылка уже в адресной строке */ }
  }

  function goFreeMode() {
    setMode('free');
    setPlaying(false);
    setIdx(ALL_YEARS.indexOf(2020));
    setMetric('pop');
  }

  if (!data) {
    return <p className="hint" role="status">{t('Загрузка данных сетки…')}</p>;
  }

  const below5 = data.national.area_share_below['5'][key ?? String(year)];
  const below1 = data.national.area_share_below['1'][key ?? String(year)];
  const pwDensity = data.national.population_weighted_density[key ?? String(year)] ?? data.national.population_weighted_density[String(year)];
  const arithDensity = data.national.arithmetic_density[key ?? String(year)] ?? data.national.arithmetic_density[String(year)];
  const settlement = data.national.settlement_components[key ?? String(year)] ?? data.national.settlement_components[String(year)];
  const g3 = data.validation.g3_nightlights_crosscheck;
  const c3 = data.validation.c3_correlation;
  const g6 = data.validation.g6_network;
  const visibleTrack = data.national.centroid_track.filter((p) => p.year <= year);
  const lastTrackPt = visibleTrack[visibleTrack.length - 1];

  // тренд-стрелки плиток (этап1 v2, п.3.3) - относительно предыдущего узла
  // ползунка (только в «Свободно», где ползунок в руках читателя)
  let prevKey: string | null = null;
  if (mode === 'free' && idx > 0) {
    const prevYear = ALL_YEARS[idx - 1];
    prevKey = frameKey(prevYear, scenario, variant);
  }
  const prevBelow5 = prevKey ? data.national.area_share_below['5'][prevKey] : null;
  const prevPw = prevKey ? data.national.population_weighted_density[prevKey] : null;
  const prevArith = prevKey ? data.national.arithmetic_density[prevKey] : null;
  const prevSettlement = prevKey ? data.national.settlement_components[prevKey] : null;

  const zoomBounds = mode === 'story'
    ? (currentStep?.id === 4 ? (step4Part === 'se' ? currentStep.bounds : STEP4_PART2.bounds) : (currentStep?.bounds ?? null))
    : null;
  const showRule500 = mode === 'story' && currentStep?.overlay === 'rule500';
  const showHighways = mode === 'story' && currentStep?.overlay === 'highway';
  const showChernobylOverlay = mode === 'story' && currentStep?.id === 4 && step4Part === 'se';
  const storyValues = storyData ? buildStoryValues(data, storyData, lang) : {};

  return (
    <div className="gv-root">
      <div className="gv-honesty" role="note">
        <strong>{t('Важно: это не независимый подсчёт людей.')}</strong>{' '}
        {t('Клетки взяты из открытого набора Европейской комиссии, а итог по каждому району приведён к официальной статистике. Проще говоря: карта надёжно показывает, где внутри района живут люди, но сколько их всего — это по-прежнему официальная цифра, а не наше измерение.')}
        {' '}
        {t('Проверка независимым спутниковым сенсором (ночные огни) наши выводы не подтвердила — подробности в конце страницы.')}
      </div>

      <div className="gv-mode-switch" role="tablist" aria-label={t('Режим просмотра')}>
        <button role="tab" aria-selected={mode === 'story'} className={mode === 'story' ? 'on' : ''}
          onClick={() => setMode('story')}>
          {storyContent ? storyContent['nav.mode-story'] : t('История')}
        </button>
        <button role="tab" aria-selected={mode === 'free'} className={mode === 'free' ? 'on' : ''}
          onClick={() => setMode('free')}>
          {storyContent ? storyContent['nav.mode-free'] : t('Свободно')}
        </button>
        <MethodDrawer slug="grid" />
      </div>

      <GridMap
        frameUrl={frameUrl}
        boundsLonLat={frameMeta?.bounds_lonlat ?? null}
        metric={metric}
        networkValues={networkValues}
        reducedMotion={reducedMotion}
        showBorders={mode === 'free' && showBorders}
        showCentroidTrack={mode === 'free' && showTrack}
        centroidTrack={data.national.centroid_track}
        centroidUpToYear={year}
        onMapClick={handleMapClick}
        onTerritoryClick={handleTerritoryClick}
        adm1={geoLoaded ? geoRef.current!.adm1 : null}
        adm2={geoLoaded ? geoRef.current!.adm2 : null}
        zoomBounds={zoomBounds}
        rule500FrameUrl={storyData ? storyData.rule500_frame : null}
        showRule500={showRule500}
        highwaysGeojson={highwaysGeojson}
        showHighways={showHighways}
        chernobylZones={storyData?.chernobyl_zone_class ?? null}
        showChernobyl={showChernobylOverlay}
      />

      {mode === 'story' && currentStep && (
        <>
          {currentStep.scrub && (
            <div className="gv-story-play-row">
              <button className="play-btn gv-play-big" onClick={() => {
                if (!playing && idx >= playEndIdx) setIdx(ALL_YEARS.indexOf(currentStep.scrub!.fromYear));
                setPlaying((p) => !p);
              }} aria-label={playing ? t('пауза') : t('воспроизвести')}>
                {playing ? '❚❚' : '▶'}
              </button>
              <span className="gv-year-label">{year}{isForecast && <span className="urban-badge model">{t('МОДЕЛЬ')}</span>}</span>
            </div>
          )}
          <StoryPanel
            step={storyStepIdx + 1}
            content={storyContent}
            values={storyValues}
            onNext={() => setStoryStepIdx((i) => Math.min(i + 1, STORY_STEPS.length - 1))}
            onPrev={() => setStoryStepIdx((i) => Math.max(i - 1, 0))}
            onShare={handleShareStep}
            step4Part={step4Part}
            onShowSecondPart={() => setStep4Part('west')}
            scenario={scenario}
            variant={variant}
            onScenario={setScenario}
            onVariant={setVariant}
            onFreeMode={goFreeMode}
          />
          {shareCopied && <p className="hint gv-share-copied" role="status">{t('Ссылка скопирована')}</p>}
        </>
      )}

      {mode === 'free' && (
        <>
          <div className="gv-play-row">
            <button className="play-btn gv-play-big" onClick={() => {
              if (!playing && idx >= ALL_YEARS.length - 1) setIdx(0);
              setPlaying((p) => !p);
            }} aria-label={playing ? t('пауза') : t('воспроизвести')}>
              {playing ? '❚❚' : '▶'}
            </button>
            <span className="gv-play-label">
              {playing ? t('❚❚ Пауза') : t('Показать, как менялось — 75 лет за 11 секунд')}
            </span>
          </div>

          <div className="gv-slider-zone">
            <div className="gv-slider-merged">
              <div className="gv-slider-bg" aria-hidden="true">
                <div className="gv-slider-observed" style={{ width: `${(ALL_YEARS.indexOf(2020) / (ALL_YEARS.length - 1)) * 100}%` }} />
                <div className="gv-slider-model" style={{ width: `${100 - (ALL_YEARS.indexOf(2020) / (ALL_YEARS.length - 1)) * 100}%` }}>
                  {t('модель')}
                </div>
                {ALL_YEARS.map((y) => (
                  <span key={y} className={`gv-slider-node${y > 2020 ? ' model' : ''}`} style={{ left: `${(ALL_YEARS.indexOf(y) / (ALL_YEARS.length - 1)) * 100}%` }} title={String(y)} />
                ))}
              </div>
              <input
                className="gv-range-overlay"
                type="range" min={0} max={ALL_YEARS.length - 1} step={1} value={idx}
                disabled={metric === 'network'}
                aria-label={t('Год')}
                onChange={(e) => { pauseUser(); setIdx(parseInt(e.target.value, 10)); }}
              />
            </div>
            <div className="gv-year-label">{year}{isForecast && <span className="urban-badge model">{t('МОДЕЛЬ')}</span>}</div>
            {metric === 'network' && (
              <p className="hint gv-network-note">{t('Дороги — снимок 2026 года, временной ползунок для этого показателя недоступен.')}</p>
            )}
            {snapNotice && <p className="hint gv-snap-notice" role="status">{snapNotice}</p>}
          </div>

          <div className="gv-toolbar">
            <div className="gv-metric-switch" role="group" aria-label={t('Показатель')}>
              {(['pop', 'density', 'network'] as const).map((m) => (
                <button key={m} className={`btn${metric === m ? ' active' : ''}`}
                  aria-pressed={metric === m}
                  onMouseEnter={() => setHoveredHint(METRIC_HINT_RU[m])}
                  onMouseLeave={() => setHoveredHint(null)}
                  onFocus={() => setHoveredHint(METRIC_HINT_RU[m])}
                  onBlur={() => setHoveredHint(null)}
                  onClick={() => { pauseUser(); setMetric(m); }}>
                  {t(METRIC_RU[m])}
                </button>
              ))}
            </div>
            <label className="gv-toggle"
              onMouseEnter={() => setHoveredHint(BORDERS_HINT_RU)} onMouseLeave={() => setHoveredHint(null)}>
              <input type="checkbox" checked={showBorders} onChange={(e) => { pauseUser(); setShowBorders(e.target.checked); }} />
              {t('Границы районов')}
            </label>
            <button className={`btn${showTrack ? ' active' : ''}`} aria-pressed={showTrack}
              onMouseEnter={() => setHoveredHint(TRACK_HINT_RU)} onMouseLeave={() => setHoveredHint(null)}
              onFocus={() => setHoveredHint(TRACK_HINT_RU)} onBlur={() => setHoveredHint(null)}
              onClick={() => { pauseUser(); setShowTrack((v) => !v); }}>
              {t('Центр масс населения')}
            </button>
          </div>
          <p className="hint gv-toolbar-hint" aria-live="polite">
            {t(hoveredHint ?? METRIC_HINT_RU[metric])}
          </p>

          <div className="gv-legend" aria-label={t('Легенда')}>
            {metric === 'pop' && (
              <>
                <span className="gv-legend-title">{t('людей на км²:')}</span>
                {['0', '10', '100', '1000', '5000+'].map((v) => <span key={v} className="gv-legend-tick">{v}</span>)}
                <span className="hint gv-legend-note">{t('шкала нелинейная (γ = 0,92), верх обрезан на 5000 — иначе Минск засветил бы всю палитру')}</span>
              </>
            )}
            {metric === 'density' && frameMeta && (
              <>
                {frameMeta.density_classes.map((c) => (
                  <span key={c.label} className="gv-legend-row">
                    <span className="gv-legend-swatch" style={{ background: c.color }} />
                    {t(c.label)} <span className="hint">({c.min}{c.max != null ? `–${c.max}` : '+'} {t('чел/км²')})</span>
                  </span>
                ))}
              </>
            )}
            {metric === 'network' && (
              <>
                {networkLegendStops().map((s) => (
                  <span key={s.label} className="gv-legend-row">
                    <span className="gv-legend-swatch" style={{ background: s.color }} />
                    {s.label} {t('км/1000 чел.')}
                  </span>
                ))}
                <span className="hint gv-legend-note">{t('снимок OpenStreetMap на 2026 год, истории сети у нас нет')}</span>
              </>
            )}
          </div>

          {isForecast && (
            <div className="gv-scn-switch">
              <div role="group" aria-label={t('Сценарий')}>
                {(['base', 'optimistic', 'negative'] as const).map((s) => (
                  <button key={s} className={`btn${scenario === s ? ' active' : ''}`}
                    aria-pressed={scenario === s}
                    onMouseEnter={() => setHoveredHint(SCN_HINT_RU[s])} onMouseLeave={() => setHoveredHint(null)}
                    onClick={() => { pauseUser(); setScenario(s); }}>
                    {t(SCN_RU[s])}
                  </button>
                ))}
              </div>
              <div role="group" aria-label={t('Вариант прогноза')}>
                {(['A', 'B'] as const).map((v) => (
                  <button key={v} className={`btn${variant === v ? ' active' : ''}`}
                    aria-pressed={variant === v}
                    onMouseEnter={() => setHoveredHint(VARIANT_HINT_RU[v])} onMouseLeave={() => setHoveredHint(null)}
                    onClick={() => { pauseUser(); setVariant(v); }}>
                    {v === 'A' ? t('A — инерция') : t('Б — пригороды/периферия')}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="gv-panel">
            <div className="gv-stat">
              <div className="gv-stat-value">
                {below5 != null ? fmtPct(below5) : '—'}
                <TrendBadge t={trendArrow(below5, prevBelow5)} fmt={(d) => `${d > 0 ? '+' : ''}${(d * 100).toFixed(1)} п.п.`} />
              </div>
              <div className="hint">{t('страны, где живёт меньше 5 человек на км² — фактически пустая территория')}{below1 != null ? ` (${t('из них ниже 1')}: ${fmtPct(below1)})` : ''}</div>
            </div>
            <div className="gv-stat">
              <div className="gv-stat-value">
                {pwDensity != null ? fmtInt(pwDensity) : '—'}
                <TrendBadge t={trendArrow(pwDensity, prevPw)} fmt={(d) => `${d > 0 ? '+' : ''}${fmtInt(d)}`} />
              </div>
              <div className="hint">{t('плотность вокруг среднего жителя — насколько тесно живёт обычный человек')}</div>
            </div>
            <div className="gv-stat">
              <div className="gv-stat-value">
                {arithDensity != null ? arithDensity.toFixed(1) : '—'}
                <TrendBadge t={trendArrow(arithDensity, prevArith)} fmt={(d) => `${d > 0 ? '+' : ''}${d.toFixed(1)}`} />
              </div>
              <div className="hint">{t('если поделить всех жителей на всю площадь страны')}</div>
            </div>
            <div className="gv-stat">
              <div className="gv-stat-value">
                {settlement ? fmtInt(settlement.n_components) : '—'}
                <TrendBadge t={trendArrow(settlement?.n_components, prevSettlement?.n_components)} fmt={(d) => `${d > 0 ? '+' : ''}${fmtInt(d)}`} />
              </div>
              <div className="hint">
                {t('отдельных «островов» расселения — связных пятен, где вообще живут люди')}
                {settlement ? ` — ${t('крупнейший')}: ${fmtPct(settlement.largest_share_of_pop)} ${t('населения на')} ${fmtPct(settlement.largest_share_of_area)} ${t('площади')}` : ''}
              </div>
            </div>
          </div>

          <div className="gv-finding" role="note">
            <strong>{t('Два разных ответа на вопрос «насколько плотно живёт Беларусь».')}</strong>
            <p>
              {t('Если поделить всех жителей на всю площадь страны, получится около')} 45 {t('человек на квадратный километр — и это число за 45 лет почти не изменилось (44,6 в 1975-м, 44,9 в 2020-м). Похоже, что ничего не происходит.')}
            </p>
            <p>
              {t('Но если спросить иначе — «а какая плотность вокруг обычного, среднего жителя?» — ответ за те же годы вырос почти вдвое: с 3 106 до 5 657 человек на квадратный километр. Средний житель Беларуси живёт заметно теснее, чем в 1975 году.')}
            </p>
            <p>
              {t('Противоречия здесь нет. Это два разных процесса, идущих одновременно: территория пустеет, а люди собираются вместе — и собираются быстрее, чем пустеет территория. Доля страны, где живёт меньше пяти человек на квадратный километр, выросла с 71,6% до 74,2%, а к 2050 году по базовому сценарию доходит до 84,9%. Крупнейший связный «остров» расселения в 2020 году вмещает 45,5% населения страны на 10,7% её площади.')}
            </p>
            <p className="hint">
              {t('Рост плотности вокруг среднего жителя к 2050 году (почти втрое от уровня 2020-го) — следствие модельной экстраполяции тренда, а не наблюдение. За этим стоит отдельная находка: внутри района она переконцентрирует население до вдвое сильнее, чем когда-либо наблюдалось за 45 реальных лет (проверка G-9, docs/decisions/INF-15.md D-013) — относитесь к числам 2050 года как к сценарию модели, а не к факту.')}
            </p>
          </div>

          {cell && (
            <div className="gv-cell-card" role="status">
              <button className="gv-cell-close" onClick={() => setCell(null)} aria-label={t('закрыть')}>×</button>
              {cell.exact && cell.value != null ? (
                <p>{year}{isForecast ? ` (${t(SCN_RU[scenario])}, ${variant})` : ''} — <strong>{fmtInt(cell.value)}</strong> {t('человек в клетке 1×1 км')} <span className={`urban-badge${isForecast ? ' model' : ''}`}>{isForecast ? t('модель') : t('данные')}</span></p>
              ) : (
                <p className="hint">{t('Точное число для этой комбинации года/сценария не подгружено — показаны только национальные показатели выше.')}</p>
              )}
            </div>
          )}
          {!cell && !territory && (
            <p className="hint gv-click-hint">
              {t('Нажмите на карту, чтобы узнать, сколько людей живёт в этом квадрате.')}
            </p>
          )}

          {territory && (
            <div className="gv-cell-card" role="status">
              <button className="gv-cell-close" onClick={() => setTerritory(null)} aria-label={t('закрыть')}>×</button>
              <p>
                <strong>{territory.name}</strong> — {territory.value != null ? (
                  <>{territory.value.toFixed(1)} {t('км дороги на 1000 жителей')}</>
                ) : t('данных по сети нет')} <span className="urban-badge">{t('снимок 2026')}</span>
              </p>
            </div>
          )}

          {showTrack && lastTrackPt && (
            <p className="hint gv-track-caption">
              {t('За')} {lastTrackPt.year - visibleTrack[0].year} {t('лет центр тяжести населения сместился на несколько километров в сторону Минска — направление устойчивое, а величина для новейшего периода сопоставима с собственной погрешностью метода (±')}{lastTrackPt.err_km}{t(' км), поэтому мы не подаём её как точную. Узлы 1897 и 1970 построены другим методом (см. методблок) и обведены более широким коридором.')}
            </p>
          )}

          <button className="btn gv-restart-story" onClick={() => { setMode('story'); setStoryStepIdx(0); }}>
            {storyContent ? storyContent['nav.restart'] : t('Смотреть историю с начала')}
          </button>
        </>
      )}

      <div className="gv-chips" aria-label={t('Статус утверждений')}>
        {data.meta.claims.map((cid) => {
          const status = data.meta.claims_status[cid];
          return (
            <span key={cid} className={`gv-chip gv-chip-${status}`}>
              <strong>{t(CLAIM_STATUS_RU[status] ?? status)}</strong> — {t(CLAIM_LABEL_RU[cid] ?? cid)}
            </span>
          );
        })}
      </div>

      <div className="gv-g3-callout" role="note">
        <strong>{t('Что здесь не сходится.')}</strong>{' '}
        {t('В 63.9% районов официальная численность падает, а ночная светимость (независимый спутниковый сенсор) растёт — согласие направления изменений всего')} {g3.pct_agree}% {t('при пороге 70%. Вероятная причина — модернизация освещения (переход на LED) и рост инфраструктурной активности, не связанные с числом жителей; причина установлена не окончательно.')}
      </div>

      {c3?.supports_c3 && (
        <div className="gv-network-callout" role="note">
          <strong>{t('Дороги остаются, плательщики уезжают.')}</strong>{' '}
          {t('Чем сильнее район обезлюдел с 1989 года, тем больше километров дороги приходится на одного оставшегося жителя (коэффициент Спирмена')} {c3.spearman_rho.toFixed(2)}
          {t(', 118 районов, вероятность случайности исчезающе мала).')}
          {g6 && ` ${t('Снимок дорожной сети OpenStreetMap на 2026 год —')} ${fmtInt(g6.osm_total_km)} ${t('км против')} ${fmtInt(g6.official_total_km)} ${t('км официальной статистики (расхождение')} ${Math.abs(g6.delta_pct).toFixed(1)}%, ${t('в пределах допуска).')}`}
        </div>
      )}

      <div className="gv-next" role="note">
        <strong>{t('Смежные материалы.')}</strong>{' '}
        {t('«Цена пустеющей карты» (INF-12) — тот же процесс изнутри городов;')}{' '}
        <a href={lang === 'be' ? '/be/research/urban-overhang' : '/research/urban-overhang'}>{t('открыть')}</a>.{' '}
        {t('«Беларусь из космоса» (INF-08) — независимый спутниковый сенсор, который и обнаружил расхождение выше;')}{' '}
        <a href={lang === 'be' ? '/be/research/nightlights' : '/research/nightlights'}>{t('открыть')}</a>.
      </div>

      <div className="hint src-note">
        {t('Клетки населения — GHS-POP R2023A (Joint Research Centre, Еврокомиссия, CC BY 4.0), эпохи 1975–2020, приведены к официальным рядам Белстата по каждому району. Прогноз клеток 2026–2050 нормирован к районной модели проекта v2026.4. Дороги — снимок OpenStreetMap на 2026 год (классы motorway…tertiary), сверено с данными РУП «Белдорцентр». Ночные огни — VIIRS VNL v2.1 (исследование INF-08). Полные оговорки — в методблоке и в LIMITATIONS.md пакета артефактов.')}
      </div>

      <div className="hint gv-reduced-motion-note" aria-hidden={!reducedMotion}>
        {reducedMotion && t('Системная настройка «уменьшить движение» включена — автовоспроизведение ▶ по-прежнему запускается только вручную, плавный переход между кадрами отключён.')}
      </div>
    </div>
  );
}

function TrendBadge({ t, fmt }: { t: { dir: 'up' | 'down' | 'flat'; delta: number } | null; fmt: (d: number) => string }) {
  if (!t || t.dir === 'flat') return null;
  return (
    <span className={`gv-trend gv-trend-${t.dir}`}>
      {t.dir === 'up' ? '↑' : '↓'} {fmt(t.delta)}
    </span>
  );
}
