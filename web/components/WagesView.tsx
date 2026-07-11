'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { DataFile } from '@/lib/types';
import MethodDrawer from './MethodDrawer';

interface WageRec {
  wageRel: number;
  popChange: number;
  cls: string;        // w{0..2}p{0..2}
  resid: number;
  wage2025: number | null;
}

interface WagesData {
  version: string;
  window: [number, number];
  wageYears: [number, number];
  terciles: { wage: [number, number]; pop: [number, number] };
  territories: Record<string, WageRec>;
  regressions: Record<string, { beta: number[]; se: number[]; r2: number; n: number }>;
  outliers: string[];
  minskWage: Record<string, number>;
}

interface GeoFeature {
  properties: { id: string };
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][] };
}

/** Биваритная палитра 3x3 (Stevens teal x purple):
 *  строки - динамика населения (убыль -> рост), столбцы - дифференциал. */
const BIVAR = [
  ['#e8e8e8', '#ace4e4', '#5ac8c8'],  // p0: убыль
  ['#dfb0d6', '#a5add3', '#5698b9'],  // p1
  ['#be64ac', '#8c62aa', '#3b4994'],  // p2: рост
];

function clsColor(cls: string | undefined): string {
  if (!cls) return 'var(--surface-2)';
  const w = +cls[1], p = +cls[3];
  return BIVAR[p][w];
}

/** Хороплет районов с биваритной заливкой. */
function BivarChoro({ geo, wages, names, selected, onSelect }: {
  geo: GeoFeature[];
  wages: WagesData;
  names: Record<string, string>;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
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
          `${i ? 'L' : 'M'}${X(lon).toFixed(1)},${Y(lat).toFixed(1)}`).join('') + 'Z';
      });
      return { id: f.properties.id, d };
    });
    return { paths: ps, height: h };
  }, [geo, width]);

  const hrec = hover ? wages.territories[hover.id] : null;

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg width={width} height={height} role="img" aria-label="зарплата и динамика по районам">
        {paths.map((p) => (
          <path key={p.id} d={p.d}
            fill={clsColor(wages.territories[p.id]?.cls)}
            stroke={p.id === selected ? 'var(--ink)' : 'var(--surface-1)'}
            strokeWidth={p.id === selected ? 1.8 : 0.7}
            style={{ cursor: 'pointer' }}
            onPointerMove={(e) => {
              const box = wrapRef.current!.getBoundingClientRect();
              setHover({ id: p.id, x: e.clientX - box.left, y: e.clientY - box.top });
            }}
            onPointerLeave={() => setHover(null)}
            onClick={() => onSelect(p.id)}
          />
        ))}
        {paths.filter((p) => p.id === selected).map((p) => (
          <path key={p.id + '-s'} d={p.d} fill="none" stroke="var(--ink)"
            strokeWidth="1.8" pointerEvents="none" />
        ))}
        {/* биваритная легенда 3x3 */}
        <g transform={`translate(${width - 132}, ${height - 132})`}>
          {BIVAR.map((row, p) => row.map((c, w) => (
            <rect key={`${w}${p}`} x={w * 22} y={(2 - p) * 22} width="21" height="21" fill={c} />
          )))}
          <text x="33" y="82" textAnchor="middle" fontSize="9.5" fill="var(--ink-2)">зарплата →</text>
          <text x="-8" y="33" textAnchor="middle" fontSize="9.5" fill="var(--ink-2)"
            transform="rotate(-90 -8 33)">рост →</text>
        </g>
      </svg>
      {hover && hrec && (
        <div className="chart-tooltip" style={{ left: Math.min(hover.x + 14, width - 210), top: hover.y - 8 }}>
          <div className="ct-row"><span className="ct-val">{names[hover.id] ?? hover.id}</span></div>
          <div className="ct-year">
            зарплата {(hrec.wageRel * 100).toFixed(0)}% минской
            {hrec.wage2025 ? ` (${Math.round(hrec.wage2025)} BYN, 2025)` : ''}
            {' · '}{hrec.popChange > 0 ? '+' : ''}{hrec.popChange.toFixed(1)}% за 2015–2025
          </div>
        </div>
      )}
    </div>
  );
}

/** Scatter: дифференциал x динамика, терцильные линии, выбросы подписаны. */
function WageScatter({ wages, names, selected, onSelect }: {
  wages: WagesData;
  names: Record<string, string>;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(560);
  const [hover, setHover] = useState<string | null>(null);
  const height = 380;
  const M = { top: 12, right: 14, bottom: 34, left: 44 };

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => el.clientWidth > 40 && setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const ids = Object.keys(wages.territories);
  const xs = ids.map((t) => wages.territories[t].wageRel * 100);
  const ys = ids.map((t) => wages.territories[t].popChange);
  const x0 = Math.floor(Math.min(...xs) / 5) * 5 - 2;
  const x1 = Math.ceil(Math.max(...xs) / 5) * 5 + 2;
  const y0 = Math.floor(Math.min(...ys) / 5) * 5 - 2;
  const y1 = Math.ceil(Math.max(...ys) / 5) * 5 + 2;
  const iw = width - M.left - M.right;
  const ih = height - M.top - M.bottom;
  const X = (v: number) => M.left + ((v - x0) / (x1 - x0)) * iw;
  const Y = (v: number) => M.top + ih - ((v - y0) / (y1 - y0)) * ih;

  const outSet = new Set(wages.outliers);

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg width={width} height={height} role="img">
        {/* терцильные линии */}
        {wages.terciles.wage.map((t) => (
          <line key={'w' + t} x1={X(t * 100)} x2={X(t * 100)} y1={M.top} y2={M.top + ih}
            stroke="var(--grid)" strokeDasharray="4 3" />
        ))}
        {wages.terciles.pop.map((t) => (
          <line key={'p' + t} x1={M.left} x2={width - M.right} y1={Y(t)} y2={Y(t)}
            stroke="var(--grid)" strokeDasharray="4 3" />
        ))}
        <line x1={M.left} x2={width - M.right} y1={Y(0)} y2={Y(0)} stroke="var(--baseline)" />
        {/* оси */}
        {[40, 50, 60, 70, 80, 90, 100].filter((v) => v >= x0 && v <= x1).map((v) => (
          <text key={v} x={X(v)} y={height - 18} textAnchor="middle" fontSize="10" fill="var(--muted)">{v}%</text>
        ))}
        {[-20, -10, 0, 10, 20, 30].filter((v) => v >= y0 && v <= y1).map((v) => (
          <text key={v} x={M.left - 6} y={Y(v) + 3} textAnchor="end" fontSize="10" fill="var(--muted)">{v}</text>
        ))}
        <text x={M.left + iw / 2} y={height - 4} textAnchor="middle" fontSize="10.5" fill="var(--ink-2)">
          средняя зарплата района, % минской ({wages.wageYears[0]}–{wages.wageYears[1]})
        </text>

        {ids.map((t) => {
          const r = wages.territories[t];
          const isOut = outSet.has(t);
          const isSel = t === selected || t === hover;
          return (
            <circle key={t}
              cx={X(r.wageRel * 100)} cy={Y(r.popChange)}
              r={isSel ? 7 : isOut ? 5.5 : 4}
              fill={clsColor(r.cls)}
              stroke={isOut || isSel ? 'var(--ink)' : 'var(--surface-1)'}
              strokeWidth={isSel ? 1.8 : 1}
              style={{ cursor: 'pointer' }}
              onPointerEnter={() => setHover(t)}
              onPointerLeave={() => setHover(null)}
              onClick={() => onSelect(t)}
            />
          );
        })}
        {/* подписи выбросов */}
        {wages.outliers.map((t) => {
          const r = wages.territories[t];
          if (!r) return null;
          return (
            <text key={t} x={X(r.wageRel * 100) + 8} y={Y(r.popChange) - 6}
              fontSize="10" fill="var(--ink-2)">
              {(names[t] ?? t).replace(' район', '')}
            </text>
          );
        })}
      </svg>
      {hover && wages.territories[hover] && (
        <div className="chart-tooltip"
          style={{ left: Math.min(X(wages.territories[hover].wageRel * 100) + 12, width - 200), top: Y(wages.territories[hover].popChange) - 12 }}>
          <div className="ct-row"><span className="ct-val">{names[hover] ?? hover}</span></div>
          <div className="ct-year">
            {(wages.territories[hover].wageRel * 100).toFixed(0)}% минской ·{' '}
            {wages.territories[hover].popChange > 0 ? '+' : ''}{wages.territories[hover].popChange.toFixed(1)}%
            {' · остаток '}{wages.territories[hover].resid > 0 ? '+' : ''}{wages.territories[hover].resid.toFixed(1)} п.п.
          </div>
        </div>
      )}
    </div>
  );
}

export default function WagesView() {
  const [wages, setWages] = useState<WagesData | null>(null);
  const [geo, setGeo] = useState<GeoFeature[] | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [sel, setSel] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return new URLSearchParams(window.location.search).get('sel');
  });

  useEffect(() => {
    fetch('/data/wages.json').then((r) => r.json()).then(setWages);
    fetch('/data/geo/adm2.geojson').then((r) => r.json()).then((g) => setGeo(
      g.features.filter((f: GeoFeature) => f.properties.id.startsWith('r-'))));
    fetch('/data/data.json').then((r) => r.json()).then((d: DataFile) => {
      const m: Record<string, string> = {};
      for (const t of Object.values(d.territories)) m[t.id] = t.ru;
      setNames(m);
    });
  }, []);

  if (!wages || !geo) return <p className="hint">Загрузка данных…</p>;

  const select = (id: string) => {
    setSel(id);
    const url = new URL(window.location.href);
    url.searchParams.set('sel', id);
    window.history.replaceState(null, '', url);
  };

  const m = wages.regressions.main;
  const pct10 = (b: number) => b * Math.log(1.1);
  const betas = Object.values(wages.regressions).map((v) => pct10(v.beta[1]));
  const diag = Object.values(wages.territories)
    .filter((r) => r.cls === 'w0p0' || r.cls === 'w2p2').length;
  const rec = sel ? wages.territories[sel] : null;

  return (
    <div>
      <div className="controls" style={{ marginBottom: 6 }}>
        <MethodDrawer slug="wages" />
        <a className="btn" href="/artifacts/by-maps-wages-v1.0.0.zip" download>
          ⬇ Проверяемый пакет (ZIP)
        </a>
      </div>

      <div className="stat-row">
        <div className="stat-tile">
          <div className="st-label">Эластичность динамики по зарплате</div>
          <div className="st-value">+{pct10(m.beta[1]).toFixed(1)} п.п.</div>
          <div className="st-delta">
            за десятилетие на +10% дифференциала (по спецификациям {Math.min(...betas).toFixed(1)}–{Math.max(...betas).toFixed(1)}); R² {m.r2.toFixed(2)}
          </div>
        </div>
        <div className="stat-tile">
          <div className="st-label">Углы диагонали 3×3</div>
          <div className="st-value">{diag} из 118</div>
          <div className="st-delta">районов: «бедные убывают» + «богатые растут»</div>
        </div>
        <div className="stat-tile">
          <div className="st-label">Зарплата Минска, 2025</div>
          <div className="st-value">{Math.round(wages.minskWage['2025']).toLocaleString('ru-RU')} BYN</div>
          <div className="st-delta">медианный район получает ~57% минской; максимум — Солигорский (101%)</div>
        </div>
      </div>

      <div className="grid-2">
        <div className="chart-block">
          <div className="chart-title">
            Биваритная карта: зарплатный дифференциал × динамика населения 2015–2025
          </div>
          <BivarChoro geo={geo} wages={wages} names={names} selected={sel} onSelect={select} />
        </div>
        <div className="chart-block">
          <div className="chart-title">
            Каждая точка — район; пунктир — терцили; выбросы регрессии подписаны
          </div>
          <WageScatter wages={wages} names={names} selected={sel} onSelect={select} />
        </div>
      </div>

      {rec && sel && (
        <div className="stat-row">
          <div className="stat-tile">
            <div className="st-label">{names[sel] ?? sel} · <a href={`/?sel=${sel}`}>на карту</a></div>
            <div className="st-value">{(rec.wageRel * 100).toFixed(0)}%</div>
            <div className="st-delta">минской зарплаты (среднее {wages.wageYears[0]}–{wages.wageYears[1]}){rec.wage2025 ? ` · ${Math.round(rec.wage2025)} BYN в 2025` : ''}</div>
          </div>
          <div className="stat-tile">
            <div className="st-label">Динамика населения {wages.window[0]}–{wages.window[1]}</div>
            <div className={`st-value`}>{rec.popChange > 0 ? '+' : ''}{rec.popChange.toFixed(1)}%</div>
            <div className="st-delta">остаток от регрессии: {rec.resid > 0 ? '+' : ''}{rec.resid.toFixed(1)} п.п. {Math.abs(rec.resid) > 8 ? '— аномалия' : ''}</div>
          </div>
        </div>
      )}

      <p className="src-note">
        Зарплата — номинальная начисленная по месту работы (дата-портал
        Белстата), поэтому маятниковые работники пригородов учтены по месту
        занятости; дифференциал к Минску самонормируется и не требует
        дефлятора. Связь — корреляционная, не причинная: высокая зарплата и
        рост населения могут иметь общую причину. Полные ограничения — в
        методблоке и LIMITATIONS.md пакета.
      </p>
    </div>
  );
}
