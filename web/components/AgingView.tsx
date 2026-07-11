'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { DataFile } from '@/lib/types';
import { formatNumber } from '@/lib/series';
import { CAT } from '@/lib/scales';
import MethodDrawer from './MethodDrawer';

interface AgingRec {
  median2009: number | null;
  median2019: number;
  share65_2009: number | null;
  share65_2019: number;
  depRatio2019: number;
  yearsTo30: number | null;
  naturalCagr: number | null;
  pyramid2009: { m: number[]; f: number[] } | null;
  pyramid2019: { m: number[]; f: number[] };
}

interface AgingData {
  version: string;
  ageGroups: string[];
  threshold: number;
  counterfactual: string;
  territories: Record<string, AgingRec>;
}

interface GeoFeature {
  properties: { id: string };
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][] };
}

/** Тёплая секвенциальная шкала «старения» (светлый - молодой, тёмный - старый). */
const RAMP = ['#fde4d0', '#f6bd99', '#ee9164', '#dd6236', '#bd3f1a', '#8f2a0e'];
/** «Не пересекает порог за горизонт» - холодный нейтральный. */
const NO_CROSS = '#b9c9dc';

type Mode = 'share65' | 'median' | 'years';

const MODES: Record<Mode, {
  label: string;
  breaks: number[];
  get: (r: AgingRec) => number | null;
  legend: (i: number, breaks: number[]) => string;
  reversed?: boolean;
  nullLabel?: string;
}> = {
  share65: {
    label: 'Доля 65+, 2019',
    breaks: [14, 16, 18, 20, 22],
    get: (r) => r.share65_2019,
    legend: (i, b) => (i === 0 ? `< ${b[0]}%` : i >= b.length ? `≥ ${b[b.length - 1]}%` : `${b[i - 1]}–${b[i]}%`),
  },
  median: {
    label: 'Медианный возраст, 2019',
    breaks: [40, 42, 44, 46, 48],
    get: (r) => r.median2019,
    legend: (i, b) => (i === 0 ? `< ${b[0]}` : i >= b.length ? `≥ ${b[b.length - 1]}` : `${b[i - 1]}–${b[i]}`),
  },
  years: {
    label: 'Лет до порога 30% доли 65+',
    breaks: [15, 25, 35, 45],
    get: (r) => r.yearsTo30,
    legend: (i, b) => (i === 0 ? `≤ ${b[0] - 5}` : i >= b.length ? `≥ ${b[b.length - 1]}` : `${b[i - 1]}–${b[i] - 5}`),
    reversed: true,
    nullLabel: 'не пересекает за 60 лет',
  },
};

function fillFor(mode: Mode, rec: AgingRec | undefined): string {
  if (!rec) return 'var(--surface-2)';
  const m = MODES[mode];
  const v = m.get(rec);
  if (v == null) return NO_CROSS;
  let i = 0;
  while (i < m.breaks.length && v >= m.breaks[i]) i++;
  return RAMP[m.reversed ? m.breaks.length - i : i];
}

/** Мини-хороплет районов: равнопромежуточная проекция, подгонка под контейнер. */
function AgingChoro({ geo, aging, names, mode, selected, onSelect }: {
  geo: GeoFeature[];
  aging: AgingData;
  names: Record<string, string>;
  mode: Mode;
  selected: string;
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
    const iw = width - pad * 2;
    const scale = iw / ((maxLon - minLon) * kx);
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

  const m = MODES[mode];
  const hoverRec = hover ? aging.territories[hover.id] : null;

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg width={width} height={height} role="img" aria-label={m.label}>
        {paths.map((p) => (
          <path
            key={p.id}
            d={p.d}
            fill={fillFor(mode, aging.territories[p.id])}
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
        {/* выбранный район поверх соседей, чтобы обводка не перекрывалась */}
        {paths.filter((p) => p.id === selected).map((p) => (
          <path key={p.id + '-sel'} d={p.d} fill="none" stroke="var(--ink)" strokeWidth="1.8" pointerEvents="none" />
        ))}
      </svg>
      <div className="choro-legend">
        {Array.from({ length: m.breaks.length + 1 }, (_, i) => (
          <span key={i} className="cl-item">
            <span className="cl-swatch" style={{ background: RAMP[m.reversed ? m.breaks.length - i : i] }} />
            {m.legend(i, m.breaks)}
          </span>
        ))}
        {m.nullLabel && (
          <span className="cl-item">
            <span className="cl-swatch" style={{ background: NO_CROSS }} />
            {m.nullLabel}
          </span>
        )}
      </div>
      {hover && hoverRec && (
        <div className="chart-tooltip" style={{ left: Math.min(hover.x + 14, width - 190), top: hover.y - 8 }}>
          <div className="ct-row"><span className="ct-val">{names[hover.id] ?? hover.id}</span></div>
          <div className="ct-year">
            65+: {hoverRec.share65_2019}% · медиана {hoverRec.median2019}
            {hoverRec.yearsTo30 != null ? ` · порог через ${hoverRec.yearsTo30} лет` : ''}
          </div>
        </div>
      )}
    </div>
  );
}

/** Возрастно-половая пирамида: 2019 - заливка, 2009 - пунктирный контур. */
function Pyramid({ rec, groups }: { rec: AgingRec; groups: string[] }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(560);
  const [hoverRow, setHoverRow] = useState<number | null>(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => el.clientWidth > 40 && setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const rowH = 15;
  const M = { top: 20, bottom: 6, center: 46 };
  const height = groups.length * rowH + M.top + M.bottom;
  const half = (width - M.center) / 2;

  const maxVal = Math.max(
    ...rec.pyramid2019.m, ...rec.pyramid2019.f,
    ...(rec.pyramid2009 ? [...rec.pyramid2009.m, ...rec.pyramid2009.f] : []),
  );
  const cxL = half;            // правый край левой (мужской) половины
  const cxR = half + M.center; // левый край правой (женской) половины
  const len = (v: number) => (v / maxVal) * (half - 8);
  const rowY = (i: number) => M.top + (groups.length - 1 - i) * rowH;

  const outline = (side: 'm' | 'f') => {
    if (!rec.pyramid2009) return '';
    const sgn = side === 'm' ? -1 : 1;
    const x0 = side === 'm' ? cxL : cxR;
    let d = '';
    for (let i = groups.length - 1; i >= 0; i--) {
      const x = x0 + sgn * len(rec.pyramid2009[side][i]);
      const yT = rowY(i), yB = rowY(i) + rowH;
      d += `${d ? 'L' : 'M'}${x.toFixed(1)},${yT.toFixed(1)}L${x.toFixed(1)},${yB.toFixed(1)}`;
    }
    return d;
  };

  const fmtK = (v: number) => (v >= 1000 ? `${Math.round(v / 100) / 10} тыс.` : String(v));

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg width={width} height={height} role="img" aria-label="возрастно-половая пирамида">
        <text x={cxL - 4} y={12} textAnchor="end" fontSize="10.5" fill={CAT[0]}>мужчины</text>
        <text x={cxR + 4} y={12} fontSize="10.5" fill={CAT[3]}>женщины</text>
        {groups.map((g, i) => (
          <g key={g} opacity={hoverRow == null || hoverRow === i ? 1 : 0.55}>
            <rect
              x={cxL - len(rec.pyramid2019.m[i])} y={rowY(i) + 1.5}
              width={len(rec.pyramid2019.m[i])} height={rowH - 3}
              fill={CAT[0]}
            />
            <rect
              x={cxR} y={rowY(i) + 1.5}
              width={len(rec.pyramid2019.f[i])} height={rowH - 3}
              fill={CAT[3]}
            />
            <text x={cxL + M.center / 2} y={rowY(i) + rowH - 4} textAnchor="middle" fontSize="9.5" fill="var(--muted)">
              {g}
            </text>
            <rect
              x={0} y={rowY(i)} width={width} height={rowH} fill="transparent"
              onPointerEnter={() => setHoverRow(i)} onPointerLeave={() => setHoverRow(null)}
            />
          </g>
        ))}
        {rec.pyramid2009 && (
          <>
            <path d={outline('m')} fill="none" stroke="var(--ink-2)" strokeWidth="1.2" strokeDasharray="4 3" pointerEvents="none" />
            <path d={outline('f')} fill="none" stroke="var(--ink-2)" strokeWidth="1.2" strokeDasharray="4 3" pointerEvents="none" />
          </>
        )}
      </svg>
      {hoverRow != null && (
        <div className="chart-tooltip" style={{ left: width / 2 - 90, top: rowY_export(hoverRow, groups.length, rowH, M.top) - 10 }}>
          <div className="ct-row"><span className="ct-val">{groups[hoverRow]} лет</span></div>
          <div className="ct-year">
            2019: м {formatNumber(rec.pyramid2019.m[hoverRow])} · ж {formatNumber(rec.pyramid2019.f[hoverRow])}
            {rec.pyramid2009 && <><br />2009: м {formatNumber(rec.pyramid2009.m[hoverRow])} · ж {formatNumber(rec.pyramid2009.f[hoverRow])}</>}
          </div>
        </div>
      )}
      <p className="hint" style={{ margin: '4px 0 0' }}>
        Заливка — перепись 2019; пунктирный контур — 2009. Максимум шкалы: {fmtK(maxVal)} на группу.
      </p>
    </div>
  );
}

function rowY_export(i: number, n: number, rowH: number, top: number) {
  return top + (n - 1 - i) * rowH;
}

export default function AgingView() {
  const [aging, setAging] = useState<AgingData | null>(null);
  const [geo, setGeo] = useState<GeoFeature[] | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [mode, setMode] = useState<Mode>('share65');
  // диплинк ?sel=<id> с карточки территории
  const [sel, setSel] = useState<string>(() => {
    if (typeof window === 'undefined') return 'r-svislacki';
    return new URLSearchParams(window.location.search).get('sel') ?? 'r-svislacki';
  });

  useEffect(() => {
    fetch('/data/aging.json').then((r) => r.json()).then(setAging);
    fetch('/data/geo/adm2.geojson').then((r) => r.json()).then((g) => setGeo(g.features));
    fetch('/data/data.json').then((r) => r.json()).then((d: DataFile) => {
      const m: Record<string, string> = {};
      for (const t of Object.values(d.territories)) m[t.id] = t.ru;
      setNames(m);
    });
  }, []);

  const stats = useMemo(() => {
    if (!aging) return null;
    const rs = Object.entries(aging.territories).filter(([t]) => t.startsWith('r-'));
    const negative = rs.filter(([, v]) => (v.naturalCagr ?? 0) < 0).length;
    const crossing = rs.filter(([, v]) => v.yearsTo30 != null);
    const soon = crossing.filter(([, v]) => v.yearsTo30! <= 20).length;
    const oldest = rs.reduce((a, b) => (b[1].share65_2019 > a[1].share65_2019 ? b : a));
    return { total: rs.length, negative, crossing: crossing.length, soon, oldest };
  }, [aging]);

  if (!aging || !geo || !stats) return <p className="hint">Загрузка данных…</p>;

  const rec = aging.territories[sel] ?? aging.territories['r-svislacki'];
  const selId = aging.territories[sel] ? sel : 'r-svislacki';
  const raionIds = Object.keys(aging.territories).filter((t) => t.startsWith('r-'))
    .sort((a, b) => (names[a] ?? a).localeCompare(names[b] ?? b, 'ru'));
  const otherIds = Object.keys(aging.territories).filter((t) => !t.startsWith('r-'))
    .sort((a, b) => (names[a] ?? a).localeCompare(names[b] ?? b, 'ru'));

  const select = (id: string) => {
    setSel(id);
    const url = new URL(window.location.href);
    url.searchParams.set('sel', id);
    window.history.replaceState(null, '', url);
  };

  return (
    <div>
      <div className="controls" style={{ marginBottom: 6 }}>
        <div className="control-group">
          <span className="control-label">Показатель</span>
          <div className="seg">
            {(Object.keys(MODES) as Mode[]).map((k) => (
              <button key={k} className={k === mode ? 'on' : ''} onClick={() => setMode(k)}>
                {MODES[k].label}
              </button>
            ))}
          </div>
        </div>
        <MethodDrawer slug="aging" />
        <a className="btn" href="/artifacts/by-maps-aging-v1.0.2.zip" download>
          ⬇ Проверяемый пакет (ZIP)
        </a>
      </div>

      <div className="stat-row">
        <div className="stat-tile">
          <div className="st-label">Естественная убыль при нулевой миграции</div>
          <div className="st-value">{stats.negative} из {stats.total}</div>
          <div className="st-delta">районов; сценарий: {aging.counterfactual}</div>
        </div>
        <div className="stat-tile">
          <div className="st-label">Пересекут {aging.threshold}% доли 65+ за 60 лет</div>
          <div className="st-value">{stats.crossing}</div>
          <div className="st-delta">районов, из них {stats.soon} — в ближайшие 20 лет</div>
        </div>
        <div className="stat-tile">
          <div className="st-label">Самый «старый» район, 2019</div>
          <div className="st-value">{names[stats.oldest[0]] ?? stats.oldest[0]}</div>
          <div className="st-delta">{stats.oldest[1].share65_2019}% жителей — 65 лет и старше</div>
        </div>
      </div>

      <div className="grid-2">
        <div className="chart-block">
          <div className="chart-title">{MODES[mode].label} по районам (клик — выбрать район)</div>
          <AgingChoro geo={geo} aging={aging} names={names} mode={mode} selected={selId} onSelect={select} />
        </div>

        <div className="chart-block">
          <div className="chart-title">
            Пирамида: {names[selId] ?? selId}
            {' · '}
            <a href={`/?sel=${selId}`}>показать на карте</a>
          </div>
          <div className="controls" style={{ margin: '2px 0 6px' }}>
            <select value={selId} onChange={(e) => select(e.target.value)} aria-label="территория">
              <optgroup label="Районы">
                {raionIds.map((t) => <option key={t} value={t}>{names[t] ?? t}</option>)}
              </optgroup>
              <optgroup label="Области и города">
                {otherIds.map((t) => <option key={t} value={t}>{names[t] ?? t}</option>)}
              </optgroup>
            </select>
          </div>
          <Pyramid rec={rec} groups={aging.ageGroups} />
        </div>
      </div>

      <div className="stat-row">
        <div className="stat-tile">
          <div className="st-label">Медианный возраст</div>
          <div className="st-value">{rec.median2019}</div>
          {rec.median2009 != null && (
            <div className={`st-delta ${rec.median2019 > rec.median2009 ? 'down' : 'up'}`}>
              {rec.median2009} в 2009 → {(rec.median2019 - rec.median2009) >= 0 ? '+' : ''}{(rec.median2019 - rec.median2009).toFixed(1)} за десятилетие
            </div>
          )}
        </div>
        <div className="stat-tile">
          <div className="st-label">Доля 65+</div>
          <div className="st-value">{rec.share65_2019}%</div>
          {rec.share65_2009 != null && (
            <div className="st-delta">{rec.share65_2009}% в 2009</div>
          )}
        </div>
        <div className="stat-tile">
          <div className="st-label">Демографическая нагрузка</div>
          <div className="st-value">{rec.depRatio2019}</div>
          <div className="st-delta">детей и пожилых на 100 чел. 15–64, 2019</div>
        </div>
        <div className="stat-tile">
          <div className="st-label">Порог {aging.threshold}% доли 65+</div>
          <div className="st-value">{rec.yearsTo30 != null ? (rec.yearsTo30 === 0 ? 'уже' : `через ${rec.yearsTo30} лет`) : '—'}</div>
          <div className="st-delta">
            {rec.yearsTo30 != null ? `≈ ${2019 + rec.yearsTo30} г. · ` : 'не пересекает за 60 лет · '}
            сценарий: {aging.counterfactual}
          </div>
        </div>
        <div className="stat-tile">
          <div className="st-label">Естественная динамика</div>
          <div className="st-value">{rec.naturalCagr != null ? `${rec.naturalCagr > 0 ? '+' : ''}${rec.naturalCagr}%` : '—'}</div>
          <div className="st-delta">в год, 2019–2039, при нулевой миграции</div>
        </div>
      </div>

      <p className="src-note">
        Индикаторы — по переписям 2009 и 2019 гг. (возрастно-половые структуры
        районов, OLAP-куб Белстата). «Лет до порога» и «естественная динамика» —
        контрфактная когортная передвижка без миграции со смертностью и
        рождаемостью базового сценария прогноза v2026.2: показывает, где убыль
        самоподдерживается возрастной структурой. Полные ограничения — в
        методблоке и LIMITATIONS.md пакета.
      </p>
    </div>
  );
}
