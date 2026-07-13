'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { DataFile } from '@/lib/types';
import { useT } from '@/lib/i18n';
import MethodDrawer from './MethodDrawer';

interface RaionRec {
  rate1519: number | null;
  rate2425: number | null;
  net: Record<string, number>;
}

interface Country {
  geo: string; name: string;
  s2019: number | null; latest: number; latestYear: number;
}

interface Estimate {
  low: number; high: number; year: number; label: string;
  who: string; published: string; src: string; snap: string;
}

interface MigrationData {
  version: string;
  ladder: { years: number[]; tiers: Record<string, number[]>; nRaionCenters: number };
  matrix: {
    flows: { from: string; to: string; n: number }[];
    net: Record<string, number>; total: number;
    oblNames: Record<string, string>;
  };
  raions: Record<string, RaionRec>;
  intlOfficial: Record<string, Record<string, number>>;
  external: {
    countries: Country[];
    euStock: Record<string, number>;
    euFirst: Record<string, number>;
    nonEu: { geo: string; name: string; stock: number; asof: string; src: string }[];
    interval: { low: number; mid: number; high: number };
    timeline: { years: number[]; low: number[]; mid: number[]; high: number[] };
    estimates: Estimate[];
    events: { year: number; label: string }[];
    accessed: string;
  };
}

interface GeoFeature {
  properties: { id: string };
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][] };
}

const TIER_META: [string, string, string][] = [
  ['minsk', 'Минск', '#3b4994'],
  ['oblCenters', 'облцентры', '#5698b9'],
  ['raionCenters', 'райцентры', '#5ac8c8'],
  ['otherUrban', 'прочие города и пгт', '#a5add3'],
  ['rural', 'село', '#be64ac'],
];

/** Дивергентная шкала сальдо, ‰/год: отток - маджента, приток - тил. */
function rateColor(r: number | null | undefined): string {
  if (r == null) return 'var(--surface-2)';
  if (r >= 8) return '#0f6e6e';
  if (r >= 3) return '#5ac8c8';
  if (r >= 0) return '#ace4e4';
  if (r >= -5) return '#e8d0e4';
  if (r >= -10) return '#dfa3cf';
  if (r >= -14) return '#be64ac';
  return '#8b3a80';
}

function useWidth(init: number): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(init);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => el.clientWidth > 40 && setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}

function fmtK(n: number): string {
  return n >= 1e6 ? `${(n / 1e6).toFixed(2)} млн`
    : n >= 1000 ? `${Math.round(n / 1000)} тыс.` : String(Math.round(n));
}

/** Хороплет районного сальдо (та же проекция, что в INF-03/04). */
function SaldoChoro({ geo, mig, names, period, selected, onSelect }: {
  geo: GeoFeature[];
  mig: MigrationData;
  names: Record<string, string>;
  period: 'rate1519' | 'rate2425';
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const [wrapRef, width] = useWidth(640);
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);
  const t = useT();

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

  const legend = [
    { c: '#0f6e6e', t: '≥ +8 ‰/год' }, { c: '#5ac8c8', t: '+3…+8' },
    { c: '#ace4e4', t: '0…+3' }, { c: '#e8d0e4', t: '0…−5' },
    { c: '#dfa3cf', t: '−5…−10' }, { c: '#be64ac', t: '−10…−14' },
    { c: '#8b3a80', t: '< −14 ‰/год' },
  ];

  const hrec = hover ? mig.raions[hover.id] : null;

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg width={width} height={height} role="img" aria-label={t('сальдо миграции по районам')}>
        {paths.map((p) => (
          <path key={p.id} d={p.d}
            fill={rateColor(mig.raions[p.id]?.[period])}
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
        <g transform={`translate(10, ${height - legend.length * 15 - 8})`}>
          {legend.map((l, i) => (
            <g key={i} transform={`translate(0, ${i * 15})`}>
              <rect width="12" height="12" fill={l.c} stroke="var(--grid)" strokeWidth="0.5" />
              <text x="17" y="10" fontSize="9.5" fill="var(--ink-2)">{t(l.t)}</text>
            </g>
          ))}
        </g>
      </svg>
      {hover && hrec && (
        <div className="chart-tooltip" style={{ left: Math.min(hover.x + 14, width - 230), top: hover.y - 8 }}>
          <div className="ct-row"><span className="ct-val">{names[hover.id] ?? hover.id}</span></div>
          <div className="ct-year">
            {period === 'rate1519' ? '2015–2019' : '2024–2025'}:{' '}
            {hrec[period] != null ? `${hrec[period]! > 0 ? '+' : ''}${hrec[period]} ‰/год` : t('нет данных')}
            {' · 2019: '}{hrec.net['2019'] > 0 ? '+' : ''}{hrec.net['2019']} {t('чел.')}
          </div>
        </div>
      )}
    </div>
  );
}

/** «Лестница»: ярусы расселения, млн человек, 1959-2026. */
function Ladder({ mig }: { mig: MigrationData }) {
  const [wrapRef, width] = useWidth(560);
  const t = useT();
  const height = 330;
  const M = { top: 14, right: 150, bottom: 26, left: 36 };
  const years = mig.ladder.years;
  const iw = width - M.left - M.right;
  const ih = height - M.top - M.bottom;
  const X = (y: number) => M.left + ((y - years[0]) / (years[years.length - 1] - years[0])) * iw;
  const maxV = Math.max(...Object.values(mig.ladder.tiers).flat()) / 1e6;
  const Y = (v: number) => M.top + ih - (v / (maxV * 1.05)) * ih;

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg width={width} height={height} role="img" aria-label={t('ярусы расселения')}>
        {[0, 1, 2, 3, 4, 5].filter((v) => v <= maxV).map((v) => (
          <g key={v}>
            <line x1={M.left} x2={width - M.right} y1={Y(v)} y2={Y(v)} stroke="var(--grid)" strokeDasharray="3 4" />
            <text x={M.left - 5} y={Y(v) + 3} textAnchor="end" fontSize="10" fill="var(--muted)">{v}</text>
          </g>
        ))}
        {years.map((y) => (
          <text key={y} x={X(y)} y={height - 8} textAnchor="middle" fontSize="9.5" fill="var(--muted)">{y}</text>
        ))}
        {(() => {
          // разводим подписи справа, чтобы не слипались при близких значениях
          const lab = TIER_META.map(([key, label, color]) => {
            const vals = mig.ladder.tiers[key];
            return { key, label, color, vals, y: Y(vals[vals.length - 1] / 1e6) + 3.5 };
          }).sort((a, b) => a.y - b.y);
          for (let i = 1; i < lab.length; i++) {
            if (lab[i].y - lab[i - 1].y < 13) lab[i].y = lab[i - 1].y + 13;
          }
          return lab.map(({ key, label, color, vals, y }) => (
            <g key={key}>
              <polyline fill="none" stroke={color} strokeWidth="2"
                points={vals.map((v, i) => `${X(years[i])},${Y(v / 1e6)}`).join(' ')} />
              {vals.map((v, i) => (
                <circle key={i} cx={X(years[i])} cy={Y(v / 1e6)} r="2.6" fill={color} />
              ))}
              <text x={width - M.right + 6} y={y} fontSize="10.5" fill={color}>
                {t(label)} {(vals[vals.length - 1] / 1e6).toFixed(1)}
              </text>
            </g>
          ));
        })()}
        <text x={M.left - 24} y={M.top + 4} fontSize="9.5" fill="var(--muted)">{t('млн')}</text>
      </svg>
    </div>
  );
}

/** Хронология внешней волны: полоса low-high, линия mid, точечные оценки. */
function Timeline({ mig }: { mig: MigrationData }) {
  const [wrapRef, width] = useWidth(560);
  const [hover, setHover] = useState<Estimate | null>(null);
  const t = useT();
  const height = 360;
  const M = { top: 16, right: 16, bottom: 44, left: 46 };
  const ext = mig.external;
  const years = ext.timeline.years;
  const iw = width - M.left - M.right;
  const ih = height - M.top - M.bottom;
  const X = (y: number) => M.left + ((y - years[0]) / (years[years.length - 1] - years[0])) * iw;
  const maxV = 620_000;
  const Y = (v: number) => M.top + ih - (v / maxV) * ih;

  const band = years.map((y, i) => `${X(y)},${Y(ext.timeline.high[i])}`).join(' ')
    + ' ' + [...years].reverse().map((y) => {
      const i = years.indexOf(y);
      return `${X(y)},${Y(ext.timeline.low[i])}`;
    }).join(' ');

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg width={width} height={height} role="img" aria-label={t('хронология оттока 2020-2026')}>
        {[0, 100, 200, 300, 400, 500, 600].map((v) => (
          <g key={v}>
            <line x1={M.left} x2={width - M.right} y1={Y(v * 1000)} y2={Y(v * 1000)}
              stroke="var(--grid)" strokeDasharray="3 4" />
            <text x={M.left - 5} y={Y(v * 1000) + 3} textAnchor="end" fontSize="9.5" fill="var(--muted)">{v}</text>
          </g>
        ))}
        <polygon points={band} fill="#be64ac" opacity="0.18" />
        <polyline fill="none" stroke="#be64ac" strokeWidth="2"
          points={years.map((y, i) => `${X(y)},${Y(ext.timeline.mid[i])}`).join(' ')} />
        {years.map((y, i) => (
          <circle key={y} cx={X(y)} cy={Y(ext.timeline.mid[i])} r="2.6" fill="#be64ac" />
        ))}
        {/* точечные оценки: вертикальные интервалы */}
        {ext.estimates.map((e, i) => (
          <g key={i}
            onPointerEnter={() => setHover(e)} onPointerLeave={() => setHover(null)}
            style={{ cursor: 'help' }}>
            <line x1={X(e.year) + 6} x2={X(e.year) + 6} y1={Y(e.low)} y2={Y(e.high)}
              stroke="var(--ink-2)" strokeWidth="2.4" opacity="0.85" />
            <circle cx={X(e.year) + 6} cy={Y((e.low + e.high) / 2)} r="3.4"
              fill="var(--surface-1)" stroke="var(--ink-2)" strokeWidth="1.6" />
          </g>
        ))}
        {years.map((y) => (
          <text key={y} x={X(y)} y={height - 28} textAnchor="middle" fontSize="10" fill="var(--muted)">{y}</text>
        ))}
        {ext.events.map((ev) => (
          <g key={ev.year}>
            <line x1={X(ev.year)} x2={X(ev.year)} y1={M.top} y2={M.top + ih}
              stroke="var(--baseline)" strokeDasharray="2 5" opacity="0.6" />
          </g>
        ))}
        <text x={M.left + iw / 2} y={height - 6} textAnchor="middle" fontSize="10" fill="var(--muted)">
          {t('накопленный незарегистрированный отток, тыс. человек (полоса — интервал WP-F3; штрихи — оценки со стороны)')}
        </text>
      </svg>
      {hover && (
        <div className="chart-tooltip" style={{ left: 60, top: 20, maxWidth: 320 }}>
          <div className="ct-row"><span className="ct-val">{hover.label}</span></div>
          <div className="ct-year">
            {fmtK(hover.low)}{hover.high !== hover.low ? `–${fmtK(hover.high)}` : ''} · {hover.who}
          </div>
          <div className="ct-year">{hover.src}, {hover.published} · {t('снапшот в пакете')}</div>
        </div>
      )}
    </div>
  );
}

/** Страны назначения: сток ВНЖ 2019 vs последний год. */
function Countries({ mig }: { mig: MigrationData }) {
  const [wrapRef, width] = useWidth(560);
  const t = useT();
  const ext = mig.external;
  const top = ext.countries.slice(0, 10);
  const rowH = 26;
  const M = { left: 96, right: 84 };
  const maxV = Math.max(...top.map((c) => c.latest));
  const W = (v: number) => ((width - M.left - M.right) * v) / maxV;

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg width={width} height={top.length * rowH + 30} role="img" aria-label={t('страны назначения')}>
        {top.map((c, i) => (
          <g key={c.geo} transform={`translate(0, ${i * rowH + 8})`}>
            <text x={M.left - 8} y={13} textAnchor="end" fontSize="11" fill="var(--ink)">{c.name}</text>
            <rect x={M.left} y={2} width={W(c.latest)} height={16} fill="#5698b9" rx="2" />
            {c.s2019 != null && (
              <rect x={M.left} y={2} width={W(c.s2019)} height={16} fill="#3b4994" rx="2" />
            )}
            <text x={M.left + W(c.latest) + 6} y={14.5} fontSize="10.5" fill="var(--ink-2)">
              {fmtK(c.latest)} ({c.latestYear})
            </text>
          </g>
        ))}
        <g transform={`translate(${M.left}, ${top.length * rowH + 14})`}>
          <rect width="12" height="10" fill="#3b4994" /><text x="17" y="9" fontSize="9.5" fill="var(--ink-2)">{t('сток 2019')}</text>
          <rect x="86" width="12" height="10" fill="#5698b9" /><text x="103" y="9" fontSize="9.5" fill="var(--ink-2)">{t('последний год')}</text>
        </g>
      </svg>
    </div>
  );
}

export default function MigrationView() {
  const [mig, setMig] = useState<MigrationData | null>(null);
  const [geo, setGeo] = useState<GeoFeature[] | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [period, setPeriod] = useState<'rate1519' | 'rate2425'>('rate1519');
  const [sel, setSel] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return new URLSearchParams(window.location.search).get('sel');
  });

  useEffect(() => {
    fetch('/data/migration.json').then((r) => r.json()).then(setMig);
    fetch('/data/geo/adm2.geojson').then((r) => r.json()).then((g) => setGeo(
      g.features.filter((f: GeoFeature) => f.properties.id.startsWith('r-'))));
    fetch('/data/data.json').then((r) => r.json()).then((d: DataFile) => {
      const m: Record<string, string> = {};
      for (const t of Object.values(d.territories)) m[t.id] = t.ru;
      setNames(m);
    });
  }, []);

  const t = useT();

  if (!mig || !geo) return <p className="hint">{t('Загрузка данных…')}</p>;

  const select = (id: string) => {
    setSel(id);
    const url = new URL(window.location.href);
    url.searchParams.set('sel', id);
    window.history.replaceState(null, '', url);
  };

  const ext = mig.external;
  const iv = ext.interval;
  const rec = sel ? mig.raions[sel] : null;
  const flowsTop = mig.matrix.flows.slice(0, 7);
  const maxFlow = flowsTop[0].n;
  const on = mig.matrix.oblNames;

  const intlBY = mig.intlOfficial['BY'] ?? {};
  const off2425 = (intlBY['2024'] ?? 0) + (intlBY['2025'] ?? 0);

  return (
    <div>
      <div className="controls" style={{ marginBottom: 6 }}>
        <MethodDrawer slug="migration" />
        <a className="btn" href="/artifacts/by-maps-migration-v1.0.0.zip" download>
          ⬇ {t('Проверяемый пакет (ZIP)')}
        </a>
      </div>

      <div className="stat-row">
        <div className="stat-tile">
          <div className="st-label">{t('Официальная статистика vs зеркало')}</div>
          <div className="st-value">+{fmtK(off2425)} vs −{Math.round(iv.mid / 1000)} {t('тыс.')}</div>
          <div className="st-delta">
            {t('официальное сальдо 2024–2025 против накопленной центральной оценки незарегистрированного оттока 2020–2026 (интервал')} {Math.round(iv.low / 1000)}–{Math.round(iv.high / 1000)} {t('тыс.); 2020–2023 Белстат не публиковал')}
          </div>
        </div>
        <div className="stat-tile">
          <div className="st-label">{t('ВНЖ граждан РБ в ЕС')}</div>
          <div className="st-value">{fmtK(ext.euStock['2019'])} → {fmtK(ext.euStock['2024'])}</div>
          <div className="st-delta">
            {t('сток действующих разрешений, 2019 → 2024 (Eurostat; ×')}{(ext.euStock['2024'] / ext.euStock['2019']).toFixed(1)}{t('); пик первичных ВНЖ —')} {fmtK(ext.euFirst['2022'])} {t('в 2022')}
          </div>
        </div>
        <div className="stat-tile">
          <div className="st-label">{t('Лестница за 1959–2026')}</div>
          <div className="st-value">{t('село −65%')}</div>
          <div className="st-delta">
            {t('5,5 → 1,9 млн; райцентры ×2,6; Минск ×3,9 — каждая ступень питает следующую, вершина с 2020 г. — зарубеж')}
          </div>
        </div>
      </div>

      <h2>{t('Внутренняя миграция: лестница работает полвека')}</h2>
      <div className="grid-2">
        <div className="chart-block">
          <div className="chart-title">
            {t('Сальдо миграции районов, ‰/год')}{' '}
            <span className="seg" style={{ marginLeft: 10 }}>
              <button className={`btn sm ${period === 'rate1519' ? 'primary' : ''}`}
                onClick={() => setPeriod('rate1519')}>2015–2019</button>
              <button className={`btn sm ${period === 'rate2425' ? 'primary' : ''}`}
                onClick={() => setPeriod('rate2425')}>2024–2025</button>
            </span>
          </div>
          <SaldoChoro geo={geo} mig={mig} names={names} period={period}
            selected={sel} onSelect={select} />
        </div>
        <div className="chart-block">
          <div className="chart-title">{t('Ярусы расселения: куда пересыпается страна')}</div>
          <Ladder mig={mig} />
          <p className="hint" style={{ marginTop: 6 }}>
            {t('Межобластные направления (перепись-2019, накопленная миграция — «где родились живущие», не годовой поток):')}
          </p>
          {flowsTop.map((f) => (
            <div key={f.from + f.to} style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '3px 0' }}>
              <span style={{ width: 210, fontSize: 12 }} className="ink-2">
                {on[f.from]} → {on[f.to]}
              </span>
              <div style={{ flex: 1, background: 'var(--surface-2)', borderRadius: 3 }}>
                <div style={{ width: `${(f.n / maxFlow) * 100}%`, height: 10, background: '#3b4994', borderRadius: 3 }} />
              </div>
              <span style={{ width: 70, fontSize: 11.5, textAlign: 'right' }} className="ink-2">{fmtK(f.n)}</span>
            </div>
          ))}
        </div>
      </div>

      {rec && sel && (
        <div className="stat-row">
          <div className="stat-tile">
            <div className="st-label">{names[sel] ?? sel} · <a href={`/map?sel=${sel}`}>{t('на карту')}</a></div>
            <div className="st-value">
              {rec.rate1519 != null ? `${rec.rate1519 > 0 ? '+' : ''}${rec.rate1519} ‰` : '—'}
            </div>
            <div className="st-delta">
              {t('сальдо в год, среднее 2015–2019; в 2024–2025:')} {rec.rate2425 != null ? `${rec.rate2425 > 0 ? '+' : ''}${rec.rate2425} ‰` : t('нет данных')}
            </div>
          </div>
          <div className="stat-tile">
            <div className="st-label">{t('Сальдо 2019 / 2024 / 2025, человек')}</div>
            <div className="st-value">
              {['2019', '2024', '2025'].map((y) => (rec.net[y] > 0 ? '+' : '') + (rec.net[y] ?? '—')).join(' / ')}
            </div>
            <div className="st-delta">{t('все потоки вместе; 2020–2023 не публиковались')}</div>
          </div>
        </div>
      )}

      <h2>{t('Внешняя волна 2020+: интервалы, не точки')}</h2>
      <div className="grid-2">
        <div className="chart-block">
          <div className="chart-title">{t('Хронология незарегистрированного оттока (наведите на штрихи-оценки)')}</div>
          <Timeline mig={mig} />
        </div>
        <div className="chart-block">
          <div className="chart-title">{t('Страны назначения: действующие ВНЖ граждан РБ')}</div>
          <Countries mig={mig} />
          <p className="hint" style={{ marginTop: 6 }}>
            {t('Вне учёта ЕС:')} {ext.nonEu.map((n) => `${n.name} — ${fmtK(n.stock)} (${n.asof})`).join('; ')}.{' '}
            {t('Россия: независимой оценки стока нет; Росстат учёл 12–23 тыс. прибывших из РБ в год, сальдо в отдельные годы отрицательное.')}
          </p>
        </div>
      </div>

      <p className="src-note">
        {t('Каждая внешняя цифра — с источником и датой обращения (')}{ext.accessed}{t('), снапшоты страниц в пакете. Оценки поданы интервалами; «зеркальная» статистика не даёт региона происхождения, поэтому по районам внешняя волна не раскладывается — карта районов показывает только зарегистрированную миграцию. Официальные ряды 2020–2023 по миграции не публиковались. Прописка ≠ проживание: часть «уехавших» осталась в официальных рядах. Полные ограничения — в методблоке и LIMITATIONS.md.')}
      </p>
    </div>
  );
}
