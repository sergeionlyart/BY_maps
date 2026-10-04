'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { DataFile } from '@/lib/types';
import { useLang, useT } from '@/lib/i18n';
import { DIV_MID, DIV_NEG, DIV_POS, SEQ } from '@/lib/scales';
import MethodDrawer from './MethodDrawer';

/* ------------------------------------------------------------------ типы */

interface Row {
  ru: string; be: string; oblast: string;
  min_oblcenter: number | null; min_minsk: number | null;
  dO_9020: number | null; dG_9020: number | null; d_9020: number | null;
  dO_1319: number; dL_1319: number; dO_2124: number; dL_2124: number;
  series: { O: Record<string, number>; G: Record<string, number>;
            Oy: Record<string, number>; L: Record<string, number> };
}
interface H { rho?: number; p?: number; verdict: string; [k: string]: unknown }
interface SensorsData {
  version: string;
  seams: [number, number][];
  territories: Record<string, Row>;
  findings: { H1: H & { n: number; robust_2000_2020_rho: number };
              H2: H & { robust_dmsp_rho: number };
              H3: H; H4: H & { ratio: number; threshold: number } };
  summary: { n_og: number; sign_agree_OG: number;
             minsk_share: { O: Record<string, number>; G: Record<string, number> } };
  posthoc: { level_rho_light_vs_pop: Record<string, number>;
             light_up_pop_down_1319: number; median_dO_1319: number;
             median_dL_1319: number; light_change_persistence_rho: number;
             light_change_vs_initial_share_rho: number;
             belts_minsk: { belt: string; n: number; median_dO: number; median_dL: number }[] };
}
interface GeoFeature {
  properties: { id: string };
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][] };
}
type Metric = 'og' | 'lo';

/* -------------------------------------------------------------- шкалы */

/** Расхождение двух датчиков в изменении доли (лог-единицы), полярность
 *  вокруг нуля: дивергентная шкала проекта (lib/scales.ts), нейтраль — 0. */
const BREAKS = [-0.3, -0.15, -0.05, 0.05, 0.15, 0.3];
const COLORS = [DIV_NEG[3], DIV_NEG[2], DIV_NEG[0], DIV_MID, DIV_POS[0], DIV_POS[2], DIV_POS[3]];
const LABELS = ['< −26 %', '−26…−14 %', '−14…−5 %', '±5 %', '+5…16 %', '+16…35 %', '> +35 %'];

const pct = (d: number) => (Math.exp(d) - 1) * 100;      // лог-изменение -> %
const fmtPct = (d: number) => `${pct(d) >= 0 ? '+' : ''}${pct(d).toFixed(1)} %`;

function colorFor(v: number | null | undefined): string {
  if (v == null) return 'var(--surface-2)';
  let i = 0;
  while (i < BREAKS.length && v >= BREAKS[i]) i++;
  return COLORS[i];
}

/** Серии датчиков на графике района — категориальные цвета проекта. */
const C_OFF = SEQ[6];
const C_GHS = DIV_NEG[2];
const C_LIGHT = '#c8a33a';

function useWidth(initial: number) {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(initial);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (el.clientWidth > 40) setW(el.clientWidth);
    const ro = new ResizeObserver(() => el.clientWidth > 40 && setW(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

/* ------------------------------------------------------------ хороплет */

function Choro({ geo, values, names, selected, onSelect }: {
  geo: GeoFeature[]; values: Record<string, number | null>;
  names: Record<string, string>; selected: string | null; onSelect: (id: string) => void;
}) {
  const t = useT();
  const [ref, width] = useWidth(640);
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);
  const { paths, height } = useMemo(() => {
    let minLon = 180, maxLon = -180, minLat = 90, maxLat = -90;
    const each = (f: GeoFeature, cb: (r: number[][]) => void) => {
      const polys = f.geometry.type === 'Polygon'
        ? [f.geometry.coordinates as number[][][]] : (f.geometry.coordinates as number[][][][]);
      for (const p of polys) for (const r of p) cb(r);
    };
    for (const f of geo) each(f, (r) => { for (const [lo, la] of r) {
      if (lo < minLon) minLon = lo; if (lo > maxLon) maxLon = lo;
      if (la < minLat) minLat = la; if (la > maxLat) maxLat = la; } });
    const kx = Math.cos(((minLat + maxLat) / 2) * Math.PI / 180);
    const pad = 6;
    const sc = (width - pad * 2) / ((maxLon - minLon) * kx);
    const h = Math.round((maxLat - minLat) * sc) + pad * 2;
    const X = (lo: number) => pad + (lo - minLon) * kx * sc;
    const Y = (la: number) => pad + (maxLat - la) * sc;
    return {
      height: h,
      paths: geo.map((f) => {
        let d = '';
        each(f, (r) => { d += r.map(([lo, la], i) => `${i ? 'L' : 'M'}${X(lo).toFixed(1)} ${Y(la).toFixed(1)}`).join('') + 'Z'; });
        return { id: f.properties.id, d };
      }),
    };
  }, [geo, width]);
  return (
    <div className="chart-svg-wrap gv-map" ref={ref}>
      <svg width={width} height={height} role="img" aria-label={t('Карта расхождения датчиков по районам')}>
        {paths.map((p) => (
          <path key={p.id} d={p.d} fill={colorFor(values[p.id])}
            stroke={p.id === selected ? 'var(--ink)' : 'var(--surface-1)'}
            strokeWidth={p.id === selected ? 1.8 : 0.5} style={{ cursor: 'pointer' }}
            onPointerEnter={(e) => setHover({ id: p.id, x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY })}
            onPointerLeave={() => setHover(null)} onClick={() => onSelect(p.id)} />
        ))}
      </svg>
      {hover && (
        <div className="chart-tooltip" style={{ left: Math.min(hover.x + 12, width - 200), top: Math.max(hover.y - 10, 0) }}>
          <div className="ct-row"><span className="ct-val">{names[hover.id] ?? hover.id}</span></div>
          <div className="ct-year">{values[hover.id] == null ? t('нет данных') : fmtPct(values[hover.id]!)}</div>
        </div>
      )}
    </div>
  );
}

/* ----------------------------------------------------------- рассеяние */

function Scatter({ pts, xLabel, yLabel, names, selected, onSelect }: {
  pts: { id: string; x: number; y: number }[]; xLabel: string; yLabel: string;
  names: Record<string, string>; selected: string | null; onSelect: (id: string) => void;
}) {
  const [ref, width] = useWidth(420);
  const [hover, setHover] = useState<string | null>(null);
  const height = 300;
  const M = { top: 10, right: 12, bottom: 40, left: 48 };
  const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
  const pad = (a: number, b: number) => [a - (b - a) * 0.06, b + (b - a) * 0.06];
  const [x0, x1] = pad(Math.min(...xs, 0), Math.max(...xs, 0));
  const [y0, y1] = pad(Math.min(...ys, 0), Math.max(...ys, 0));
  const iw = width - M.left - M.right, ih = height - M.top - M.bottom;
  const X = (v: number) => M.left + ((v - x0) / (x1 - x0)) * iw;
  const Y = (v: number) => M.top + ih - ((v - y0) / (y1 - y0)) * ih;
  const ticks = (a: number, b: number) => [-0.4, -0.2, 0, 0.2, 0.4, 0.6].filter((v) => v >= a && v <= b);
  const hp = hover ? pts.find((p) => p.id === hover) : null;
  return (
    <div className="chart-svg-wrap" ref={ref}>
      <svg width={width} height={height} role="img" aria-label={`${xLabel} / ${yLabel}`}>
        <line x1={X(0)} x2={X(0)} y1={M.top} y2={M.top + ih} stroke="var(--baseline)" />
        <line x1={M.left} x2={width - M.right} y1={Y(0)} y2={Y(0)} stroke="var(--baseline)" />
        {ticks(x0, x1).map((v) => (
          <text key={'x' + v} x={X(v)} y={height - 24} textAnchor="middle" fontSize="10" fill="var(--muted)">{fmtPct(v).replace(' ', '')}</text>
        ))}
        {ticks(y0, y1).map((v) => (
          <text key={'y' + v} x={M.left - 6} y={Y(v) + 3} textAnchor="end" fontSize="10" fill="var(--muted)">{fmtPct(v).replace(' ', '')}</text>
        ))}
        <text x={M.left + iw / 2} y={height - 6} textAnchor="middle" fontSize="10.5" fill="var(--ink-2)">{xLabel}</text>
        <text x={12} y={M.top + ih / 2} textAnchor="middle" fontSize="10.5" fill="var(--ink-2)"
          transform={`rotate(-90 12 ${M.top + ih / 2})`}>{yLabel}</text>
        {pts.map((p) => {
          const on = p.id === selected || p.id === hover;
          return (
            <circle key={p.id} cx={X(p.x)} cy={Y(p.y)} r={on ? 6 : 4}
              fill={on ? 'var(--accent)' : SEQ[5]} fillOpacity={on ? 1 : 0.7}
              stroke="var(--surface-1)" strokeWidth={1.5} style={{ cursor: 'pointer' }}
              onPointerEnter={() => setHover(p.id)} onPointerLeave={() => setHover(null)}
              onClick={() => onSelect(p.id)} />
          );
        })}
      </svg>
      {hp && (
        <div className="chart-tooltip" style={{ left: Math.min(X(hp.x) + 12, width - 200), top: Y(hp.y) - 12 }}>
          <div className="ct-row"><span className="ct-val">{names[hp.id] ?? hp.id}</span></div>
          <div className="ct-year">{fmtPct(hp.x)} · {fmtPct(hp.y)}</div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------ три датчика у одного района */

function SensorLines({ row, seams }: { row: Row; seams: [number, number][] }) {
  const t = useT();
  const [ref, width] = useWidth(560);
  const height = 280;
  const M = { top: 14, right: 14, bottom: 34, left: 52 };
  const toPts = (s: Record<string, number>) =>
    Object.entries(s).map(([y, v]) => [+y, v * 100] as [number, number]).sort((a, b) => a[0] - b[0]);
  const off = toPts(row.series.O).filter(([y]) => y < 2004).concat(toPts(row.series.Oy));
  const ghs = toPts(row.series.G);
  const light = toPts(row.series.L);
  const all = [...off, ...ghs, ...light];
  const x0 = 1975, x1 = 2024;
  const vmax = Math.max(...all.map((p) => p[1])) * 1.1;
  const iw = width - M.left - M.right, ih = height - M.top - M.bottom;
  const X = (y: number) => M.left + ((y - x0) / (x1 - x0)) * iw;
  const Y = (v: number) => M.top + ih - (v / vmax) * ih;
  // линия света рвётся на стыках сенсоров — их нельзя соединять
  const seg = (pts: [number, number][], breakAt: number[]) => {
    let d = '';
    pts.forEach(([y, v], i) => {
      const brk = i > 0 && breakAt.some((b) => pts[i - 1][0] <= b && y > b);
      d += `${i === 0 || brk ? 'M' : 'L'}${X(y).toFixed(1)} ${Y(v).toFixed(1)}`;
    });
    return d;
  };
  const seamYears = seams.map((s) => s[0]);
  const yt = [0, vmax / 2, vmax].map((v) => +v.toPrecision(2));
  return (
    <div className="chart-svg-wrap" ref={ref}>
      <svg width={width} height={height} role="img" aria-label={t('Доля района в стране по трём датчикам')}>
        {yt.map((v) => (
          <g key={v}>
            <line x1={M.left} x2={width - M.right} y1={Y(v)} y2={Y(v)} stroke="var(--grid)" strokeDasharray="4 3" />
            <text x={M.left - 6} y={Y(v) + 3} textAnchor="end" fontSize="10" fill="var(--muted)">{v.toFixed(2)} %</text>
          </g>
        ))}
        {seamYears.map((s) => (
          <g key={s}>
            <line x1={X(s + 0.5)} x2={X(s + 0.5)} y1={M.top} y2={M.top + ih} stroke="var(--muted)" strokeDasharray="2 3" />
            <text x={X(s + 0.5) + 3} y={M.top + 10} fontSize="9" fill="var(--muted)">{t('стык')}</text>
          </g>
        ))}
        {[1980, 1990, 2000, 2010, 2020].map((y) => (
          <text key={y} x={X(y)} y={height - 14} textAnchor="middle" fontSize="10" fill="var(--muted)">{y}</text>
        ))}
        <path d={seg(off, [])} fill="none" stroke={C_OFF} strokeWidth={2} />
        <path d={seg(ghs, [])} fill="none" stroke={C_GHS} strokeWidth={2} />
        <path d={seg(light, seamYears)} fill="none" stroke={C_LIGHT} strokeWidth={2} />
        {ghs.map(([y, v]) => <circle key={'g' + y} cx={X(y)} cy={Y(v)} r={3} fill={C_GHS} />)}
      </svg>
      <div className="chart-legend">
        <span className="gv-legend-row"><span className="gv-legend-swatch" style={{ background: C_OFF }} />{t('официальный ряд')}</span>
        <span className="gv-legend-row"><span className="gv-legend-swatch" style={{ background: C_GHS }} />{t('спутник GHS-POP')}</span>
        <span className="gv-legend-row"><span className="gv-legend-swatch" style={{ background: C_LIGHT }} />{t('ночные огни')}</span>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------- видео */

function Reel() {
  const t = useT();
  const base = useLang() === 'be' ? '/video/reel_sensors_be' : '/video/reel_sensors_ru';
  return (
    <div className="chart-block pen-reel-block">
      <div className="chart-title">{t('Видеоверсия исследования')}</div>
      <video className="pen-reel" src={`${base}.mp4`} poster={`${base}.webp`}
        controls playsInline preload="none" width={1080} height={1920} />
    </div>
  );
}

/* ------------------------------------------------------------- страница */

export default function SensorsView() {
  const t = useT();
  const [data, setData] = useState<SensorsData | null>(null);
  const [geo, setGeo] = useState<GeoFeature[] | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [metric, setMetric] = useState<Metric>('lo');
  const [sel, setSel] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return new URLSearchParams(window.location.search).get('sel');
  });

  useEffect(() => {
    fetch('/data/sensors.json').then((r) => r.json()).then(setData);
    fetch('/data/geo/adm2.geojson').then((r) => r.json()).then((g) => setGeo(
      g.features.filter((f: GeoFeature) => f.properties.id.startsWith('r-'))));
    fetch('/data/data.json').then((r) => r.json()).then((d: DataFile) => {
      const m: Record<string, string> = {};
      for (const x of Object.values(d.territories)) m[x.id] = x.ru;
      setNames(m);
    });
  }, []);

  if (!data || !geo) return <p className="hint">{t('Загрузка данных…')}</p>;

  const T = data.territories, F = data.findings, PH = data.posthoc, S = data.summary;
  const ids = Object.keys(T);
  const values: Record<string, number | null> = {};
  for (const id of ids) {
    values[id] = metric === 'og' ? T[id].d_9020 : T[id].dL_1319 - T[id].dO_1319;
  }
  const select = (id: string) => {
    setSel(id);
    const url = new URL(window.location.href);
    url.searchParams.set('sel', id);
    window.history.replaceState(null, '', url);
  };
  const rec = sel ? T[sel] : null;
  const ptsOG = ids.filter((i) => T[i].dO_9020 != null)
    .map((i) => ({ id: i, x: T[i].dO_9020!, y: T[i].dG_9020! }));
  const ptsOL = ids.map((i) => ({ id: i, x: T[i].dO_1319, y: T[i].dL_1319 }));
  const r2 = (v: number | undefined) => (v ?? 0).toFixed(2);

  const csv = () => {
    const rows = [['район', 'официальный 1990-2020, %', 'спутник 1990-2020, %',
                   'официальный 2013-2019, %', 'свет 2013-2019, %']];
    for (const [id, r] of Object.entries(T)) {
      rows.push([r.ru, r.dO_9020 == null ? '' : pct(r.dO_9020).toFixed(2),
                 r.dG_9020 == null ? '' : pct(r.dG_9020).toFixed(2),
                 pct(r.dO_1319).toFixed(2), pct(r.dL_1319).toFixed(2)]);
      void id;
    }
    const blob = new Blob(['﻿' + rows.map((r) => r.join(';')).join('\n')], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'sensors.csv';
    a.click();
  };

  return (
    <div className="gv-root">
      <div className="controls" style={{ marginBottom: 6 }}>
        <MethodDrawer slug="sensors" />
        <a className="btn" href={`/artifacts/by-maps-sensors-v${data.version}.zip`} download>
          ⬇ {t('Проверяемый пакет (ZIP)')}
        </a>
      </div>

      <div className="gv-honesty" role="note">
        {t('Три из четырёх заранее заданных гипотез опровергнуты. Главное: мы ожидали, что ночные огни подтвердят, куда уходит население, — и это не так. Свет хорошо показывает, где люди живут, но не куда они уходят: за 2013–2019 годы изменение доли района в свете с изменением доли в населении не связано.')}
      </div>

      <div className="stat-row">
        <div className="stat-tile">
          <div className="st-label">{t('Статистика и спутник согласны')}</div>
          <div className="st-value">ρ = {r2(F.H1.rho)}</div>
          <div className="st-delta">{t('изменение доли районов, 1990–2020; знак совпадает в')} {S.sign_agree_OG} {t('из')} {S.n_og}</div>
        </div>
        <div className="stat-tile">
          <div className="st-label">{t('Свет и население')}</div>
          <div className="st-value">{r2(PH.level_rho_light_vs_pop['2019'])} / {r2(F.H2.rho)}</div>
          <div className="st-delta">{t('ρ по уровням (2019) / ρ по изменениям (2013–2019)')}</div>
        </div>
        <div className="stat-tile">
          <div className="st-label">{t('Свет растёт, люди уходят')}</div>
          <div className="st-value">{PH.light_up_pop_down_1319} {t('из')} 118</div>
          <div className="st-delta">{t('районов, 2013–2019: доля в свете выросла, доля в населении упала')}</div>
        </div>
      </div>

      <div className="gv-toolbar">
        <div className="gv-metric-switch" role="group" aria-label={t('Показатель')}>
          <button className={`btn${metric === 'lo' ? ' active' : ''}`} aria-pressed={metric === 'lo'}
            onClick={() => setMetric('lo')}>{t('Свет против населения, 2013–2019')}</button>
          <button className={`btn${metric === 'og' ? ' active' : ''}`} aria-pressed={metric === 'og'}
            onClick={() => setMetric('og')}>{t('Статистика против спутника, 1990–2020')}</button>
        </div>
      </div>

      <div className="grid-2">
        <div className="chart-block">
          <div className="chart-title">
            {metric === 'lo'
              ? t('Насколько доля района в свете изменилась сильнее, чем доля в населении: синее — свет обогнал людей, красное — отстал')
              : t('Насколько доля района по официальному ряду изменилась сильнее, чем по спутнику: синее — статистика «оптимистичнее» спутника, красное — наоборот')}
          </div>
          <Choro geo={geo} values={values} names={names} selected={sel} onSelect={select} />
          <div className="gv-legend" aria-label={t('Легенда')}>
            {COLORS.map((c, i) => (
              <span key={c + i} className="gv-legend-row"><span className="gv-legend-swatch" style={{ background: c }} />{LABELS[i]}</span>
            ))}
            <span className="hint gv-legend-note">{t('разница изменений доли двух датчиков; серый — датчики согласны в пределах ±5 %')}</span>
          </div>
        </div>
        <div className="chart-block">
          <div className="chart-title">
            {rec ? `${names[sel!] ?? sel}: ${t('доля в стране по трём датчикам')}` : t('Выберите район — покажем все три датчика сразу')}
          </div>
          {rec ? <SensorLines row={rec} seams={data.seams} /> : (
            <p className="hint">{t('Все три линии — доля района в стране, в процентах, на одной оси. Линия огней разорвана на стыках сенсоров: 2011/2012 и 2020/2021 — через них сравнивать нельзя.')}</p>
          )}
        </div>
      </div>

      <div className="grid-2">
        <div className="chart-block">
          <div className="chart-title">{t('H1: статистика и спутник, 1990–2020 — каждая точка район')}</div>
          <Scatter pts={ptsOG} xLabel={t('официальный ряд: изменение доли')} yLabel={t('спутник: изменение доли')}
            names={names} selected={sel} onSelect={select} />
        </div>
        <div className="chart-block">
          <div className="chart-title">{t('H2: население и свет, 2013–2019 — облако без наклона')}</div>
          <Scatter pts={ptsOL} xLabel={t('официальный ряд: изменение доли')} yLabel={t('ночные огни: изменение доли')}
            names={names} selected={sel} onSelect={select} />
        </div>
      </div>

      <div className="chart-block">
        <div className="chart-title">{t('Четыре заранее заданных утверждения и что с ними стало')}</div>
        <div className="gv-chips">
          <span className="gv-chip gv-chip-verified">
            {t('H1 подтверждена')}: {t('статистика и спутник согласны, ρ =')} {r2(F.H1.rho)} ({t('порог')} 0,60); {t('на 2000–2020')} ρ = {r2(F.H1.robust_2000_2020_rho)}
          </span>
          <span className="gv-chip gv-chip-refuted">
            {t('H2 опровергнута')}: {t('свет не следует за населением, ρ =')} {r2(F.H2.rho)} ({t('порог')} 0,40); {t('на DMSP 1992–2011')} ρ = {r2(F.H2.robust_dmsp_rho)}
          </span>
          <span className="gv-chip gv-chip-refuted">
            {t('H3 опровергнута')}: {t('«бумажного населения» периферии нет, ρ с удалённостью =')} {r2(F.H3.rho)}
          </span>
          <span className="gv-chip gv-chip-refuted">
            {t('H4 опровергнута')}: {t('после 2021 расхождение выросло в')} {F.H4.ratio.toFixed(2)} {t('раза при пороге')} {F.H4.threshold.toFixed(2)}
          </span>
        </div>
        <div className="gv-finding">
          <strong>{t('Почему H2 опровергнута — пост-хок.')}</strong>{' '}
          {t('Эти расчёты сделаны после получения данных и гипотезу не подтверждают. По уровням свет и население согласны: ρ =')}{' '}
          {Object.entries(PH.level_rho_light_vs_pop).map(([y, v], i) => <span key={y}>{i ? ', ' : ''}{v.toFixed(2)} ({y})</span>)}.{' '}
          {t('По изменениям — нет: в медианном районе доля в населении')} {fmtPct(PH.median_dO_1319)}, {t('доля в свете')} {fmtPct(PH.median_dL_1319)}.{' '}
          {t('Изменения света антиперсистентны (ρ =')} {PH.light_change_persistence_rho.toFixed(2)}) {t('и сильнее у исходно тусклых районов (ρ =')} {PH.light_change_vs_initial_share_rho.toFixed(2)}){t(': свет растекается по стране, люди концентрируются.')}
        </div>
      </div>

      <Reel />

      <div className="controls" style={{ marginTop: 8 }}>
        <button className="btn gv-raion-table-csv" onClick={csv}>⬇ {t('Таблица всех 118 районов (CSV)')}</button>
      </div>

      <p className="src-note">
        {t('Сравнение ведётся по долям района в национальном итоге каждого датчика: так гасится общий уровень спутниковой модели и калибровка сенсора огней. GHS-POP не полностью независим от переписи — он раскладывает переписные итоги по застройке. Свет измеряет активность, а не людей. Дрибинский район восстановлен в 1989 году и в окне 1990–2020 не участвует. Полные ограничения — в методблоке и LIMITATIONS.md пакета.')}
      </p>
    </div>
  );
}
