'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { DataFile } from '@/lib/types';
import LineChart, { ChartSeries } from './LineChart';
import MethodDrawer from './MethodDrawer';

interface Sanction { jurisdiction: string; date: string; note?: string }
interface Town {
  id: string; ru: string; lat: number; lon: number;
  enterprise: string; enterpriseEn: string; industry: string;
  founded: string; employment: string; employmentYear: string;
  dep: string; sanctions: Sanction[]; nSanctions: number;
  riskScore: number; risk: string;
  pop: Record<string, number>;
  index: Record<string, number> | null;
  controls: string[]; ctrlIndex: Record<string, number>;
  gap: number | null; nSources: number;
}
interface AggCell { n: number; medianGap: number | null; medianIndex2026: number | null }
interface MonoData {
  version: string; baselineYear: number; grid: number[]; idxGrid: number[];
  towns: Town[];
  typology: Record<string, { n: number; ids: string[] }>;
  aggregate: { all: AggCell; byRisk: Record<string, AggCell>; byDep: Record<string, AggCell> };
}
interface GeoFeature {
  properties: { id: string };
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][] };
}

const RISK_COLOR: Record<string, string> = {
  'высокий': '#a63603', 'повышенный': '#e6550d',
  'умеренный': '#fdae6b', 'низкий': '#5698b9',
};
const RISK_ORDER = ['высокий', 'повышенный', 'умеренный', 'низкий'];

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

/** Карта моногородов: контуры районов + точки-города (цвет=риск, размер=население). */
function RiskMap({ geo, towns, selected, onSelect, names }: {
  geo: GeoFeature[]; towns: Town[]; selected: string | null;
  onSelect: (id: string) => void; names: Record<string, string>;
}) {
  const [wrapRef, width] = useWidth(640);
  const [hover, setHover] = useState<{ t: Town; x: number; y: number } | null>(null);

  const { outline, project, height } = useMemo(() => {
    let minLon = 180, maxLon = -180, minLat = 90, maxLat = -90;
    const eachRing = (f: GeoFeature, cb: (r: number[][]) => void) => {
      const polys = f.geometry.type === 'Polygon'
        ? [f.geometry.coordinates as number[][][]]
        : (f.geometry.coordinates as number[][][][]);
      for (const poly of polys) for (const ring of poly) cb(ring);
    };
    for (const f of geo) eachRing(f, (r) => { for (const [lo, la] of r) {
      if (lo < minLon) minLon = lo; if (lo > maxLon) maxLon = lo;
      if (la < minLat) minLat = la; if (la > maxLat) maxLat = la; } });
    const kx = Math.cos(((minLat + maxLat) / 2) * Math.PI / 180);
    const pad = 6, scale = (width - pad * 2) / ((maxLon - minLon) * kx);
    const h = Math.round((maxLat - minLat) * scale) + pad * 2;
    const X = (lo: number) => pad + (lo - minLon) * kx * scale;
    const Y = (la: number) => pad + (maxLat - la) * scale;
    const paths = geo.map((f) => {
      let d = '';
      eachRing(f, (r) => { d += r.map(([lo, la], i) => `${i ? 'L' : 'M'}${X(lo).toFixed(1)},${Y(la).toFixed(1)}`).join('') + 'Z'; });
      return d;
    });
    return { outline: paths, project: { X, Y }, height: h };
  }, [geo, width]);

  const pmax = Math.max(...towns.map((t) => t.pop['2026'] || 0));
  const r = (t: Town) => 3.5 + 9 * Math.sqrt((t.pop['2026'] || 0) / pmax);

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg width={width} height={height} role="img" aria-label="карта моногородов по риску">
        {outline.map((d, i) => (
          <path key={i} d={d} fill="var(--surface-2)" stroke="var(--surface-1)" strokeWidth="0.5" />
        ))}
        {towns.map((t) => (
          <circle key={t.id} cx={project.X(t.lon)} cy={project.Y(t.lat)} r={r(t)}
            fill={RISK_COLOR[t.risk]} fillOpacity="0.82"
            stroke={t.id === selected ? 'var(--ink)' : '#fff'} strokeWidth={t.id === selected ? 2 : 0.7}
            style={{ cursor: 'pointer' }}
            onPointerEnter={(e) => { const b = wrapRef.current!.getBoundingClientRect(); setHover({ t, x: e.clientX - b.left, y: e.clientY - b.top }); }}
            onPointerLeave={() => setHover(null)}
            onClick={() => onSelect(t.id)} />
        ))}
        <g transform={`translate(10, ${height - RISK_ORDER.length * 16 - 8})`}>
          {RISK_ORDER.map((b, i) => (
            <g key={b} transform={`translate(0, ${i * 16})`}>
              <circle cx="6" cy="6" r="5.5" fill={RISK_COLOR[b]} />
              <text x="17" y="10" fontSize="10" fill="var(--ink-2)">риск: {b}</text>
            </g>
          ))}
        </g>
      </svg>
      {hover && (
        <div className="chart-tooltip" style={{ left: Math.min(hover.x + 12, width - 240), top: hover.y - 8 }}>
          <div className="ct-row"><span className="ct-val">{hover.t.ru}</span></div>
          <div className="ct-year">{hover.t.enterprise} · {hover.t.industry}</div>
          <div className="ct-year">риск {hover.t.risk}{hover.t.nSanctions ? ` · санкции: ${hover.t.nSanctions}` : ''}</div>
        </div>
      )}
    </div>
  );
}

export default function MonotownsView() {
  const [mono, setMono] = useState<MonoData | null>(null);
  const [geo, setGeo] = useState<GeoFeature[] | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [industry, setIndustry] = useState<string>('все');
  const [sel, setSel] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return new URLSearchParams(window.location.search).get('sel');
  });

  useEffect(() => {
    fetch('/data/monotowns.json').then((r) => r.json()).then(setMono);
    fetch('/data/geo/adm1.geojson').then((r) => r.json()).then((g) =>
      setGeo(g.features));
    fetch('/data/data.json').then((r) => r.json()).then((d: DataFile) => {
      const m: Record<string, string> = {};
      for (const t of Object.values(d.territories)) m[t.id] = t.ru;
      setNames(m);
    });
  }, []);

  if (!mono || !geo) return <p className="hint">Загрузка данных…</p>;

  const select = (id: string) => {
    setSel(id);
    const url = new URL(window.location.href);
    url.searchParams.set('sel', id);
    window.history.replaceState(null, '', url);
  };

  const shown = industry === 'все' ? mono.towns
    : mono.towns.filter((t) => t.industry === industry);
  const rec = sel ? mono.towns.find((t) => t.id === sel) ?? null : null;
  const highRisk = mono.towns.filter((t) => t.risk === 'высокий');
  const agg = mono.aggregate;

  // серии графика выбранного города: город vs медиана контролей
  let series: ChartSeries[] = [];
  let milestones: { value: number; label: string }[] = [];
  if (rec && rec.index) {
    series = [
      { name: rec.ru, color: RISK_COLOR[rec.risk],
        points: mono.idxGrid.filter((y) => rec.index![String(y)] != null)
          .map((y) => ({ year: y, value: rec.index![String(y)], major: true })) },
    ];
    const ctrlPts = mono.idxGrid.filter((y) => rec.ctrlIndex[String(y)] != null)
      .map((y) => ({ year: y, value: rec.ctrlIndex[String(y)], major: true }));
    if (ctrlPts.length) series.push({ name: 'типовой город того же размера', color: 'var(--muted)', points: ctrlPts });
    const fy = parseInt(rec.founded);
    if (fy >= 1959 && fy <= 2026) milestones.push({ value: fy, label: 'завод' });
    for (const s of rec.sanctions) {
      const y = parseInt((s.date || '').slice(0, 4));
      if (y >= 1989) milestones.push({ value: y, label: `санкции ${s.jurisdiction}` });
    }
    // dedup milestone years
    const seen = new Set<number>();
    milestones = milestones.filter((m) => (seen.has(m.value) ? false : (seen.add(m.value), true)));
  }

  return (
    <div>
      <div className="controls" style={{ marginBottom: 6 }}>
        <MethodDrawer slug="monotowns" />
        <a className="btn" href="/artifacts/by-maps-monotowns-v1.0.0.zip" download>
          ⬇ Проверяемый пакет (ZIP)
        </a>
      </div>

      <div className="stat-row">
        <div className="stat-tile">
          <div className="st-label">Моногородов в реестре</div>
          <div className="st-value">{mono.towns.length}</div>
          <div className="st-delta">
            пар «город — градообразующее предприятие», {Object.keys(mono.typology).length} отраслей;
            каждая с источником и санкционной экспозицией
          </div>
        </div>
        <div className="stat-tile">
          <div className="st-label">В зоне высокого риска</div>
          <div className="st-value">{highRisk.length}</div>
          <div className="st-delta">
            сильная зависимость от одного (санкционного) завода: {highRisk.slice(0, 5).map((t) => t.ru).join(', ')}… — уязвимость при негативном сценарии
          </div>
        </div>
        <div className="stat-tile">
          <div className="st-label">Чем выше зависимость, тем хуже</div>
          <div className="st-value">
            {agg.byDep.high.medianGap} vs +{agg.byDep.medium.medianGap} п.п.
          </div>
          <div className="st-delta">
            среди сопоставимых по размеру: у моногородов высокой зависимости
            население к 2026 отстаёт от типовых, у средней — держится; это
            ассоциация, не доказанная причинность
          </div>
        </div>
      </div>

      <div className="grid-2">
        <div className="chart-block">
          <div className="chart-title">
            Карта моногородов: цвет — полоса риска, размер — население{' '}
            <select value={industry} onChange={(e) => setIndustry(e.target.value)}
              style={{ marginLeft: 8, fontSize: 12, padding: '2px 6px', background: 'var(--surface-2)', color: 'var(--ink)', border: '1px solid var(--border)', borderRadius: 4 }}>
              <option value="все">все отрасли</option>
              {Object.keys(mono.typology).map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
          </div>
          <RiskMap geo={geo} towns={shown} names={names} selected={sel} onSelect={select} />
        </div>
        <div className="chart-block">
          <div className="chart-title">
            {rec ? `${rec.ru}: население к 1989 = 100${rec.gap != null ? ' (город против типовых того же размера)' : ' — крупный, сопоставимых по размеру нет'}`
              : 'Выберите город на карте — траектория против типовых'}
          </div>
          {rec && rec.index ? (
            <>
              <LineChart series={series} height={230} domain={[mono.baselineYear, 2026]}
                markYear={null} refXs={milestones} refY={{ value: 100, label: '1989' }}
                yFormat={(v) => String(Math.round(v))} yTooltip={(v) => `${v.toFixed(0)} к 1989`} />
              <div className="stat-row" style={{ marginTop: 8 }}>
                <div className="stat-tile">
                  <div className="st-label">{rec.enterprise}</div>
                  <div className="st-value" style={{ fontSize: 15 }}>{rec.industry}</div>
                  <div className="st-delta">
                    осн. {rec.founded || '—'}; занятость {rec.employment || '—'}
                    {rec.employmentYear ? ` (${rec.employmentYear})` : ''}; зависимость города — {rec.dep === 'high' ? 'высокая' : rec.dep === 'medium' ? 'средняя' : 'низкая'}
                  </div>
                </div>
                <div className="stat-tile">
                  <div className="st-label">Риск: {rec.risk} · <a href={`/?sel=${rec.id}`}>на карту</a></div>
                  <div className="st-value" style={{ fontSize: 15 }}>
                    {rec.gap != null ? `${rec.gap > 0 ? '+' : ''}${rec.gap} п.п. к типовым` : 'нет пары по размеру'}
                  </div>
                  <div className="st-delta">
                    {rec.nSanctions
                      ? `санкции: ${rec.sanctions.map((s) => `${s.jurisdiction} ${(s.date || '').slice(0, 4)}`).join(', ')}`
                      : 'адресных санкций против предприятия не зафиксировано'}
                  </div>
                </div>
              </div>
            </>
          ) : (
            <p className="hint" style={{ padding: '20px 4px' }}>
              Клик по точке города покажет, как его население менялось
              относительно «типовых» городов того же размера, с вехами
              предприятия (основание, санкции).
            </p>
          )}
        </div>
      </div>

      <p className="src-note">
        Реестр — ручная курация по открытым источникам (сайты предприятий,
        отраслевая пресса, санкционные списки EU/US/UK/Canada); занятость
        оценочная, санкционная экспозиция актуальна на дату сбора
        (2026-07-12) и быстро меняется. «Типовой город» — медиана до восьми
        ближайших по населению-1989 городов в пределах фактора 2, не
        моногородов и не облцентров; у 15 крупнейших моногородов
        сопоставимых по размеру «обычных» городов в Беларуси нет (они и
        есть крупные города без облцентров) — для них показана только
        собственная траектория. Связь населения с заводом — ассоциация, не
        доказанная причинность. Построчные источники — в методблоке и пакете.
      </p>
    </div>
  );
}
