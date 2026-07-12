'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { DataFile } from '@/lib/types';
import MethodDrawer from './MethodDrawer';

interface Imp { mean: number; p05: number; p95: number }
interface Driver { f: string; c: number }
interface District {
  id: string;
  oblast: string;
  ccrResid: number;
  oofPred: number;
  fact2026: number;
  ccr2026: number;
  host: number;
  topDrivers: Driver[];
  features: Record<string, number>;
}
interface Challenger {
  version: string;
  window: string;
  n: number;
  target: string;
  skill: {
    oofR2_full: number; oofR2_ctrlOnly: number; oofR2_migOnly?: number; incrementalExo: number;
    best_m: number; best_m_ctrl: number;
    repeatedCV: { median: number; p05: number; p95: number };
  };
  permutationNull: { realR2: number; p: number; null_p05: number; null_p95: number; null_median: number };
  signalDetected: boolean;
  verdict: string;
  caveat?: string;
  importance: Record<string, Imp>;
  importanceRank: string[];
  partialDependence: Record<string, [number, number][]>;
  mapeHorserace: { ccr: number; ccr_plus_ml: number; naive: number; n: number };
  goldWindow: { n: number; best_m: number; oofR2_vs_declinemean: number; features: string[]; meanLogChange: number };
  config: Record<string, number>;
  features: string[];
  exogenous: string[];
  controls: string[];
  districts: District[];
}

interface GeoFeature {
  properties: { id: string };
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][] };
}

/** Русские подписи признаков модели. */
const FEAT: Record<string, string> = {
  wage_rel19: 'Зарплата к среднереспубликанской (2019)',
  wage_gr1519: 'Рост зарплаты 2015→2019',
  access_eff: 'Транспортная доступность (мин до Минска/облцентра)',
  access_eu2019: 'Доступ к границе ЕС (2019)',
  nl_pc19: 'Ночная светимость на душу (2019)',
  nl_trend1519: 'Тренд светимости 2015→2019',
  mig_rate1519: 'Миграционное сальдо 2015–2019 (на 1000)',
  share014_19: 'Доля 0–14 (2019)',
  share65_19: 'Доля 65+ (2019)',
  lnpop19: 'ln(население 2019)',
  cher_class: 'Чернобыльский класс',
  host_flag: 'Район с городом обл. подчинения',
};

const f2 = (x: number) => x.toFixed(2);
const pctSigned = (x: number) => `${x > 0 ? '+' : ''}${(x * 100).toFixed(1)}%`;
const imp4 = (x: number) => (x * 1e4).toFixed(2);

/** Дивергентная шкала остатка CCR e = ln(факт/CCR), центр 0:
 *  положительный (CCR недооценил район) — синий; отрицательный
 *  (переоценил) — красный; около нуля — нейтральный серый. */
function residColor(v: number | null | undefined): string {
  if (v == null) return 'var(--surface-2)';
  if (v >= 0.035) return '#08519c';
  if (v >= 0.018) return '#3182bd';
  if (v >= 0.006) return '#9ecae1';
  if (v > -0.006) return '#f0f0f0';
  if (v > -0.018) return '#fcae91';
  if (v > -0.035) return '#de2d26';
  return '#a50f15';
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

/** Хороплет остатка CCR (районы adm2 + Минск adm1 как нейтральная «дыра»). */
function ResidChoro({ geo, byId, names, selected, onSelect }: {
  geo: GeoFeature[];
  byId: Record<string, District>;
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

  const hrec = hover ? byId[hover.id] : null;

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg width={width} height={height} role="img" aria-label="остаток CCR по районам">
        {paths.map((p) => (
          <path key={p.id} d={p.d}
            fill={residColor(byId[p.id]?.ccrResid)}
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
      </svg>
      {hover && (
        <div className="chart-tooltip" style={{ left: Math.min(hover.x + 14, width - 210), top: hover.y - 8 }}>
          <div className="ct-row"><span className="ct-val">{names[hover.id] ?? hover.id}</span></div>
          <div className="ct-year">
            {hrec
              ? `остаток CCR ${pctSigned(hrec.ccrResid)} — CCR ${hrec.ccrResid > 0 ? 'недооценил' : 'переоценил'}`
              : 'вне выборки (Минск)'}
          </div>
        </div>
      )}
    </div>
  );
}

/** Мини-график частной зависимости: pdp против значения признака. */
function PdpSpark({ label, pts }: { label: string; pts: [number, number][] }) {
  const w = 214, h = 118;
  const M = { top: 10, right: 10, bottom: 22, left: 40 };
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  let y0 = Math.min(...ys, 0), y1 = Math.max(...ys, 0);
  if (y1 - y0 < 1e-6) { y1 += 1e-3; y0 -= 1e-3; }
  const iw = w - M.left - M.right, ih = h - M.top - M.bottom;
  const X = (v: number) => M.left + ((v - x0) / (x1 - x0 || 1)) * iw;
  const Y = (v: number) => M.top + ih - ((v - y0) / (y1 - y0)) * ih;

  return (
    <div>
      <div className="chart-title" style={{ minHeight: 30 }}>{label}</div>
      <svg width={w} height={h} role="img" aria-label={`частная зависимость: ${label}`}>
        <line x1={M.left} x2={w - M.right} y1={Y(0)} y2={Y(0)} stroke="var(--baseline)" strokeDasharray="2 3" />
        <polyline fill="none" stroke="var(--accent)" strokeWidth="2"
          points={pts.map((p) => `${X(p[0])},${Y(p[1])}`).join(' ')} />
        <text x={M.left - 4} y={Y(y1) + 3} textAnchor="end" fontSize="8.5" fill="var(--muted)">{y1.toFixed(3)}</text>
        <text x={M.left - 4} y={Y(y0)} textAnchor="end" fontSize="8.5" fill="var(--muted)">{y0.toFixed(3)}</text>
        <text x={M.left} y={h - 6} textAnchor="start" fontSize="8.5" fill="var(--muted)">{x0.toFixed(0)}</text>
        <text x={w - M.right} y={h - 6} textAnchor="end" fontSize="8.5" fill="var(--muted)">{x1.toFixed(0)}</text>
      </svg>
    </div>
  );
}

export default function MLChallengerView() {
  const [d, setD] = useState<Challenger | null>(null);
  const [geo, setGeo] = useState<GeoFeature[] | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [sel, setSel] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return new URLSearchParams(window.location.search).get('sel');
  });

  useEffect(() => {
    fetch('/data/mlchallenger.json').then((r) => r.json()).then(setD);
    Promise.all([
      fetch('/data/geo/adm2.geojson').then((r) => r.json()),
      fetch('/data/geo/adm1.geojson').then((r) => r.json()),
    ]).then(([g2, g1]) => setGeo([
      ...g2.features.filter((f: GeoFeature) => f.properties.id.startsWith('r-')),
      ...g1.features.filter((f: GeoFeature) => f.properties.id === 'BY-HM'),
    ]));
    fetch('/data/data.json').then((r) => r.json()).then((data: DataFile) => {
      const m: Record<string, string> = {};
      for (const t of Object.values(data.territories)) m[t.id] = t.ru;
      setNames(m);
    });
  }, []);

  if (!d || !geo) return <p className="hint">Загрузка данных…</p>;

  const select = (id: string) => {
    setSel(id);
    const url = new URL(window.location.href);
    url.searchParams.set('sel', id);
    window.history.replaceState(null, '', url);
  };

  const byId: Record<string, District> = {};
  for (const r of d.districts) byId[r.id] = r;
  const rec = sel ? byId[sel] : null;

  const nm = (id: string) => (names[id] ?? id).replace(' район', '');
  const impRows = [...d.importanceRank, ...d.controls];
  const impMax = Math.max(...impRows.map((k) => Math.max(0, d.importance[k]?.mean ?? 0)));
  const influential = (im: Imp) => im.p05 > 0;

  // крайние остатки: районы, где CCR ошибается сильнее всего в обе стороны
  const sortedResid = [...d.districts].sort((a, b) => b.ccrResid - a.ccrResid);
  const extremes = [...sortedResid.slice(0, 6), ...sortedResid.slice(-6).reverse()];

  const hr = d.mapeHorserace;
  const hrMax = Math.max(hr.ccr, hr.ccr_plus_ml, hr.naive);
  const hrRows = [
    { t: 'CCR (структурная)', v: hr.ccr, best: false },
    { t: 'CCR + ML-коррекция', v: hr.ccr_plus_ml, best: true },
    { t: 'наивная (без изменений)', v: hr.naive, best: false },
  ];

  return (
    <div>
      <div className="controls" style={{ marginBottom: 6 }}>
        <MethodDrawer slug="mlchallenger" label="Методика" />
      </div>

      {/* (A) вердикт-баннер */}
      <div className="prob-panel" style={{ borderLeftColor: d.signalDetected ? '#08519c' : 'var(--baseline)' }}>
        <div className="prob-head">
          Диагностический вердикт · {d.signalDetected ? 'сигнал обнаружен' : 'сигнал не обнаружен'} · окно {d.window}
        </div>
        <div style={{ fontSize: 15, fontWeight: 650, margin: '4px 0 2px' }}>{d.verdict}</div>
        <div className="prob-rows">
          <span>перестановочный p <b>{d.permutationNull.p}</b> (нуль-полоса [{d.permutationNull.null_p05.toFixed(2)}; {d.permutationNull.null_p95.toFixed(2)}])</span>
          <span>повторная CV <b>{f2(d.skill.repeatedCV.median)}</b> [{f2(d.skill.repeatedCV.p05)}; {f2(d.skill.repeatedCV.p95)}]</span>
        </div>
        <div className="prob-note">
          Мишень e = {d.target}. R² измерен вне выборки (OOF); заявление о сигнале
          гейтится перестановочным нулём — реальный R² лежит далеко за верхней
          границей нуль-полосы.
        </div>
      </div>

      <div className="stat-row" style={{ marginTop: 12 }}>
        <div className="stat-tile">
          <div className="st-label">OOF R² (полная)</div>
          <div className="st-value">{f2(d.skill.oofR2_full)}</div>
          <div className="st-delta">ковариаты ≤2019 объясняют ~треть дисперсии остатка CCR</div>
        </div>
        <div className="stat-tile">
          <div className="st-label">Только структура</div>
          <div className="st-value">{f2(d.skill.oofR2_ctrlOnly)}</div>
          <div className="st-delta">возраст, размер, Чернобыль, host — без экзогенных</div>
        </div>
        <div className="stat-tile">
          <div className="st-label">Прирост от экзогенных</div>
          <div className="st-value">+{f2(d.skill.incrementalExo)}</div>
          <div className="st-delta">зарплата, доступность, миграция, свет сверх структуры</div>
        </div>
      </div>

      {/* (B) хороплет + (C-помощь) крайние остатки */}
      <div className="grid-2">
        <div className="chart-block">
          <div className="chart-title">Остаток CCR по районам: где структурная модель систематически мимо</div>
          <ResidChoro geo={geo} byId={byId} names={names} selected={sel} onSelect={select} />
          <div className="choro-legend">
            <span className="cl-item"><span className="cl-swatch" style={{ background: '#08519c' }} />синий — CCR недооценил район (факт &gt; CCR)</span>
            <span className="cl-item"><span className="cl-swatch" style={{ background: '#f0f0f0' }} />около нуля</span>
            <span className="cl-item"><span className="cl-swatch" style={{ background: '#a50f15' }} />красный — CCR переоценил (факт &lt; CCR)</span>
            <span className="cl-item"><span className="cl-swatch" style={{ background: 'var(--surface-2)' }} />Минск — вне выборки</span>
          </div>
        </div>
        <div className="chart-block">
          <div className="chart-title">Крайние остатки: наибольшая систематическая ошибка CCR (нажмите район)</div>
          <div className="zone-table-wrap">
            <table className="zone-table">
              <thead>
                <tr><th>Район</th><th>остаток</th><th>факт-2026</th><th>CCR-2026</th></tr>
              </thead>
              <tbody>
                {extremes.map((r) => (
                  <tr key={r.id} className={r.id === sel ? 'sel' : ''}
                    onClick={() => select(r.id)} style={{ cursor: 'pointer' }}>
                    <td>{nm(r.id)}</td>
                    <td className={r.ccrResid > 0 ? 'pos' : 'neg'}>{pctSigned(r.ccrResid)}</td>
                    <td>{r.fact2026.toLocaleString('ru-RU')}</td>
                    <td>{r.ccr2026.toLocaleString('ru-RU')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="hint" style={{ marginTop: 8 }}>
            Синий (положительный остаток) — официальная оценка-2026 выше CCR:
            район удержал людей лучше, чем предсказывает чистая демография.
            Красный — наоборот. Знак почти всюду тянет миграция.
          </p>
        </div>
      </div>

      {/* (C) панель выбранного района */}
      {rec && sel && (
        <div className="chart-block">
          <div className="chart-title">
            {nm(sel)} · <a href={`/map?sel=${sel}`}>на карту</a>{rec.host ? ' · район с городом обл. подчинения' : ''}
          </div>
          <div className="stat-row">
            <div className="stat-tile">
              <div className="st-label">Остаток CCR (факт)</div>
              <div className="st-value">{pctSigned(rec.ccrResid)}</div>
              <div className="st-delta">{rec.ccrResid > 0 ? 'CCR недооценил район' : 'CCR переоценил район'}</div>
            </div>
            <div className="stat-tile">
              <div className="st-label">Предсказание OOF</div>
              <div className="st-value">{pctSigned(rec.oofPred)}</div>
              <div className="st-delta">оценка остатка моделью вне обучения</div>
            </div>
            <div className="stat-tile">
              <div className="st-label">Факт-2026 / CCR-2026</div>
              <div className="st-value" style={{ fontSize: 15 }}>{rec.fact2026.toLocaleString('ru-RU')}</div>
              <div className="st-delta">против {rec.ccr2026.toLocaleString('ru-RU')} по CCR</div>
            </div>
          </div>
          <div className="prob-panel">
            <div className="prob-head">Что тянет остаток (топ-драйверы SHAP-стиля)</div>
            <div className="prob-rows">
              {rec.topDrivers.map((dr) => (
                <span key={dr.f}>{FEAT[dr.f] ?? dr.f} <b>{dr.c > 0 ? '+' : ''}{(dr.c * 100).toFixed(2)} п.п.</b></span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* (D) перестановочная важность признаков */}
      <div className="chart-block">
        <div className="chart-title">Перестановочная важность признаков (прирост OOF-MSE, ×10⁻⁴; полоса — 5/95 повторов)</div>
        <div className="zone-table-wrap">
          <table className="zone-table">
            <thead>
              <tr><th>Признак</th><th>важность</th><th>[p05; p95]</th><th>ранг</th><th>вердикт</th></tr>
            </thead>
            <tbody>
              {impRows.map((k) => {
                const im = d.importance[k];
                if (!im) return null;
                const inf = influential(im);
                const isCtrl = d.controls.includes(k);
                return (
                  <tr key={k}>
                    <td>{FEAT[k] ?? k}{isCtrl ? ' · структура' : ''}</td>
                    <td className={inf ? 'pos' : ''}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                        <span style={{
                          display: 'inline-block', height: 8, borderRadius: 2,
                          width: Math.max(2, (Math.max(0, im.mean) / (impMax || 1)) * 60),
                          background: inf ? '#08519c' : 'var(--baseline)',
                        }} />
                        {imp4(im.mean)}
                      </span>
                    </td>
                    <td>[{imp4(im.p05)}; {imp4(im.p95)}]</td>
                    <td>{isCtrl || !inf ? '—' : d.importanceRank.indexOf(k) + 1}</td>
                    <td>
                      {inf
                        ? <span className="badge" style={{ borderColor: '#08519c', color: '#08519c' }}>сигнал</span>
                        : <span className="badge">в пределах шума</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="hint" style={{ marginTop: 6 }}>
          «Сигнал» = нижняя граница полосы p05 &gt; 0 (важность устойчиво положительна
          на повторах). Среди экзогенных этому критерию удовлетворяет только
          миграционное сальдо; из структурных — ln(население). Остальное неотличимо
          от перестановочного шума и в выводах не участвует.
        </p>
      </div>

      {/* (E) частные зависимости */}
      <div className="chart-block">
        <div className="chart-title">Частная зависимость остатка от трёх ведущих экзогенных признаков</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 18 }}>
          {Object.keys(d.partialDependence).map((k) => (
            <PdpSpark key={k} label={FEAT[k] ?? k} pts={d.partialDependence[k]} />
          ))}
        </div>
        <p className="hint" style={{ marginTop: 6 }}>
          Пунктир — нулевой уровень остатка. Наклон миграционного сальдо — самый
          крутой и монотонный: чем сильнее район терял людей до 2019-го, тем ниже
          официальная оценка-2026 относительно CCR.
        </p>
      </div>

      {/* (F) гонка прогноза — второстепенно */}
      <div className="chart-block">
        <div className="chart-title">Гонка прогноза MAPE, % (второстепенно, n={hr.n})</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxWidth: 460 }}>
          {hrRows.map((row) => (
            <div key={row.t} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5 }}>
              <span style={{ width: 168, color: 'var(--ink-2)' }}>{row.t}</span>
              <span style={{
                height: 14, borderRadius: 3, flex: 'none',
                width: `${(row.v / hrMax) * 200}px`,
                background: 'var(--baseline)',
              }} />
              <b style={{ fontVariantNumeric: 'tabular-nums' }}>{row.v.toFixed(2)}%</b>
            </div>
          ))}
        </div>
        <p className="hint" style={{ marginTop: 6 }}>
          ML-коррекция снижает MAPE CCR с {hr.ccr.toFixed(2)}% до {hr.ccr_plus_ml.toFixed(2)}%, но
          выигрыш 0,5 п.п. на n=118 (~6 фолдов) как единичное число лежит{' '}
          <strong>в пределах CV-шума</strong>; таблица <strong>намеренно понижена в ранге</strong>:
          единственная перепись-транзиция не даёт права называть коррекцию рабочим прогнозным
          инструментом — это лишь иллюстрация того, что найденная ошибка предсказуема, а не
          прогнозное превосходство.
        </p>
      </div>

      {/* (G) честная оговорка */}
      <p className="src-note">
        Мишень — ошибка структурной модели CCR относительно ОФИЦИАЛЬНОЙ
        оценки-2026, а не «истины»: официальная оценка сама учитывает миграцию,
        которую CCR игнорирует, поэтому обнаруженная систематическая ошибка означает
        прежде всего, что CCR недо-использует миграционную динамику. Одно только
        миграционное сальдо даёт OOF R²={(d.skill.oofR2_migOnly ?? 0).toFixed(2)} ≈ всю
        модель ({d.skill.oofR2_full.toFixed(2)}) — сигнал почти целиком миграционный, и
        перепись→перепись окно 2009→2019 (без миграционных признаков, R²≈
        {d.goldWindow.oofR2_vs_declinemean.toFixed(2)}) НЕ проверяет его против настоящего
        счёта. Это диагностика на 7-летнем окне (единственная перепись-транзиция — одна),
        а НЕ конкурирующий прогноз и НЕ инструмент на 50 лет. Все признаки датированы
        ≤2019; каждое заявление гейтится перестановочным нулём.
      </p>
    </div>
  );
}
