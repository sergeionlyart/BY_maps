'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import LineChart, { ChartSeries } from './LineChart';
import MethodDrawer from './MethodDrawer';

interface Source { url: string; claim: string }
interface EventRec {
  year: number; year_end?: number; title: string; description: string;
  affected?: string; magnitude?: string; sources: Source[];
}
interface CensusCity {
  id: string | null; ru: string; total: number; jewish: number;
  jewishShare: number; belarusian: number | null; russian: number | null;
  polish: number | null; lat: number | null; lon: number | null; source: string;
}
interface HoloTown {
  id: string | null; ru: string; jewishShare1897: number | null;
  jewishCount1897: number | null; pop1939: number | null;
  pop1959: number | null; note: string; sources: Source[];
}
interface ShocksData {
  version: string; series: Record<string, number>; seriesYears: number[];
  events: EventRec[]; census1897: CensusCity[]; holocaust: HoloTown[];
}
interface GeoFeature {
  properties: { id: string };
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][] };
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

/** Доля евреев-1897: жёлто-бордовая последовательная шкала. */
function jewColor(s: number): string {
  if (s >= 70) return '#7a0177';
  if (s >= 55) return '#c51b8a';
  if (s >= 40) return '#f768a1';
  if (s >= 25) return '#fbb4b9';
  return '#feebe2';
}

/** Карта местечек: точки-города, цвет — доля евреев-1897, размер — население. */
function ShtetlMap({ geo, cities }: { geo: GeoFeature[]; cities: CensusCity[] }) {
  const [wrapRef, width] = useWidth(640);
  const [hover, setHover] = useState<{ c: CensusCity; x: number; y: number } | null>(null);
  const pts = cities.filter((c) => c.lat && c.lon);

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
    const paths = geo.map((f) => { let d = ''; eachRing(f, (r) => { d += r.map(([lo, la], i) => `${i ? 'L' : 'M'}${X(lo).toFixed(1)},${Y(la).toFixed(1)}`).join('') + 'Z'; }); return d; });
    return { outline: paths, project: { X, Y }, height: h };
  }, [geo, width]);

  const pmax = Math.max(...pts.map((c) => c.total));
  const r = (c: CensusCity) => 3 + 10 * Math.sqrt(c.total / pmax);
  const legend = [
    { c: '#7a0177', t: '≥ 70%' }, { c: '#c51b8a', t: '55–70%' },
    { c: '#f768a1', t: '40–55%' }, { c: '#fbb4b9', t: '25–40%' }, { c: '#feebe2', t: '< 25%' },
  ];

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg width={width} height={height} role="img" aria-label="доля евреев по городам 1897">
        {outline.map((d, i) => <path key={i} d={d} fill="var(--surface-2)" stroke="var(--surface-1)" strokeWidth="0.5" />)}
        {pts.map((c) => (
          <circle key={c.ru} cx={project.X(c.lon!)} cy={project.Y(c.lat!)} r={r(c)}
            fill={jewColor(c.jewishShare)} fillOpacity="0.85" stroke="#fff" strokeWidth="0.7"
            style={{ cursor: 'help' }}
            onPointerEnter={(e) => { const b = wrapRef.current!.getBoundingClientRect(); setHover({ c, x: e.clientX - b.left, y: e.clientY - b.top }); }}
            onPointerLeave={() => setHover(null)} />
        ))}
        <g transform={`translate(10, ${height - legend.length * 15 - 8})`}>
          {legend.map((l, i) => (
            <g key={i} transform={`translate(0, ${i * 15})`}>
              <rect width="12" height="12" fill={l.c} stroke="var(--grid)" strokeWidth="0.5" />
              <text x="17" y="10" fontSize="9.5" fill="var(--ink-2)">евреи {l.t}</text>
            </g>
          ))}
        </g>
      </svg>
      {hover && (
        <div className="chart-tooltip" style={{ left: Math.min(hover.x + 12, width - 220), top: hover.y - 8 }}>
          <div className="ct-row"><span className="ct-val">{hover.c.ru}, 1897</span></div>
          <div className="ct-year">
            {hover.c.total.toLocaleString('ru-RU')} жит.; евреи (идиш) {hover.c.jewish.toLocaleString('ru-RU')} — {hover.c.jewishShare.toFixed(0)}%
          </div>
        </div>
      )}
    </div>
  );
}

export default function ShocksView() {
  const [sh, setSh] = useState<ShocksData | null>(null);
  const [geo, setGeo] = useState<GeoFeature[] | null>(null);
  const [selEvent, setSelEvent] = useState<number | null>(null);

  useEffect(() => {
    fetch('/data/shocks.json').then((r) => r.json()).then(setSh);
    fetch('/data/geo/adm1.geojson').then((r) => r.json()).then((g) => setGeo(g.features));
  }, []);

  if (!sh || !geo) return <p className="hint">Загрузка данных…</p>;

  const s = sh.series;
  const series: ChartSeries[] = [{
    name: 'население Беларуси', color: 'var(--accent, #5698b9)',
    points: sh.seriesYears.filter((y) => s[String(y)]).map((y) => ({ year: y, value: s[String(y)], major: true })),
  }];
  // маркеры по уникальным годам (несколько событий 1941 не должны
  // давать дублей ключей на оси)
  const evMarks = [...new Set(sh.events.map((e) => e.year))].map((y) => ({ value: y, label: '' }));
  const ev = selEvent != null ? sh.events[selEvent] : null;

  const wwiiLoss = (s['1940'] || 0) - (s['1950'] || 0);
  const topShtetl = sh.census1897[0];
  const holoTop = sh.holocaust.slice(0, 8);

  return (
    <div>
      <div className="controls" style={{ marginBottom: 6 }}>
        <MethodDrawer slug="shocks" />
        <a className="btn" href="/artifacts/by-maps-shocks-v1.0.0.zip" download>
          ⬇ Проверяемый пакет (ZIP)
        </a>
      </div>

      <div className="stat-row">
        <div className="stat-tile">
          <div className="st-label">Потери Второй мировой</div>
          <div className="st-value">−{(wwiiLoss / 1e6).toFixed(2)} млн</div>
          <div className="st-delta">
            9,05 млн (1940) → 7,71 млн (1950); довоенной численности страна
            достигла лишь в начале 1970-х
          </div>
        </div>
        <div className="stat-tile">
          <div className="st-label">Местечко до Холокоста</div>
          <div className="st-value">{topShtetl.jewishShare.toFixed(0)}%</div>
          <div className="st-delta">
            доля евреев в {topShtetl.ru} по переписи-1897; в десятках городов
            евреи составляли 55–76% — это и было «местечко»
          </div>
        </div>
        <div className="stat-tile">
          <div className="st-label">Событий-вех на таймлайне</div>
          <div className="st-value">{sh.events.length}</div>
          <div className="st-delta">
            от беженства 1915 до распада СССР; каждое — с проверяемым
            источником (нажмите веху ниже)
          </div>
        </div>
      </div>

      <h2>Таймлайн шоков: как население переживало XX век</h2>
      <div className="chart-block">
        <div className="chart-title">
          Население Беларуси, 1897–2026, с вехами демографических шоков (кликните веху)
        </div>
        <LineChart series={series} height={250} refXs={evMarks}
          yFormat={(v) => `${(v / 1e6).toFixed(1)}М`}
          yTooltip={(v) => `${v.toLocaleString('ru-RU')} чел.`} />
        <div className="event-chips" style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
          {sh.events.map((e, i) => (
            <button key={i} className={`btn sm ${selEvent === i ? 'primary' : ''}`}
              onClick={() => setSelEvent(selEvent === i ? null : i)}>
              {e.year}{e.year_end ? `–${e.year_end}` : ''} · {e.title.split(/[.:]/)[0].slice(0, 26)}
            </button>
          ))}
        </div>
        {ev && (
          <div className="card" style={{ marginTop: 8 }}>
            <div className="card-code">
              {ev.year}{ev.year_end ? `–${ev.year_end}` : ''} · {ev.title}
            </div>
            <p style={{ margin: '6px 0' }}>{ev.description}</p>
            {ev.magnitude && <p className="hint">Масштаб: {ev.magnitude}</p>}
            <div className="card-foot">
              {ev.sources.map((src, j) => (
                <a key={j} href={src.url} target="_blank" rel="noopener noreferrer"
                  style={{ marginRight: 10, fontSize: 12 }}>
                  источник {j + 1} ↗
                </a>
              ))}
            </div>
          </div>
        )}
      </div>

      <h2>Местечко: география 1897 года и его исчезновение</h2>
      <div className="grid-2">
        <div className="chart-block">
          <div className="chart-title">
            Доля евреев по городам, перепись-1897 (родной язык — идиш)
          </div>
          <ShtetlMap geo={geo} cities={sh.census1897} />
        </div>
        <div className="chart-block">
          <div className="chart-title">Местечки до и после: 1897 → послевоенная перепись</div>
          <div className="zone-table-wrap">
            <table className="zone-table">
              <thead>
                <tr><th>Город</th><th>евреи 1897</th><th>1939</th><th>1959</th></tr>
              </thead>
              <tbody>
                {holoTop.map((t) => (
                  <tr key={t.ru}>
                    <td>{t.ru}</td>
                    <td className="neg">{t.jewishShare1897 != null ? `${t.jewishShare1897.toFixed(0)}%` : '—'}</td>
                    <td>{t.pop1939 != null ? Math.round(t.pop1939 / 1000) + 'к' : '—'}</td>
                    <td>{t.pop1959 != null ? Math.round(t.pop1959 / 1000) + 'к' : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="hint" style={{ marginTop: 8 }}>
            Часть городов к 1959 году восстановила общую численность — но
            <strong> иным, нееврейским</strong> населением, часть (Рогачёв,
            Слоним) не восстановилась вовсе: еврейское большинство местечек
            было уничтожено в 1941–1943 гг. Число в столбце «евреи 1897» —
            доля по переписи-1897 (идиш/всё; для городов вне переписи —
            оценка источника), мера утраченного типа поселения, а не оценка
            жертв конкретного города. Источники — в пакете.
          </p>
        </div>
      </div>

      <p className="src-note">
        Национальный ряд — база проекта (переписи и оценки; разрыв
        1939–1959 — межпереписной, промежуточные оценки неточны). Перепись-
        1897 — таблицы Демоскопа по родному языку (язык ≠ этничность:
        идиш — близкое, но не тождественное приближение еврейского
        населения). Событийные аннотации — с проверяемыми источниками;
        чувствительные темы поданы фактологически. Полные оговорки — в
        методблоке и LIMITATIONS.md пакета.
      </p>
    </div>
  );
}
