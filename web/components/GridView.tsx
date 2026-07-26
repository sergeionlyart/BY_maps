'use client';

/**
 * «Полотно» (INF-15): карта расселения Беларуси по сетке 1 км, 1975-2050,
 * без административных границ (тумблер - по умолчанию выключен).
 *
 * - слайдер 1975-2050 (наблюдаемая часть 1975-2020 / модельная 2026-2050,
 *   визуально разделены - штриховка+подпись на модельной зоне);
 * - переключатель метрики: люди в клетке / плотность-класс / метры сети;
 * - переключатели сценария (2026+) и варианта прогноза A/Б;
 * - кнопка «центр масс населения» - трек с коридором погрешности;
 * - плашка честности - видна без прокрутки, не только в подвале;
 * - клик по клетке - точная история клетки (наблюдаемые годы +
 *   2050:base:A/Б), иначе - только национальный диапазон;
 * - deep-link ?year=&metric=&scenario=&variant=&borders=&track=, дебаунс
 *   350 мс (регресс INF-08/INF-11 - без дебаунса скраббинг ронял историю).
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useT, useLang } from '@/lib/i18n';
import MethodDrawer from './MethodDrawer';
import GridMap from './grid/GridMap';
import {
  useGridData, frameKey, loadCellGrid, cellHasBinary, lonLatToCellIndex,
  cellValue, fmtInt, fmtPct, OBSERVED_YEARS, FORECAST_YEARS,
  type Scenario, type Variant,
} from '@/lib/grid';

const SCN_RU: Record<Scenario, string> = { base: 'базовый', optimistic: 'оптимистичный', negative: 'негативный' };
const METRIC_RU: Record<string, string> = {
  pop: 'Люди в клетке', density: 'Класс плотности', network: 'Метры сети на жителя',
};

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

export default function GridView() {
  const t = useT();
  const lang = useLang();
  const data = useGridData();
  const geoRef = useRef<{ adm1: GeoJSON.FeatureCollection; adm2: GeoJSON.FeatureCollection } | null>(null);
  const [geoLoaded, setGeoLoaded] = useState(false);
  const reducedMotion = useReducedMotion();

  const [year, setYear] = useState(2020);
  const [metric, setMetric] = useState<'pop' | 'density' | 'network'>('pop');
  const [scenario, setScenario] = useState<Scenario>('base');
  const [variant, setVariant] = useState<Variant>('A');
  const [showBorders, setShowBorders] = useState(false);
  const [showTrack, setShowTrack] = useState(false);
  const [cell, setCell] = useState<{ lon: number; lat: number; value: number | null; exact: boolean } | null>(null);
  const initDone = useRef(false);

  useEffect(() => {
    Promise.all([
      fetch('/data/geo/adm1.geojson').then((r) => r.json()),
      fetch('/data/geo/adm2.geojson').then((r) => r.json()),
    ]).then(([adm1, adm2]) => { geoRef.current = { adm1, adm2 }; setGeoLoaded(true); });
  }, []);

  // deep-link: чтение при монтировании
  useEffect(() => {
    if (!data || initDone.current) return;
    initDone.current = true;
    const p = new URLSearchParams(window.location.search);
    const y = parseInt(p.get('year') ?? '', 10);
    if (Number.isFinite(y)) setYear(y);
    const m = p.get('metric');
    if (m === 'pop' || m === 'density' || m === 'network') setMetric(m);
    const s = p.get('scenario') as Scenario | null;
    if (s && ['base', 'optimistic', 'negative'].includes(s)) setScenario(s);
    const v = p.get('variant') as Variant | null;
    if (v === 'A' || v === 'B') setVariant(v);
    if (p.get('borders') === '1') setShowBorders(true);
    if (p.get('track') === '1') setShowTrack(true);
  }, [data]);

  // deep-link: запись, с дебаунсом 350 мс (обязательно - см. докстринг)
  useEffect(() => {
    if (!data) return;
    const id = window.setTimeout(() => {
      const url = new URL(window.location.href);
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
      try { window.history.replaceState(null, '', url); } catch { /* лимит истории - следующая запись догонит */ }
    }, 350);
    return () => window.clearTimeout(id);
  }, [data, year, metric, scenario, variant, showBorders, showTrack]);

  const isForecast = year > 2020;
  const key = data ? frameKey(year, scenario, variant) : null;
  const frameUrl = data && key && data.frames[key] ? data.frames[key] : null;
  const boundsLonLat = useMemo<[number, number, number, number] | null>(() => null, []);
  const [metaBounds, setMetaBounds] = useState<[number, number, number, number] | null>(null);
  useEffect(() => {
    fetch('/data/grid_frames/meta.json').then((r) => r.json()).then((m) => {
      setMetaBounds(m.bounds_lonlat as [number, number, number, number]);
    });
  }, []);

  async function handleMapClick(lon: number, lat: number) {
    if (!data) return;
    setCell({ lon, lat, value: null, exact: false });
    const idx = lonLatToCellIndex(lon, lat, data.grid);
    if (!idx) return;
    if (cellHasBinary(key ?? '')) {
      const arr = await loadCellGrid(key!);
      if (arr) {
        const v = cellValue(arr, idx.row, idx.col, data.grid);
        setCell({ lon, lat, value: v, exact: true });
        return;
      }
    }
    setCell({ lon, lat, value: null, exact: false });
  }

  if (!data) {
    return <p className="hint" role="status">{t('Загрузка данных сетки…')}</p>;
  }

  const below5 = data.national.area_share_below['5'][key ?? String(year)];
  const pwDensity = data.national.population_weighted_density[key ?? String(year)] ?? data.national.population_weighted_density[String(year)];
  const arithDensity = data.national.arithmetic_density[key ?? String(year)] ?? data.national.arithmetic_density[String(year)];
  const settlement = data.national.settlement_components[key ?? String(year)] ?? data.national.settlement_components[String(year)];
  const g3 = data.validation.g3_nightlights_crosscheck;

  return (
    <div className="gv-root">
      <div className="gv-honesty" role="note">
        <strong>{t('Важно.')}</strong>{' '}
        {t('Карта построена дазиметрически из официальной статистики (GHS-POP), а не измерена независимо — она достоверно показывает рисунок расселения, но не является независимой проверкой численности населения.')}
        {' '}
        {t('Проверка по независимому сенсору (ночные огни) не подтвердила совпадение направления изменений — выводы о концентрации населения и росте пустеющей территории публикуются как открытый вопрос.')}
      </div>

      <div className="gv-toolbar">
        <div className="gv-metric-switch" role="group" aria-label={t('Показатель')}>
          {(['pop', 'density', 'network'] as const).map((m) => (
            <button key={m} className={`btn${metric === m ? ' active' : ''}`}
              aria-pressed={metric === m} onClick={() => setMetric(m)}>
              {t(METRIC_RU[m])}
            </button>
          ))}
        </div>
        <label className="gv-toggle">
          <input type="checkbox" checked={showBorders} onChange={(e) => setShowBorders(e.target.checked)} />
          {t('Границы районов')}
        </label>
        <button className={`btn${showTrack ? ' active' : ''}`} aria-pressed={showTrack}
          onClick={() => setShowTrack((v) => !v)}>
          {t('Центр масс населения')}
        </button>
        <MethodDrawer slug="grid" />
      </div>

      <GridMap
        frameUrl={frameUrl}
        boundsLonLat={metaBounds}
        showBorders={showBorders}
        showCentroidTrack={showTrack}
        centroidTrack={data.national.centroid_track}
        centroidUpToYear={year}
        onMapClick={handleMapClick}
        adm1={geoLoaded ? geoRef.current!.adm1 : null}
        adm2={geoLoaded ? geoRef.current!.adm2 : null}
      />

      <div className="gv-slider-zone">
        <input
          className="nlv3-range gv-range"
          type="range" min={1975} max={2050} step={1} value={year}
          aria-label={t('Год')}
          onChange={(e) => setYear(parseInt(e.target.value, 10))}
        />
        <div className="gv-slider-track">
          <div className="gv-slider-observed" style={{ width: `${((2020 - 1975) / (2050 - 1975)) * 100}%` }} />
          <div className="gv-slider-model" style={{ width: `${((2050 - 2020) / (2050 - 1975)) * 100}%` }}>
            {t('модель')}
          </div>
        </div>
        <div className="gv-year-label">{year}{isForecast && <span className="urban-badge model">{t('МОДЕЛЬ')}</span>}</div>
      </div>

      {isForecast && (
        <div className="gv-scn-switch">
          <div role="group" aria-label={t('Сценарий')}>
            {(['base', 'optimistic', 'negative'] as const).map((s) => (
              <button key={s} className={`btn${scenario === s ? ' active' : ''}`}
                aria-pressed={scenario === s} onClick={() => setScenario(s)}>
                {t(SCN_RU[s])}
              </button>
            ))}
          </div>
          <div role="group" aria-label={t('Вариант прогноза')}>
            {(['A', 'B'] as const).map((v) => (
              <button key={v} className={`btn${variant === v ? ' active' : ''}`}
                aria-pressed={variant === v} onClick={() => setVariant(v)}>
                {v === 'A' ? t('A — инерция') : t('Б — пригороды/периферия')}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="gv-panel">
        <div className="gv-stat">
          <div className="gv-stat-value">{below5 != null ? fmtPct(below5) : '—'}</div>
          <div className="hint">{t('территории с плотностью ниже 5 чел/км²')}</div>
        </div>
        <div className="gv-stat">
          <div className="gv-stat-value">{pwDensity != null ? fmtInt(pwDensity) : '—'}</div>
          <div className="hint">{t('плотность вокруг среднего жителя, чел/км²')}</div>
        </div>
        <div className="gv-stat">
          <div className="gv-stat-value">{arithDensity != null ? arithDensity.toFixed(1) : '—'}</div>
          <div className="hint">{t('обычная (арифметическая) плотность страны, чел/км²')}</div>
        </div>
        <div className="gv-stat">
          <div className="gv-stat-value">{settlement ? fmtInt(settlement.n_components) : '—'}</div>
          <div className="hint">{t('«островов» расселения')}</div>
        </div>
      </div>

      <div className="gv-g3-callout" role="note">
        <strong>{t('Что здесь не сходится.')}</strong>{' '}
        {t('В 63.9% районов официальная численность падает, а ночная светимость (независимый спутниковый сенсор) растёт — согласие направления изменений всего')} {g3.pct_agree}% {t('при пороге 70%. Вероятная причина — модернизация освещения (переход на LED) и рост инфраструктурной активности, не связанные с числом жителей; причина установлена не окончательно.')}
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

      <div className="hint gv-reduced-motion-note" aria-hidden={!reducedMotion}>
        {reducedMotion && t('Анимация перелистывания отключена (системная настройка «уменьшить движение»).')}
      </div>
    </div>
  );
}
