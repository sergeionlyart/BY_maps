'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { DataFile } from '@/lib/types';
import MethodDrawer from './MethodDrawer';

interface Row {
  id: string;
  light: Record<string, number>;
  pop: Record<string, number | null>;
  lightRatio: number | null;
  popRatio: number | null;
  div: number | null;
}

interface NightData {
  version: string;
  trendYears: [number, number];
  shockYears: number[];
  years: number[];
  rows: Row[];
  natLight: Record<string, number>;
  natPop: Record<string, number>;
}

interface GeoFeature {
  properties: { id: string };
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][] };
}

/** Дивергентная шкала индекса расхождения (ln свет/тренд − ln нас./тренд):
 *  отрицательный (свет упал сильнее населения) — оранжевый; положительный —
 *  сине-зелёный. */
function divColor(d: number | null | undefined): string {
  if (d == null) return 'var(--surface-2)';
  if (d <= -0.30) return '#8c2d04';
  if (d <= -0.18) return '#e6550d';
  if (d <= -0.08) return '#fd8d3c';
  if (d <= -0.03) return '#fdd0a2';
  if (d < 0.03) return '#f0f0f0';
  if (d < 0.10) return '#c7e9e4';
  if (d < 0.20) return '#5ac8c8';
  return '#0f6e6e';
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

/** Хороплет индекса расхождения (районы adm2 + Минск adm1). */
function DivChoro({ geo, rowById, names, selected, onSelect }: {
  geo: GeoFeature[];
  rowById: Record<string, Row>;
  names: Record<string, string>;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const [wrapRef, width] = useWidth(640);
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);

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
    { c: '#8c2d04', t: 'свет ≪ население' },
    { c: '#fd8d3c', t: 'свет < населения' },
    { c: '#f0f0f0', t: 'совпадают' },
    { c: '#5ac8c8', t: 'свет > населения' },
    { c: '#0f6e6e', t: 'свет ≫ население' },
  ];
  const hrec = hover ? rowById[hover.id] : null;

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg width={width} height={height} role="img" aria-label="индекс расхождения свет-население">
        {paths.map((p) => (
          <path key={p.id} d={p.d}
            fill={divColor(rowById[p.id]?.div)}
            stroke={p.id === selected ? 'var(--ink)' : 'var(--surface-1)'}
            strokeWidth={p.id === selected ? 1.8 : 0.6}
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
              <text x="17" y="10" fontSize="9.5" fill="var(--ink-2)">{l.t}</text>
            </g>
          ))}
        </g>
      </svg>
      {hover && hrec && (
        <div className="chart-tooltip" style={{ left: Math.min(hover.x + 14, width - 240), top: hover.y - 8 }}>
          <div className="ct-row"><span className="ct-val">{names[hover.id] ?? hover.id}</span></div>
          <div className="ct-year">
            {hrec.div != null
              ? `доля света ×${hrec.lightRatio!.toFixed(2)}, доля населения ×${hrec.popRatio!.toFixed(2)}; расхождение ${hrec.div > 0 ? '+' : ''}${(hrec.div * 100).toFixed(0)}%`
              : 'недостаточно данных'}
          </div>
        </div>
      )}
    </div>
  );
}

/** Спарклайны ДОЛЕЙ района в стране (свет и население), к первому году = 100.
 *  Доли, а не абсолют: уровень света искажён версией продукта, доля — нет. */
function LightPopSpark({ row, night }: { row: Row; night: NightData }) {
  const [wrapRef, width] = useWidth(520);
  const height = 200;
  const M = { top: 12, right: 96, bottom: 24, left: 34 };
  const years = night.years;
  const lightShare = (y: number) => (row.light[String(y)] ?? 0) / (night.natLight[String(y)] || 1);
  const base = lightShare(years[0]) || 1e-9;
  const lightIdx = years.map((y) => lightShare(y) / base * 100);
  const popShare = (y: number) => {
    const p = row.pop[String(y)]; const n = night.natPop[String(y)];
    return p != null && n ? p / n : null;
  };
  const popYears = years.filter((y) => popShare(y) != null);
  const popBase = popYears.length ? popShare(popYears[0])! : 1;
  const popI = (y: number) => popShare(y)! / popBase * 100;
  const iw = width - M.left - M.right;
  const ih = height - M.top - M.bottom;
  const all = [...lightIdx, ...popYears.map((y) => popI(y))];
  const y0 = Math.min(50, Math.floor(Math.min(...all) / 10) * 10);
  const y1 = Math.max(120, Math.ceil(Math.max(...all) / 10) * 10);
  const X = (y: number) => M.left + ((y - years[0]) / (years[years.length - 1] - years[0])) * iw;
  const Y = (v: number) => M.top + ih - ((v - y0) / (y1 - y0)) * ih;

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg width={width} height={height} role="img" aria-label="свет и население, индекс">
        {[50, 75, 100, 125].filter((v) => v >= y0 && v <= y1).map((v) => (
          <g key={v}>
            <line x1={M.left} x2={width - M.right} y1={Y(v)} y2={Y(v)}
              stroke="var(--grid)" strokeDasharray="3 4" />
            <text x={M.left - 4} y={Y(v) + 3} textAnchor="end" fontSize="9" fill="var(--muted)">{v}</text>
          </g>
        ))}
        <line x1={M.left} x2={width - M.right} y1={Y(100)} y2={Y(100)} stroke="var(--baseline)" />
        {night.trendYears[1] && (
          <line x1={X(night.trendYears[1])} x2={X(night.trendYears[1])} y1={M.top} y2={M.top + ih}
            stroke="var(--baseline)" strokeDasharray="2 4" opacity="0.6" />
        )}
        <polyline fill="none" stroke="#e6a817" strokeWidth="2"
          points={years.map((y, i) => `${X(y)},${Y(lightIdx[i])}`).join(' ')} />
        <polyline fill="none" stroke="#5698b9" strokeWidth="2"
          points={popYears.map((y) => `${X(y)},${Y(popI(y))}`).join(' ')} />
        <text x={width - M.right + 6} y={Y(lightIdx[lightIdx.length - 1]) + 3} fontSize="10" fill="#e6a817">доля света</text>
        <text x={width - M.right + 6} y={Y(popI(popYears[popYears.length - 1])) + 3} fontSize="10" fill="#5698b9">доля населения</text>
        {years.map((y) => (
          y % 2 === 1 &&
          <text key={y} x={X(y)} y={height - 8} textAnchor="middle" fontSize="8.5" fill="var(--muted)">{`'${String(y).slice(2)}`}</text>
        ))}
        <text x={M.left} y={M.top - 2} fontSize="9" fill="var(--muted)">{years[0]} = 100</text>
      </svg>
    </div>
  );
}

export default function NightlightsView() {
  const [night, setNight] = useState<NightData | null>(null);
  const [geo, setGeo] = useState<GeoFeature[] | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [sel, setSel] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return new URLSearchParams(window.location.search).get('sel');
  });

  useEffect(() => {
    fetch('/data/nightlights.json').then((r) => r.json()).then(setNight);
    Promise.all([
      fetch('/data/geo/adm2.geojson').then((r) => r.json()),
      fetch('/data/geo/adm1.geojson').then((r) => r.json()),
    ]).then(([g2, g1]) => setGeo([
      ...g2.features.filter((f: GeoFeature) => f.properties.id.startsWith('r-')),
      ...g1.features.filter((f: GeoFeature) => f.properties.id === 'BY-HM'),
    ]));
    fetch('/data/data.json').then((r) => r.json()).then((d: DataFile) => {
      const m: Record<string, string> = {};
      for (const t of Object.values(d.territories)) m[t.id] = t.ru;
      setNames(m);
    });
  }, []);

  if (!night || !geo) return <p className="hint">Загрузка данных…</p>;

  const select = (id: string) => {
    setSel(id);
    const url = new URL(window.location.href);
    url.searchParams.set('sel', id);
    window.history.replaceState(null, '', url);
  };

  const rowById: Record<string, Row> = {};
  for (const r of night.rows) rowById[r.id] = r;
  const rec = sel ? rowById[sel] : null;

  const yrs = night.years;
  // средняя светимость трендового окна = мера надёжности (малые сельские
  // районы с крохотной базой шумны); «надёжные» = верхняя половина по свету
  const lsize = (r: Row) => {
    const vals = [];
    for (let y = night.trendYears[0]; y <= night.trendYears[1]; y++) {
      vals.push(r.light[String(y)] ?? 0);
    }
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  };
  const withDiv = night.rows.filter((r) => r.div != null);
  // «надёжные» = 20 ярчайших районов: у них база светимости велика,
  // индекс - содержательный индустриальный сигнал, а не шум малых
  const reliable = [...withDiv].sort((a, b) => lsize(b) - lsize(a)).slice(0, 20);
  const negLeaders = [...reliable].sort((a, b) => a.div! - b.div!).slice(0, 8);
  const top = negLeaders[0];

  return (
    <div>
      <div className="controls" style={{ marginBottom: 6 }}>
        <MethodDrawer slug="nightlights" />
        <a className="btn" href="/artifacts/by-maps-nightlights-v1.0.0.zip" download>
          ⬇ Проверяемый пакет (ZIP)
        </a>
      </div>

      <div className="stat-row">
        <div className="stat-tile">
          <div className="st-label">Свет отстаёт от людей</div>
          <div className="st-value">{top ? (names[top.id] ?? top.id).replace(' район', '') : '—'}</div>
          <div className="st-delta">
            {top ? `доля света ×${top.lightRatio!.toFixed(2)} при доле населения ×${top.popRatio!.toFixed(2)} — ` : ''}
            крупнейший по светимости район, чья доля в светимости страны упала
            относительно доли в населении сильнее всего (Жодино/БелАЗ); за ним — индустриальные центры
          </div>
        </div>
        <div className="stat-tile">
          <div className="st-label">Окно тренда → сравнения</div>
          <div className="st-value">{night.trendYears[0]}–{night.trendYears[1]} → {night.shockYears.join('–')}</div>
          <div className="st-delta">
            индекс = доля района в светимости страны против его доли в населении;
            нормировка на страну гасит версионные скачки продукта VNL
          </div>
        </div>
        <div className="stat-tile">
          <div className="st-label">Свет ≠ население</div>
          <div className="st-value">маркер, не оценка</div>
          <div className="st-delta">
            расхождение может значить недоучёт оттока — или закрытие
            производства, светодиоды, экономию энергии; вход для проверки
          </div>
        </div>
      </div>

      <div className="grid-2">
        <div className="chart-block">
          <div className="chart-title">
            Индекс расхождения «свет против населения» по районам, {night.shockYears.join('–')} к тренду {night.trendYears[0]}–{night.trendYears[1]}
          </div>
          <DivChoro geo={geo} rowById={rowById} names={names} selected={sel} onSelect={select} />
        </div>
        <div className="chart-block">
          <div className="chart-title">Индустриальные районы: доля света отстаёт от доли населения</div>
          <div className="zone-table-wrap">
            <table className="zone-table">
              <thead>
                <tr><th>Район</th><th>свет к тренду</th><th>население к тренду</th><th>расхождение</th></tr>
              </thead>
              <tbody>
                {negLeaders.map((r) => (
                  <tr key={r.id} className={r.id === sel ? 'sel' : ''}
                    onClick={() => select(r.id)} style={{ cursor: 'pointer' }}>
                    <td>{(names[r.id] ?? r.id).replace(' район', '')}</td>
                    <td className={r.lightRatio! < 1 ? 'neg' : 'pos'}>×{r.lightRatio!.toFixed(2)}</td>
                    <td>×{r.popRatio!.toFixed(2)}</td>
                    <td className="neg">{(r.div! * 100).toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="hint" style={{ marginTop: 8 }}>
            Отрицательное расхождение = доля района в светимости страны
            растёт медленнее его доли в населении (свет отстаёт от
            официальных людей). Это <strong>маркер для разбора</strong>, не
            «истинное население»: причиной может быть недоучтённый отток —
            или закрытие производства, переход на светодиоды,
            энергосбережение. Список — вход для дальнейшей проверки, не вывод.
          </p>
        </div>
      </div>

      {rec && sel && (
        <div className="chart-block">
          <div className="chart-title">
            {names[sel] ?? sel} · <a href={`/?sel=${sel}`}>на карту</a> — доля района в стране: свет против населения ({night.years[0]} = 100)
          </div>
          <LightPopSpark row={rec} night={night} />
          {rec.div != null && (
            <p className="hint">
              Доля света к докризисному тренду ×{rec.lightRatio!.toFixed(2)}, доля населения ×{rec.popRatio!.toFixed(2)};
              расхождение {rec.div > 0 ? '+' : ''}{(rec.div * 100).toFixed(0)}%.
              {rec.div < -0.05 ? ' Доля света отстаёт от доли населения — кандидат на недоучёт оттока или деиндустриализацию.'
                : rec.div > 0.05 ? ' Доля света держится лучше доли населения — вероятно рост промышленной/инфраструктурной активности.'
                : ' Доля света и доля населения движутся согласованно.'}
            </p>
          )}
        </div>
      )}

      <p className="src-note">
        Источник — годовые композиты VIIRS «average_masked» (EOG VNL
        2.1/2.2, Colorado School of Mines) в 100-м обработке WorldPop для
        Беларуси, 2015–2023: подлинный, а не смоделированный ряд, пригодный
        для трендов, но не для абсолютных уровней. Индекс — доля района в
        светимости страны против его доли в населении (нормировка на страну
        гасит версионные скачки продукта); Минск выделен отдельной зоной
        (в adm2 он — «дыра» Минского района). Малые сельские районы с
        крохотной светимостью шумны — таблица показывает крупные надёжные;
        свет ≠ население: индекс — маркер расхождения, а не оценка
        численности. Полный перечень причин ложных расхождений — в
        методблоке и LIMITATIONS.md пакета.
      </p>
    </div>
  );
}
