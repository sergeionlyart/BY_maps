'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { DataFile } from '@/lib/types';
import MethodDrawer from './MethodDrawer';

interface AccessRec {
  minMinsk: number;
  minObl: number;
  oblId: string;
  eff: number;
  belt: string;
  beltEff: string;
  eu2019: number;
  euNadir: number;
  eu2026: number;
  euDelta: number;
  euDeltaNadir: number;
  popChange: number;
  wageRel: number;
}

interface Profile { belt: string; n: number; median: number; q25: number; q75: number }
interface Reg { beta: number[]; se: number[]; seHc1: number[]; r2: number; n: number }

interface AccessData {
  version: string;
  window: [number, number];
  belts: string[];
  baseBelt: string;
  beltNames: string[];
  territories: Record<string, AccessRec>;
  profileMinsk: Profile[];
  profileEff: Profile[];
  regression: Reg;
  regressionNoWage: Reg;
  west30: string[];
}

interface GeoFeature {
  properties: { id: string };
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][] };
}

/** Цвета поясов согласованы со Stevens-палитрой INF-03:
 *  пригород — teal (растёт), кольцо — маджента (худшее). */
const BELT_COLOR: Record<string, string> = {
  '<45 мин': '#5ac8c8',
  '45-90 мин': '#a5add3',
  '1,5-2,5 ч': '#be64ac',
  '>2,5 ч': '#e8e8e8',
};

/** Облцентр по коду области — для подписей. */
const OBL_CENTER_NAME: Record<string, string> = {
  'BY-BR': 'Бреста', 'BY-VI': 'Витебска', 'BY-HO': 'Гомеля',
  'BY-HR': 'Гродно', 'BY-MA': 'Могилёва', 'BY-HM': 'Минска',
};

/** Потеря доступности ЕС в надир (минуты) — последовательная шкала. */
function nadirColor(d: number): string {
  if (d <= 0) return '#e8e8e8';
  if (d <= 30) return '#fdd0a2';
  if (d <= 60) return '#fd8d3c';
  if (d <= 120) return '#e6550d';
  return '#a63603';
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

/** Хороплет районов с произвольной заливкой и тултипом. */
function Choro({ geo, fill, tooltip, selected, onSelect, label, legend }: {
  geo: GeoFeature[];
  fill: (id: string) => string;
  tooltip: (id: string) => string;
  selected: string | null;
  onSelect: (id: string) => void;
  label: string;
  legend: { color: string; text: string }[];
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

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg width={width} height={height} role="img" aria-label={label}>
        {paths.map((p) => (
          <path key={p.id} d={p.d}
            fill={fill(p.id)}
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
        <g transform={`translate(10, ${height - legend.length * 17 - 8})`}>
          {legend.map((l, i) => (
            <g key={i} transform={`translate(0, ${i * 17})`}>
              <rect width="13" height="13" fill={l.color} stroke="var(--grid)" strokeWidth="0.5" />
              <text x="18" y="10.5" fontSize="10" fill="var(--ink-2)">{l.text}</text>
            </g>
          ))}
        </g>
      </svg>
      {hover && (
        <div className="chart-tooltip"
          style={{ left: Math.min(hover.x + 14, width - 230), top: hover.y - 8 }}>
          <div className="ct-year">{tooltip(hover.id)}</div>
        </div>
      )}
    </div>
  );
}

/** Профиль динамики по поясам: медиана + межквартильный размах. */
function BeltProfile({ access }: { access: AccessData }) {
  const [wrapRef, width] = useWidth(560);
  const height = 340;
  const M = { top: 16, right: 14, bottom: 40, left: 44 };
  const iw = width - M.left - M.right;
  const ih = height - M.top - M.bottom;

  const all = [...access.profileEff, ...access.profileMinsk];
  const y0 = Math.floor(Math.min(...all.map((p) => p.q25)) / 5) * 5 - 2;
  const y1 = Math.ceil(Math.max(...all.map((p) => p.q75)) / 5) * 5 + 2;
  const Y = (v: number) => M.top + ih - ((v - y0) / (y1 - y0)) * ih;
  const X = (i: number) => M.left + ((i + 0.5) / access.belts.length) * iw;

  const series = [
    { prof: access.profileMinsk, color: 'var(--muted)', dx: -9, name: 'до Минска' },
    { prof: access.profileEff, color: '#be64ac', dx: 9, name: 'эффективная (мин. из Минска и облцентра)' },
  ];

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg width={width} height={height} role="img" aria-label="профиль динамики по поясам">
        <line x1={M.left} x2={width - M.right} y1={Y(0)} y2={Y(0)} stroke="var(--baseline)" />
        {[-15, -10, -5, 0, 5, 10].filter((v) => v >= y0 && v <= y1).map((v) => (
          <g key={v}>
            <line x1={M.left} x2={width - M.right} y1={Y(v)} y2={Y(v)} stroke="var(--grid)" strokeDasharray="3 4" />
            <text x={M.left - 6} y={Y(v) + 3} textAnchor="end" fontSize="10" fill="var(--muted)">{v > 0 ? '+' : ''}{v}</text>
          </g>
        ))}
        {access.belts.map((b, i) => (
          <text key={b} x={X(i)} y={height - 20} textAnchor="middle" fontSize="10.5" fill="var(--ink-2)">{b}</text>
        ))}
        <text x={M.left + iw / 2} y={height - 5} textAnchor="middle" fontSize="10" fill="var(--muted)">
          время в пути от райцентра · медиана и межквартильный размах, % за {access.window[0]}–{access.window[1]}
        </text>
        {series.map((s) => {
          const pts = access.belts
            .map((b, i) => ({ i, p: s.prof.find((p) => p.belt === b) }))
            .filter((x): x is { i: number; p: Profile } => !!x.p);
          return (
            <g key={s.name}>
              <polyline fill="none" stroke={s.color} strokeWidth="1.6" opacity="0.75"
                points={pts.map(({ i, p }) => `${X(i) + s.dx},${Y(p.median)}`).join(' ')} />
              {pts.map(({ i, p }) => (
                <g key={i}>
                  <line x1={X(i) + s.dx} x2={X(i) + s.dx} y1={Y(p.q25)} y2={Y(p.q75)}
                    stroke={s.color} strokeWidth="1.2" opacity="0.6" />
                  <circle cx={X(i) + s.dx} cy={Y(p.median)} r="4.5" fill={s.color} />
                  <text x={X(i) + s.dx} y={Y(p.median) - 9} textAnchor="middle" fontSize="9.5" fill="var(--ink-2)">
                    {p.median > 0 ? '+' : ''}{p.median.toFixed(1)}
                  </text>
                </g>
              ))}
            </g>
          );
        })}
        <g transform={`translate(${M.left + 8}, ${M.top + 2})`}>
          {series.map((s, i) => (
            <g key={s.name} transform={`translate(0, ${i * 16})`}>
              <circle cx="5" cy="5" r="4.5" fill={s.color} />
              <text x="15" y="8.5" fontSize="10" fill="var(--ink-2)">{s.name}</text>
            </g>
          ))}
        </g>
      </svg>
    </div>
  );
}

export default function AccessView() {
  const [access, setAccess] = useState<AccessData | null>(null);
  const [geo, setGeo] = useState<GeoFeature[] | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [sel, setSel] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return new URLSearchParams(window.location.search).get('sel');
  });

  useEffect(() => {
    fetch('/data/access.json').then((r) => r.json()).then(setAccess);
    fetch('/data/geo/adm2.geojson').then((r) => r.json()).then((g) => setGeo(
      g.features.filter((f: GeoFeature) => f.properties.id.startsWith('r-'))));
    fetch('/data/data.json').then((r) => r.json()).then((d: DataFile) => {
      const m: Record<string, string> = {};
      for (const t of Object.values(d.territories)) m[t.id] = t.ru;
      setNames(m);
    });
  }, []);

  if (!access || !geo) return <p className="hint">Загрузка данных…</p>;

  const select = (id: string) => {
    setSel(id);
    const url = new URL(window.location.href);
    url.searchParams.set('sel', id);
    window.history.replaceState(null, '', url);
  };

  const t = access.territories;
  const fmtMin = (m: number) => {
    const total = Math.round(m);
    return total >= 90 ? `${Math.floor(total / 60)} ч ${total % 60} мин`
      : `${total} мин`;
  };

  const profEff = Object.fromEntries(access.profileEff.map((p) => [p.belt, p]));
  const ringGap = profEff['>2,5 ч'].median - profEff['1,5-2,5 ч'].median;
  const reg = access.regression;
  const iRing = 1 + access.beltNames.indexOf('1,5-2,5 ч');
  const nadirHit = Object.values(t).filter((r) => r.euDeltaNadir > 60).length;
  const rec = sel ? t[sel] : null;

  return (
    <div>
      <div className="controls" style={{ marginBottom: 6 }}>
        <MethodDrawer slug="access" />
        <a className="btn" href="/artifacts/by-maps-access-v1.0.0.zip" download>
          ⬇ Проверяемый пакет (ZIP)
        </a>
      </div>

      <div className="stat-row">
        <div className="stat-tile">
          <div className="st-label">Пригород против кольца</div>
          <div className="st-value">
            {profEff['<45 мин'].median > 0 ? '+' : ''}{profEff['<45 мин'].median.toFixed(1)} vs {profEff['1,5-2,5 ч'].median.toFixed(1)}%
          </div>
          <div className="st-delta">
            медианная динамика {access.window[0]}–{access.window[1]}: до 45 мин от центра — против кольца 1,5–2,5 ч
          </div>
        </div>
        <div className="stat-tile">
          <div className="st-label">«Тень»: кольцо хуже дальней периферии</div>
          <div className="st-value">{ringGap > 0 ? '+' : ''}{ringGap.toFixed(1)} п.п.</div>
          <div className="st-delta">
            дальше 2,5 ч убыль слабее, чем в кольце ({profEff['>2,5 ч'].median.toFixed(1)} против {profEff['1,5-2,5 ч'].median.toFixed(1)}%) — профиль немонотонный
          </div>
        </div>
        <div className="stat-tile">
          <div className="st-label">Легковые переходы в ЕС</div>
          <div className="st-value">13 → 4 → 6</div>
          <div className="st-delta">
            2019 → надир 2024–2025 → июль 2026; в надир {nadirHit} районов потеряли больше часа пути до ЕС
          </div>
        </div>
      </div>

      <div className="grid-2">
        <div className="chart-block">
          <div className="chart-title">
            Пояса эффективной доступности: время в пути до Минска или ближайшего облцентра
          </div>
          <Choro geo={geo} selected={sel} onSelect={select}
            label="пояса доступности по районам"
            fill={(id) => BELT_COLOR[t[id]?.beltEff] ?? 'var(--surface-2)'}
            legend={access.belts.map((b) => ({
              color: BELT_COLOR[b],
              text: `${b} · медиана ${profEff[b].median > 0 ? '+' : ''}${profEff[b].median.toFixed(1)}%`,
            }))}
            tooltip={(id) => {
              const r = t[id];
              if (!r) return names[id] ?? id;
              return `${names[id] ?? id}: до Минска ${fmtMin(r.minMinsk)}, до облцентра ${fmtMin(r.minObl)} · ${r.popChange > 0 ? '+' : ''}${r.popChange.toFixed(1)}%`;
            }}
          />
        </div>
        <div className="chart-block">
          <div className="chart-title">
            Профиль динамики по поясам: минимум потерь у центра, дно в кольце, подъём на периферии
          </div>
          <BeltProfile access={access} />
        </div>
      </div>

      <div className="grid-2">
        <div className="chart-block">
          <div className="chart-title">
            Надир 2024–2025: насколько дальше стал ЕС после закрытия переходов
          </div>
          <Choro geo={geo} selected={sel} onSelect={select}
            label="потеря доступности ЕС в надир"
            fill={(id) => nadirColor(t[id]?.euDeltaNadir ?? 0)}
            legend={[
              { color: '#e8e8e8', text: 'без изменений (ближайший переход не закрывался)' },
              { color: '#fdd0a2', text: 'до +30 мин' },
              { color: '#fd8d3c', text: '+30–60 мин' },
              { color: '#e6550d', text: '+1–2 ч' },
              { color: '#a63603', text: 'более +2 ч (гродненский пояс)' },
            ]}
            tooltip={(id) => {
              const r = t[id];
              if (!r) return names[id] ?? id;
              return `${names[id] ?? id}: до ЕС ${fmtMin(r.eu2019)} (2019) → ${fmtMin(r.euNadir)} (надир) → ${fmtMin(r.eu2026)} (2026)`;
            }}
          />
        </div>
        <div className="chart-block">
          <div className="chart-title">Что остаётся от поясов после контроля зарплаты</div>
          <div className="zone-table-wrap">
            <table className="zone-table">
              <thead>
                <tr><th>Пояс (к базе «{access.baseBelt}»)</th><th>сырой профиль</th><th>с контролями, п.п.</th><th>HC1 SE</th></tr>
              </thead>
              <tbody>
                {access.beltNames.map((b, i) => (
                  <tr key={b}>
                    <td>{b}</td>
                    <td className={profEff[b].median < 0 ? 'neg' : 'pos'}>
                      {profEff[b].median > 0 ? '+' : ''}{profEff[b].median.toFixed(1)}%
                    </td>
                    <td>{reg.beta[i + 1] > 0 ? '+' : ''}{reg.beta[i + 1].toFixed(2)}</td>
                    <td>{reg.seHc1[i + 1].toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="hint" style={{ marginTop: 8 }}>
            Контроли: ln зарплатного дифференциала (INF-03) и ln населения
            райцентра; R² {reg.r2.toFixed(2)}, n = {reg.n}. Сырой градиент
            выражен, но после контроля зарплаты пояса статистически слабы
            (|t| &lt; 2): доступность капитализируется в зарплатах и размере
            центра, а не действует отдельно от них. Кольцо 1,5–2,5 ч —
            {' '}{reg.beta[iRing].toFixed(2)} п.п. — остаётся самым глубоким
            и в модели.
          </p>
        </div>
      </div>

      {rec && sel && (
        <div className="stat-row">
          <div className="stat-tile">
            <div className="st-label">{names[sel] ?? sel} · <a href={`/?sel=${sel}`}>на карту</a></div>
            <div className="st-value">{fmtMin(rec.eff)}</div>
            <div className="st-delta">
              до {rec.minMinsk <= rec.minObl ? 'Минска' : (OBL_CENTER_NAME[rec.oblId] ?? rec.oblId)} — пояс «{rec.beltEff}»; до Минска {fmtMin(rec.minMinsk)}
            </div>
          </div>
          <div className="stat-tile">
            <div className="st-label">Доступность ЕС</div>
            <div className="st-value">{fmtMin(rec.eu2019)} → {fmtMin(rec.euNadir)}</div>
            <div className="st-delta">
              2019 → надир 2024–2025; июль 2026: {fmtMin(rec.eu2026)}
              {rec.euDeltaNadir > 0 ? ` (в надир +${Math.round(rec.euDeltaNadir)} мин)` : ' (в модельном надире без потерь)'}
            </div>
          </div>
          <div className="stat-tile">
            <div className="st-label">Динамика {access.window[0]}–{access.window[1]}</div>
            <div className="st-value">{rec.popChange > 0 ? '+' : ''}{rec.popChange.toFixed(1)}%</div>
            <div className="st-delta">
              медиана пояса «{rec.beltEff}»: {profEff[rec.beltEff].median > 0 ? '+' : ''}{profEff[rec.beltEff].median.toFixed(1)}% · зарплата {(rec.wageRel * 100).toFixed(0)}% минской
            </div>
          </div>
        </div>
      )}

      <p className="src-note">
        Время в пути — Дейкстра по дорожному графу OSM (классы
        motorway–tertiary, консервативные скорости 45–105 км/ч, без пробок
        и очередей на границе) от узла у райцентра; для районов с городом
        областного подчинения — от этого города. Доступность ЕС — время до
        ближайшего перехода, открытого для легковых автомобилей в
        соответствующий период; очереди (в 2026 — часы и сутки) не
        моделируются, поэтому фактическое ухудшение сильнее расчётного.
        Профиль корреляционный: пояс не назначен случайно. Полные
        ограничения — в методблоке и LIMITATIONS.md пакета.
      </p>
    </div>
  );
}
