'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { DataFile } from '@/lib/types';
import { useLang, useT } from '@/lib/i18n';
import { DIV_MID, DIV_NEG, DIV_POS, SEQ } from '@/lib/scales';
import MethodDrawer from './MethodDrawer';

/* ------------------------------------------------------------------ типы */

interface Summary {
  r2539: number | null;
  r70: number | null;
  gap: number;
  gap_rel: number | null;
  missing: number;
  missing_sex: 'm' | 'f' | null;
  pop2539: number;
}
interface DecompRow {
  m: { start: number; expected: number; observed: number; residual: number };
  f: { start: number; expected: number; observed: number; residual: number };
  mortality_gap: number;
  migration_gap: number;
  dominant: 'migration' | 'mortality';
}
interface Territory {
  ru: string;
  be: string;
  oblast: string;
  min_minsk: number | null;
  profile: Record<string, (number | null)[]>;
  summary: Record<string, Summary>;
  forecast_profile: Record<string, (number | null)[]>;
  forecast_summary: Record<string, Record<string, Summary>>;
  onset_year: number | null;
  decomposition: Record<string, DecompRow>;
  h3: { mortality: number; migration: number; dominant: 'migration' | 'mortality' };
}
interface Spike {
  id: string; ru: string; r2539_census_perimeter: number;
  peak_group: string; peak_ratio: number; pop2539: number;
  top_locality_share_pct: number;
}
interface SexRatioData {
  version: string;
  code: string;
  age_groups: string[];
  census_years: number[];
  node_years: number[];
  core_scenario: string;
  country: { sex_ratio_2019: number | null };
  female_surplus_2019: {
    n: number; n_male_surplus: number; hosted_city: number;
    minsk_belt_30min: number; other: number; other_by_oblast: Record<string, number>;
  };
  territories: Record<string, Territory>;
  cities: Record<string, { ru: string; be: string; summary: Record<string, Summary> }>;
  findings: {
    H1: { median_r2539_2019: number; spearman_rho: number; spearman_p: number; verdict: string };
    H2: { cities: Record<string, number>; raion_median: number; verdict: string };
    H3: { raions_migration_dominant: number; n: number; verdict: string };
    H4: { max_r70_2019: number; median_r70_2019: number; median_r70_2046: number; verdict: string };
  };
  posthoc: {
    census_perimeter_h1: { median_r2539: number; spearman_rho: number; spearman_p: number };
    belts_median_r2539: { belt: string; n: number; median: number }[];
    size_effect: { spearman_rho: number };
    narrow_age_male_spike: Spike[];
  };
}
interface GeoFeature {
  properties: { id: string };
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][] };
}

type Metric = 'r2539' | 'r70';

/* -------------------------------------------------------------- палитры */

/** Дивергентная шкала вокруг паритета 100 (полярность: кого не хватает).
 *  Тёплая ветвь — не хватает женщин, холодная — не хватает мужчин,
 *  нейтральный серый на паритете. Шкала и её шаги — `lib/scales.ts`,
 *  референсная палитра проекта; обе ветви монотонны по светлоте. */
const DIV_BREAKS = [92, 96, 99, 101, 104, 108, 115];
const DIV_COLORS = [DIV_POS[3], DIV_POS[2], DIV_POS[1], DIV_MID,
                    DIV_NEG[1], DIV_NEG[2], DIV_NEG[3]];
const DIV_LABELS = ['< 92', '92–96', '96–99', '99–101', '101–104', '104–108', '> 115'];

/** 70+ — величина, не полярность (все значения далеко ниже 100),
 *  поэтому секвенциальная шкала в один тон. */
const OLD_BREAKS = [34, 38, 42, 46, 50];
const OLD_COLORS = [SEQ[7], SEQ[6], SEQ[4], SEQ[2], SEQ[1], SEQ[0]];
const OLD_LABELS = ['< 34', '34–38', '38–42', '42–46', '46–50', '> 50'];

function colorFor(metric: Metric, v: number | null | undefined): string {
  if (v == null) return 'var(--surface-2)';
  if (metric === 'r70') {
    let i = 0;
    while (i < OLD_BREAKS.length && v >= OLD_BREAKS[i]) i++;
    return OLD_COLORS[i];
  }
  let i = 0;
  while (i < DIV_BREAKS.length - 1 && v >= DIV_BREAKS[i]) i++;
  return DIV_COLORS[Math.min(i, DIV_COLORS.length - 1)];
}

/* ------------------------------------------------------------ хороплет */

function Choro({ geo, values, names, metric, selected, onSelect }: {
  geo: GeoFeature[];
  values: Record<string, number | null>;
  names: Record<string, string>;
  metric: Metric;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const t = useT();
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    // синхронное чтение: первый колбэк ResizeObserver срабатывает не везде
    if (el.clientWidth > 40) setWidth(el.clientWidth);
    const ro = new ResizeObserver(() => el.clientWidth > 40 && setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const { paths, height } = useMemo(() => {
    let minLon = 180, maxLon = -180, minLat = 90, maxLat = -90;
    const eachRing = (f: GeoFeature, cb: (ring: number[][]) => void) => {
      const polys = f.geometry.type === 'Polygon'
        ? [f.geometry.coordinates as number[][][]]
        : (f.geometry.coordinates as number[][][][]);
      for (const poly of polys) for (const ring of poly) cb(ring);
    };
    for (const f of geo) eachRing(f, (ring) => {
      for (const [lon, lat] of ring) {
        if (lon < minLon) minLon = lon; if (lon > maxLon) maxLon = lon;
        if (lat < minLat) minLat = lat; if (lat > maxLat) maxLat = lat;
      }
    });
    const kx = Math.cos(((minLat + maxLat) / 2) * Math.PI / 180);
    const pad = 6;
    const scale = (width - pad * 2) / ((maxLon - minLon) * kx);
    const h = Math.round((maxLat - minLat) * scale) + pad * 2;
    const X = (lon: number) => pad + (lon - minLon) * kx * scale;
    const Y = (lat: number) => pad + (maxLat - lat) * scale;
    const ps = geo.map((f) => {
      let d = '';
      eachRing(f, (ring) => {
        d += ring.map(([lon, lat], i) =>
          `${i ? 'L' : 'M'}${X(lon).toFixed(1)} ${Y(lat).toFixed(1)}`).join('') + 'Z';
      });
      return { id: f.properties.id, d };
    });
    return { paths: ps, height: h };
  }, [geo, width]);

  return (
    <div className="chart-svg-wrap gv-map" ref={wrapRef}>
      <svg width={width} height={height} role="img"
        aria-label={t('Карта: соотношение полов по районам')}>
        {paths.map((p) => (
          <path key={p.id} d={p.d}
            fill={colorFor(metric, values[p.id])}
            stroke={p.id === selected ? 'var(--ink)' : 'var(--surface-1)'}
            strokeWidth={p.id === selected ? 1.8 : 0.5}
            style={{ cursor: 'pointer' }}
            onPointerEnter={(e) => setHover({ id: p.id, x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY })}
            onPointerLeave={() => setHover(null)}
            onClick={() => onSelect(p.id)} />
        ))}
      </svg>
      {hover && (
        <div className="chart-tooltip"
          style={{ left: Math.min(hover.x + 12, width - 190), top: Math.max(hover.y - 10, 0) }}>
          <div className="ct-row"><span className="ct-val">{names[hover.id] ?? hover.id}</span></div>
          <div className="ct-year">
            {values[hover.id] == null ? t('нет данных')
              : `${values[hover.id]!.toFixed(1)} ${t('м на 100 ж')}`}
          </div>
        </div>
      )}
    </div>
  );
}

/* --------------------------------------------- возрастной профиль района */

/** Соотношение полов по 17 возрастным группам: наблюдённая перепись 2019
 *  против выбранного года. Две серии — значит обязательны легенда и
 *  прямые подписи концов; опорная линия паритета 100 рецессивна. */
function AgeProfile({ groups, census, current, currentYear, isModel }: {
  groups: string[];
  census: (number | null)[];
  current: (number | null)[];
  currentYear: number;
  isModel: boolean;
}) {
  const t = useT();
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(560);
  const height = 300;
  const M = { top: 14, right: 16, bottom: 46, left: 42 };

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    if (el.clientWidth > 40) setWidth(el.clientWidth);
    const ro = new ResizeObserver(() => el.clientWidth > 40 && setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const vals = [...census, ...current].filter((v): v is number => v != null);
  const y1 = Math.max(130, Math.ceil(Math.max(...vals, 110) / 10) * 10);
  const y0 = Math.min(20, Math.floor(Math.min(...vals, 90) / 10) * 10);
  const iw = width - M.left - M.right;
  const ih = height - M.top - M.bottom;
  const X = (i: number) => M.left + (i / (groups.length - 1)) * iw;
  const Y = (v: number) => M.top + ih - ((v - y0) / (y1 - y0)) * ih;
  const line = (s: (number | null)[]) => s
    .map((v, i) => (v == null ? null : `${X(i).toFixed(1)} ${Y(v).toFixed(1)}`))
    .filter(Boolean).map((p, i) => `${i ? 'L' : 'M'}${p}`).join('');

  const ticks = [20, 40, 60, 80, 100, 120, 140, 160, 180].filter((v) => v >= y0 && v <= y1);

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg width={width} height={height} role="img"
        aria-label={t('Соотношение полов по возрастным группам')}>
        {ticks.map((v) => (
          <g key={v}>
            <line x1={M.left} x2={width - M.right} y1={Y(v)} y2={Y(v)}
              stroke={v === 100 ? 'var(--baseline)' : 'var(--grid)'}
              strokeDasharray={v === 100 ? undefined : '4 3'} />
            <text x={M.left - 6} y={Y(v) + 3} textAnchor="end" fontSize="10"
              fill="var(--muted)">{v}</text>
          </g>
        ))}
        {/* подпись справа: к старшим возрастам линии уходят далеко ниже 100 */}
        <text x={width - M.right} y={Y(100) - 5} textAnchor="end" fontSize="9.5"
          fill="var(--muted)">
          {t('паритет 100')}
        </text>
        {groups.map((g, i) => (i % 2 === 0 ? (
          <text key={g} x={X(i)} y={height - 28} textAnchor="middle" fontSize="9"
            fill="var(--muted)">{g}</text>
        ) : null))}
        <path d={line(census)} fill="none" stroke={SEQ[6]} strokeWidth={2} />
        <path d={line(current)} fill="none" stroke={DIV_NEG[2]} strokeWidth={2}
          strokeDasharray={isModel ? '5 4' : undefined} />
        {census.map((v, i) => (v == null ? null : (
          <circle key={'c' + i} cx={X(i)} cy={Y(v)} r={3} fill={SEQ[6]}
            stroke="var(--surface-1)" strokeWidth={1} />
        )))}
        {current.map((v, i) => (v == null ? null : (
          <circle key={'f' + i} cx={X(i)} cy={Y(v)} r={3} fill={DIV_NEG[2]}
            stroke="var(--surface-1)" strokeWidth={1} />
        )))}
        <text x={M.left + iw / 2} y={height - 6} textAnchor="middle" fontSize="10.5"
          fill="var(--ink-2)">{t('возрастная группа')}</text>
      </svg>
      <div className="chart-legend">
        <span className="gv-legend-row">
          <span className="gv-legend-swatch" style={{ background: SEQ[6] }} />
          {t('перепись 2019')}
        </span>
        <span className="gv-legend-row">
          <span className="gv-legend-swatch" style={{ background: DIV_NEG[2] }} />
          {currentYear}{isModel ? ` — ${t('модель')}` : ''}
        </span>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------- видеоверсия */

/** Рилс R-S1 (1080×1920, 42 с, RU/BE): tools/render_reel_sexratio.py, все
 *  числа в кадрах — из того же sexratio.json. Здесь — перекодировка CRF 18;
 *  каноническая CBR-версия не версионируется. preload="none": ролик не
 *  тянется, пока читатель не нажал play. */
function Reel() {
  const t = useT();
  const base = useLang() === 'be' ? '/video/reel_sexratio_be' : '/video/reel_sexratio_ru';
  return (
    <div className="chart-block pen-reel-block">
      <div className="chart-title">{t('Видеоверсия исследования — 42 секунды')}</div>
      <video className="pen-reel" src={`${base}.mp4`} poster={`${base}.webp`}
        controls playsInline preload="none" width={1080} height={1920} />
      <p className="hint pen-reel-caption">
        {t('Ролик собран из тех же данных, что и эта страница, и показывает опровержение главной гипотезы отдельной сценой.')}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------- страница */

export default function SexRatioView() {
  const t = useT();
  const [data, setData] = useState<SexRatioData | null>(null);
  const [geo, setGeo] = useState<GeoFeature[] | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [metric, setMetric] = useState<Metric>('r2539');
  const [idx, setIdx] = useState(1);              // по умолчанию перепись 2019
  const [playing, setPlaying] = useState(false);
  const [sel, setSel] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return new URLSearchParams(window.location.search).get('sel');
  });

  useEffect(() => {
    fetch('/data/sexratio.json').then((r) => r.json()).then(setData);
    fetch('/data/geo/adm2.geojson').then((r) => r.json()).then((g) => setGeo(
      g.features.filter((f: GeoFeature) => f.properties.id.startsWith('r-'))));
    fetch('/data/data.json').then((r) => r.json()).then((d: DataFile) => {
      const m: Record<string, string> = {};
      for (const x of Object.values(d.territories)) m[x.id] = x.ru;
      setNames(m);
    });
  }, []);

  const years = useMemo(
    () => (data ? [...data.census_years, ...data.node_years] : []), [data]);

  useEffect(() => {
    if (!playing || !years.length) return;
    const id = setInterval(() => setIdx((i) => {
      if (i >= years.length - 1) { setPlaying(false); return i; }
      return i + 1;
    }), 900);
    return () => clearInterval(id);
  }, [playing, years.length]);

  if (!data || !geo) return <p className="hint">{t('Загрузка данных…')}</p>;

  const year = years[idx];
  const isModel = !data.census_years.includes(year);
  const core = data.core_scenario;

  const summaryFor = (tid: string): Summary | undefined => {
    const tr = data.territories[tid];
    if (!tr) return undefined;
    return isModel
      ? tr.forecast_summary[core]?.[String(year)]
      : tr.summary[String(year)];
  };
  const values: Record<string, number | null> = {};
  for (const tid of Object.keys(data.territories)) {
    values[tid] = summaryFor(tid)?.[metric] ?? null;
  }

  const select = (id: string) => {
    setSel(id);
    const url = new URL(window.location.href);
    url.searchParams.set('sel', id);
    window.history.replaceState(null, '', url);
  };

  const F = data.findings;
  const PH = data.posthoc;
  const rec = sel ? data.territories[sel] : null;
  const recSum = sel ? summaryFor(sel) : undefined;
  // Сравниваемая серия профиля: выбранный год; если выбран сам 2019 —
  // перепись 2009, иначе обе линии совпадут и опорная скроется под второй.
  const cmpYear = year === 2019 ? 2009 : year;
  const profCur = rec
    ? (isModel ? rec.forecast_profile[String(cmpYear)] : rec.profile[String(cmpYear)])
    : null;

  const FS = data.female_surplus_2019;
  const spikeIds = new Set(PH.narrow_age_male_spike.map((s) => s.id));

  const legend = metric === 'r2539'
    ? DIV_COLORS.map((c, i) => ({ color: c, label: DIV_LABELS[i] }))
    : OLD_COLORS.map((c, i) => ({ color: c, label: OLD_LABELS[i] }));

  const csv = () => {
    const rows = [['район', 'м на 100 ж, 25-39', 'м на 100 ж, 70+',
                    'перевес 25-39', 'до Минска, мин', 'год']];
    for (const [tid, tr] of Object.entries(data.territories)) {
      const s = summaryFor(tid);
      rows.push([tr.ru, String(s?.r2539 ?? ''), String(s?.r70 ?? ''),
                 String(s?.gap ?? ''), String(tr.min_minsk ?? ''), String(year)]);
    }
    const blob = new Blob(['﻿' + rows.map((r) => r.join(';')).join('\n')],
      { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `sexratio-${year}.csv`;
    a.click();
  };

  return (
    <div className="gv-root">
      <div className="controls" style={{ marginBottom: 6 }}>
        <MethodDrawer slug="sexratio" />
        <a className="btn" href={`/artifacts/by-maps-sexratio-v${data.version}.zip`} download>
          ⬇ {t('Проверяемый пакет (ZIP)')}
        </a>
      </div>

      <div className="gv-honesty" role="note">
        {t('Главная гипотеза этого исследования опровергнута собственным заранее заданным критерием. Мы предсказывали, что чем дальше район от Минска, тем сильнее мужской перевес в возрасте 25–39. Связь оказалась обратной и значимой: ρ = −0,30 при p = 0,001. Предсказание не смягчено и не удалено — ниже показано, что в данных на самом деле.')}
      </div>

      <div className="stat-row">
        <div className="stat-tile">
          <div className="st-label">{t('Страна, перепись 2019')}</div>
          <div className="st-value">{data.country.sex_ratio_2019?.toFixed(1)}</div>
          <div className="st-delta">{t('мужчин на 100 женщин — во всех возрастах')}</div>
        </div>
        <div className="stat-tile">
          <div className="st-label">{t('Мужской перевес в 25–39')}</div>
          <div className="st-value">{FS.n_male_surplus} {t('из')} {FS.n_male_surplus + FS.n}</div>
          <div className="st-delta">
            {t('районов; в остальных')} {FS.n} {t('— женский')}
          </div>
        </div>
        <div className="stat-tile">
          <div className="st-label">{t('В возрасте 70+')}</div>
          <div className="st-value">{F.H4.median_r70_2019.toFixed(1)}</div>
          <div className="st-delta">
            {t('мужчин на 100 женщин — медиана районов; максимум среди районов')}{' '}
            {F.H4.max_r70_2019.toFixed(1)}, {t('к 2046 медиана растёт до')}{' '}
            {F.H4.median_r70_2046.toFixed(1)}
          </div>
        </div>
      </div>

      <p className="hint">
        {t('Из')} {FS.n} {t('районов с женским перевесом в 25–39')} {FS.hosted_city}{' '}
        {t('включают свой областной город,')} {FS.minsk_belt_30min}{' '}
        {t('— пригороды Минска, ещё')} {FS.other}{' '}
        {t('— прочие районы, из них в Гомельской области —')} {FS.other_by_oblast['BY-HO'] ?? 0}.
      </p>

      <div className="gv-play-row">
        <button className="play-btn gv-play-big" onClick={() => {
          if (!playing && idx >= years.length - 1) setIdx(0);
          setPlaying((p) => !p);
        }} aria-label={playing ? t('пауза') : t('воспроизвести')}>
          {playing ? '❚❚' : '▶'}
        </button>
        <span className="gv-play-label">
          {playing ? t('❚❚ Пауза') : t('Показать, как меняется — от переписи 2009 до 2056 года')}
        </span>
      </div>

      <div className="gv-slider-zone">
        <div className="gv-slider-merged">
          <div className="gv-slider-bg" aria-hidden="true">
            <div className="gv-slider-observed"
              style={{ width: `${(1 / (years.length - 1)) * 100}%` }} />
            <div className="gv-slider-model"
              style={{ width: `${100 - (1 / (years.length - 1)) * 100}%` }}>
              {t('модель')}
            </div>
            {years.map((y, i) => (
              <span key={y}
                className={`gv-slider-node${data.census_years.includes(y) ? '' : ' model'}`}
                style={{ left: `${(i / (years.length - 1)) * 100}%` }} title={String(y)} />
            ))}
          </div>
          <input className="gv-range-overlay" type="range"
            min={0} max={years.length - 1} step={1} value={idx}
            aria-label={t('Год')}
            onChange={(e) => { setPlaying(false); setIdx(parseInt(e.target.value, 10)); }} />
        </div>
        <div className="gv-year-label">
          {year}
          {isModel && <span className="urban-badge model">{t('МОДЕЛЬ')}</span>}
        </div>
      </div>

      <div className="gv-toolbar">
        <div className="gv-metric-switch" role="group" aria-label={t('Показатель')}>
          <button className={`btn${metric === 'r2539' ? ' active' : ''}`}
            aria-pressed={metric === 'r2539'}
            onClick={() => setMetric('r2539')}>{t('Брачный возраст 25–39')}</button>
          <button className={`btn${metric === 'r70' ? ' active' : ''}`}
            aria-pressed={metric === 'r70'}
            onClick={() => setMetric('r70')}>{t('Старшие возрасты 70+')}</button>
        </div>
      </div>

      <div className="grid-2">
        <div className="chart-block">
          <div className="chart-title">
            {metric === 'r2539'
              ? t('Мужчин на 100 женщин в возрасте 25–39: синее — не хватает мужчин, красное — не хватает женщин')
              : t('Мужчин на 100 женщин в возрасте 70+: чем темнее, тем меньше осталось мужчин')}
          </div>
          <Choro geo={geo} values={values} names={names} metric={metric}
            selected={sel} onSelect={select} />
          <div className="gv-legend" aria-label={t('Легенда')}>
            {legend.map((c) => (
              <span key={c.label} className="gv-legend-row">
                <span className="gv-legend-swatch" style={{ background: c.color }} />
                {c.label}
              </span>
            ))}
            <span className="hint gv-legend-note">
              {metric === 'r2539'
                ? t('шкала дивергентная, нейтральный серый — паритет 100; пороги едины для всех лет, чтобы цвет был сопоставим при движении ползунка')
                : t('шкала секвенциальная: все районы далеко ниже паритета, поэтому показана величина, а не полярность')}
            </span>
          </div>
        </div>

        <div className="chart-block">
          <div className="chart-title">
            {rec
              ? `${names[sel!] ?? sel}: ${t('соотношение полов по возрастам')}`
              : t('Выберите район на карте — покажем его возрастной профиль')}
          </div>
          {rec && profCur ? (
            <AgeProfile groups={data.age_groups} census={rec.profile['2019']}
              current={profCur} currentYear={cmpYear} isModel={isModel} />
          ) : (
            <p className="hint">
              {t('Профиль показывает, где именно в возрастах возникает перекос: в молодых возрастах он обычно мужской, после 60 — резко женский.')}
            </p>
          )}
        </div>
      </div>

      {rec && sel && recSum && (
        <>
          <div className="stat-row">
            <div className="stat-tile">
              <div className="st-label">
                {names[sel] ?? sel} · <a href={`/map?sel=${sel}`}>{t('на карту')}</a>
              </div>
              <div className="st-value">{recSum.r2539?.toFixed(1) ?? '—'}</div>
              <div className="st-delta">
                {t('мужчин на 100 женщин в 25–39')}
                {recSum.missing_sex && recSum.missing > 0
                  ? ` · ${t(recSum.missing_sex === 'f' ? 'не хватает женщин:' : 'не хватает мужчин:')} ${Math.round(recSum.missing).toLocaleString('ru-RU')}`
                  : ''}
              </div>
            </div>
            <div className="stat-tile">
              <div className="st-label">{t('Умерли или уехали, 2009 → 2019')}</div>
              <div className="st-value">
                {t(rec.h3.dominant === 'migration' ? 'уехали' : 'умерли')}
              </div>
              <div className="st-delta">
                {t('по когортам, которым в 2019 было 25–39: вклад не-смертностных причин')}{' '}
                {Math.round(rec.h3.migration).toLocaleString('ru-RU')} {t('против')}{' '}
                {Math.round(rec.h3.mortality).toLocaleString('ru-RU')} {t('у смертности')}
              </div>
            </div>
            <div className="stat-tile">
              <div className="st-label">{t('Выход за коридор 85–115')}</div>
              <div className="st-value">{rec.onset_year ?? t('не наступает')}</div>
              <div className="st-delta">
                {t('первый прогнозный узел, в котором соотношение 25–39 выходит за коридор (опорный сценарий)')}
              </div>
            </div>
          </div>
          {spikeIds.has(sel) && (
            <p className="gv-story-caveat" role="note">
              {t('Осторожно: в этом районе мужской перевес сосредоточен в узкой возрастной группе и в одном типе населённых пунктов. Это подпись населения закрытых учреждений, которое перепись учитывает по месту пребывания, а не признак брачного рынка. Проверить состав этого населения по открытым данным нельзя.')}
            </p>
          )}
        </>
      )}

      <div className="chart-block">
        <div className="chart-title">{t('Четыре заранее заданных утверждения и что с ними стало')}</div>
        <div className="gv-chips">
          <span className="gv-chip gv-chip-refuted">
            {t('H1 опровергнута')}: {t('предсказывали усиление мужского перевеса с удалённостью от Минска; ρ =')} {F.H1.spearman_rho.toFixed(3)} (p = {F.H1.spearman_p.toFixed(4)}) — {t('связь обратная')}
          </span>
          <span className="gv-chip gv-chip-verified">
            {t('H2 подтверждена')}: {t('Минск и все пять облцентров ниже паритета')} ({t('Минск')} {F.H2.cities['BY-HM']?.toFixed(1)}, {t('Брест')} {F.H2.cities['c-brest']?.toFixed(1)}) {t('и ниже районной медианы')} {F.H2.raion_median.toFixed(1)}
          </span>
          <span className="gv-chip gv-chip-verified">
            {t('H3 подтверждена')}: {F.H3.raions_migration_dominant} {t('из')} {F.H3.n} {t('районов — вклад не-смертностных причин больше смертностного')}
          </span>
          <span className="gv-chip gv-chip-verified">
            {t('H4 подтверждена')}: {t('в 70+ ни один район не выше 60; медиана')} {F.H4.median_r70_2019.toFixed(1)} → {F.H4.median_r70_2046.toFixed(1)} {t('к 2046')}
          </span>
        </div>
        <div className="gv-finding">
          <strong>{t('Почему H1 опровергнута — пост-хок.')}</strong>{' '}
          {t('Эти расчёты сделаны после получения данных, не были заморожены и гипотезу не подтверждают — они только объясняют форму связи. Медиана соотношения 25–39 по поясам времени до Минска:')}
          {' '}
          {PH.belts_median_r2539.map((b, i) => (
            <span key={b.belt}>
              {i ? ' → ' : ''}{b.median.toFixed(1)} ({b.belt.replace('-', '–')} {t('мин')}, n = {b.n})
            </span>
          ))}
          . {t('Максимум — в среднем поясе, а не на периферии: связь немонотонна, и заданный монотонный тест такую форму поймать не мог. Знак не создан выбором периметра: на переписном периметре ρ =')}{' '}
          {PH.census_perimeter_h1.spearman_rho.toFixed(3)} (p = {PH.census_perimeter_h1.spearman_p.toFixed(4)}). {t('Мужской перевес сильнее в малых районах: ρ по людности =')} {PH.size_effect.spearman_rho.toFixed(3)}.
        </div>
      </div>

      <Reel />

      <div className="chart-block">
        <div className="chart-title">
          {t('Районы с узким возрастным мужским пиком — читать с осторожностью')}
        </div>
        <div className="gv-raion-table-wrap">
          <table className="gv-raion-table">
            <thead>
              <tr>
                <th>{t('район')}</th><th>{t('25–39')}</th>
                <th>{t('пик')}</th><th>{t('в одной местности')}</th>
              </tr>
            </thead>
            <tbody>
              {PH.narrow_age_male_spike.map((s) => (
                <tr key={s.id}>
                  <td>{s.ru}</td>
                  <td>{s.r2539_census_perimeter.toFixed(1)}</td>
                  <td>{s.peak_group}: {s.peak_ratio.toFixed(0)}</td>
                  <td>{s.top_locality_share_pct.toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="hint">
          {t('Это подпись населения закрытых учреждений, а не вывод о брачном рынке: по завендоренным данным состав такого населения не проверяется.')}
        </p>
      </div>

      <div className="controls" style={{ marginTop: 8 }}>
        <button className="btn gv-raion-table-csv" onClick={csv}>
          ⬇ {t('Таблица всех 118 районов за выбранный год (CSV)')}
        </button>
      </div>

      <p className="src-note">
        {t('Соотношение полов в переписи — частное двух посчитанных чисел и модели не требует; 2026 год и далее — продолжение прогноза v2026.4, помечено как модель. Разделение «умерли / уехали» получено методом переписной передвижки на страновых таблицах смертности: в остаток попадают не только миграция, но и недоучёт переписи, поэтому он называется вкладом не-смертностных причин. Разреза внутренней миграции по полу в проекте нет, поэтому независимой внешней проверки у этого разделения тоже нет. Полные ограничения — в методблоке и LIMITATIONS.md пакета.')}
      </p>
    </div>
  );
}
