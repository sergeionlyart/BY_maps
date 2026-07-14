'use client';

/**
 * INF-08 v2 «Беларусь из космоса, 1992–2075».
 *
 * Таймлайн из предрендеренных PNG-кадров (web/public/data/nl_frames):
 * ретро DMSP 1992–2011 → VIIRS 2012–2024 → МОДЕЛЬ 2030–2075 (узлы шага
 * 5 лет, 3 сценария × 2 стартовых ряда). Кадры — сетка вырезки VNL
 * (EPSG:4326); правильный аспект достигается только масштабом по оси X
 * (равномерное cos(широты) сжатие), геометрия ряда неподвижна.
 *
 * Гарантия честности будущего (ТЗ T-13): в PNG будущих лет уже впечатаны
 * штриховая рамка и бейдж «МОДЕЛЬ + сценарий»; поверх кадра UI дублирует
 * маркер бейджем и штриховой рамкой — модельный кадр невозможно
 * заскриншотить без маркера.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { DataFile } from '@/lib/types';
import MethodDrawer from './MethodDrawer';
import { useT, useLang } from '@/lib/i18n';

const SCN_LABEL: Record<string, string> = {
  base: 'базовый', negative: 'негативный', optimistic: 'оптимистичный',
};
const JMP_LABEL: Record<string, string> = {
  official: 'официальный', adjusted: 'скорректированный',
};

interface ModelPoint { l: number; ls: number; ps: number }
interface Row {
  id: string;
  lshare: Record<string, number>;
  pshare: Record<string, number>;
  light: Record<string, number>;
  lightRatio: number | null;
  popRatio: number | null;
  div: number | null;
  model: Record<string, Record<string, Record<string, ModelPoint>>>;
}
interface NightV2 {
  version: string;
  segments: { dmsp: [number, number]; vnl: [number, number]; model: [number, number] };
  yearsObs: number[];
  nodes: number[];
  scenarios: string[];
  jumpoffs: string[];
  trendYears: [number, number];
  shockYears: number[];
  mapping: { aBar: number; b: number; f18: number; r2: number };
  source: Record<string, string>;
  natLight: Record<string, number>;
  natPop: Record<string, number>;
  natModel: Record<string, Record<string, Record<string, number>>>;
  rows: Row[];
}
interface FramesMeta {
  bounds: [number, number, number, number]; // W, S, E, N
  width: number; height: number;
}
interface GeoFeature {
  properties: { id: string };
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][] };
}

function frameSrc(stop: number, isModel: boolean, scn: string, jmp: string): string {
  return isModel
    ? `/data/nl_frames/m${stop}_${scn}_${jmp}.png`
    : `/data/nl_frames/y${stop}.png`;
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

/** Слайдер по остановкам таймлайна с зонами DMSP/VIIRS/МОДЕЛЬ и play. */
function SpaceTimebar({ stops, idx, obsCount, onChange, playing, setPlaying }: {
  stops: number[]; idx: number; obsCount: number;
  onChange: (i: number) => void;
  playing: boolean; setPlaying: (p: boolean) => void;
}) {
  const t = useT();
  const raf = useRef<number>(0);
  const idxRef = useRef(idx);
  idxRef.current = idx;

  useEffect(() => {
    if (!playing) return;
    let last = performance.now();
    const tick = (now: number) => {
      const inModel = idxRef.current >= obsCount - 1;
      if (now - last > (inModel ? 700 : 430)) {
        last = now;
        const next = idxRef.current + 1;
        if (next >= stops.length) { setPlaying(false); return; }
        onChange(next);
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [playing, onChange, stops.length, obsCount, setPlaying]);

  const pct = (i: number) => (i / (stops.length - 1)) * 100;
  const dmspEnd = stops.indexOf(2012); // первая остановка VIIRS
  const marks = [1992, 2000, 2012, 2024, 2050, 2075];

  return (
    <div className="timebar nlv2-timebar">
      <button className="play-btn" onClick={() => {
        if (!playing && idx >= stops.length - 1) onChange(0);
        setPlaying(!playing);
      }} aria-label={playing ? t('пауза') : t('воспроизвести')}>
        {playing ? '❚❚' : '▶'}
      </button>
      <div className="year-display">
        {stops[idx]}
        {idx >= obsCount && <span className="forecast-flag">{t('модель')}</span>}
      </div>
      <div className="slider-zone">
        <div className="nlv2-zone nlv2-zone-dmsp" style={{ left: 0, width: `${pct(dmspEnd)}%` }} />
        <div className="nlv2-zone nlv2-zone-vnl" style={{ left: `${pct(dmspEnd)}%`, width: `${pct(obsCount - 1) - pct(dmspEnd)}%` }} />
        <div className="nlv2-zone nlv2-zone-model" style={{ left: `${pct(obsCount - 1)}%`, width: `${100 - pct(obsCount - 1)}%` }} />
        <input type="range" min={0} max={stops.length - 1} step={1} value={idx}
          onChange={(e) => onChange(+e.target.value)} aria-label={t('год')} />
        <div className="slider-ticks">
          {marks.map((y) => {
            const i = stops.indexOf(y);
            return i >= 0 && (
              <span key={y} className="tick-major" style={{ left: `${pct(i)}%` }}
                onClick={() => onChange(i)}>{y}</span>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/** Сцена кадра: кроссфейд, оверлей районов, маркер сегмента, A/B-шторка. */
function FrameStage({ meta, src, prevSrc, seg, scnText, abSrc, abLabel, curLabel,
  geo, sel, onSelect, names, showBorders }: {
  meta: FramesMeta; src: string; prevSrc: string | null;
  seg: 'dmsp' | 'vnl' | 'model'; scnText: string;
  abSrc: string | null; abLabel?: string; curLabel?: string;
  geo: GeoFeature[] | null; sel: string | null;
  onSelect: (id: string) => void; names: Record<string, string>;
  showBorders: boolean;
}) {
  const t = useT();
  const [wrapRef, width] = useWidth(720);
  const [split, setSplit] = useState(0.5);
  const dragging = useRef(false);
  const [hover, setHover] = useState<string | null>(null);

  const [W, S, E, N] = meta.bounds;
  const kx = Math.cos(((S + N) / 2) * Math.PI / 180);
  const aspect = ((E - W) * kx) / (N - S);
  const height = Math.round(width / aspect);
  const X = (lon: number) => ((lon - W) / (E - W)) * width;
  const Y = (lat: number) => ((N - lat) / (N - S)) * height;

  const paths = useMemo(() => {
    if (!geo) return [];
    return geo.map((f) => {
      const polys = f.geometry.type === 'Polygon'
        ? [f.geometry.coordinates as number[][][]]
        : (f.geometry.coordinates as number[][][][]);
      let d = '';
      for (const poly of polys) for (const ring of poly) {
        d += ring.map(([lon, lat], i) =>
          `${i ? 'L' : 'M'}${X(lon).toFixed(1)},${Y(lat).toFixed(1)}`).join('') + 'Z';
      }
      return { id: f.properties.id, d };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geo, width, height]);

  const onDrag = useCallback((e: React.PointerEvent) => {
    if (!dragging.current || !wrapRef.current) return;
    const box = wrapRef.current.getBoundingClientRect();
    setSplit(Math.min(0.98, Math.max(0.02, (e.clientX - box.left) / box.width)));
  }, [wrapRef]);

  return (
    <div ref={wrapRef} className={`nlv2-stage nlv2-seg-${seg}`}
      style={{ height }}
      onPointerMove={abSrc ? onDrag : undefined}
      onPointerUp={() => { dragging.current = false; }}>
      {prevSrc && <img src={prevSrc} alt="" className="nlv2-frame" draggable={false} />}
      <img key={src} src={src} alt={t('карта ночной светимости')}
        className="nlv2-frame nlv2-frame-fade" draggable={false} />
      {abSrc && (
        <>
          <div className="nlv2-ab-top" style={{ clipPath: `inset(0 ${100 - split * 100}% 0 0)` }}>
            <img src={abSrc} alt="" className="nlv2-frame" draggable={false} />
          </div>
          <div className="nlv2-ab-divider" style={{ left: `${split * 100}%` }}
            onPointerDown={(e) => { dragging.current = true; (e.target as HTMLElement).setPointerCapture(e.pointerId); }}>
            <span>⇔</span>
          </div>
          <div className="nlv2-ab-label" style={{ left: 8 }}>{abLabel}</div>
          <div className="nlv2-ab-label" style={{ right: 8 }}>{curLabel}</div>
        </>
      )}
      {!abSrc && (
        <svg className="nlv2-overlay" width={width} height={height}>
          {paths.map((p) => (
            <path key={p.id} d={p.d} fill="transparent"
              stroke={p.id === sel ? 'var(--accent-2)' : hover === p.id ? '#e8c896'
                : showBorders ? 'rgba(180,160,130,0.25)' : 'transparent'}
              strokeWidth={p.id === sel ? 2 : 1}
              style={{ cursor: 'pointer' }}
              onPointerEnter={() => setHover(p.id)}
              onPointerLeave={() => setHover(null)}
              onClick={() => onSelect(p.id)}>
              <title>{names[p.id] ?? p.id}</title>
            </path>
          ))}
        </svg>
      )}
      <div className={`nlv2-badge nlv2-badge-${seg}`}>
        {seg === 'dmsp' && t('DMSP · ретро, грубее')}
        {seg === 'vnl' && t('VIIRS · наблюдение')}
        {seg === 'model' && <>{t('МОДЕЛЬ')} · {scnText}</>}
      </div>
      {seg === 'model' && <div className="nlv2-model-border" />}
    </div>
  );
}

/** Карточка района: доли в свете и населении 1992→2075. */
function LongSpark({ row, night, scn, jmp }: {
  row: Row; night: NightV2; scn: string; jmp: string;
}) {
  const t = useT();
  const [wrapRef, width] = useWidth(640);
  const height = 230;
  const M = { top: 16, right: 20, bottom: 26, left: 40 };
  const iw = width - M.left - M.right, ih = height - M.top - M.bottom;

  const obsL = night.yearsObs
    .filter((y) => row.lshare[String(y)] != null)
    .map((y) => ({ y, v: row.lshare[String(y)] }));
  const obsP = Object.keys(row.pshare).map(Number).sort((a, b) => a - b)
    .filter((y) => y >= 1992 && y <= 2026)
    .map((y) => ({ y, v: row.pshare[String(y)] }));
  const mod = night.nodes.map((n) => ({ y: n, ...row.model[jmp][scn][String(n)] }));

  const baseY = obsP.find((p) => p.y >= 1999)?.y ?? obsP[0]?.y;
  const baseL = row.lshare[String(baseY)] || obsL[0]?.v || 1e-9;
  const baseP = row.pshare[String(baseY)] || 1e-9;
  const idxL = (v: number) => (v / baseL) * 100;
  const idxP = (v: number) => (v / baseP) * 100;

  const allVals = [...obsL.map((p) => idxL(p.v)), ...obsP.map((p) => idxP(p.v)),
    ...mod.map((p) => idxL(p.ls)), ...mod.map((p) => idxP(p.ps))];
  const y0 = Math.min(60, Math.floor(Math.min(...allVals) / 20) * 20);
  const y1 = Math.max(140, Math.ceil(Math.max(...allVals) / 20) * 20);
  const X = (y: number) => M.left + ((y - 1992) / (2075 - 1992)) * iw;
  const Y = (v: number) => M.top + ih - ((v - y0) / (y1 - y0)) * ih;
  const pts = (arr: { y: number; v: number }[], f: (v: number) => number) =>
    arr.map((p) => `${X(p.y).toFixed(1)},${Y(f(p.v)).toFixed(1)}`).join(' ');

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg width={width} height={height} role="img" aria-label={t('доли района: свет и население, 1992–2075')}>
        {[y0, 100, y1].filter((v, i, a) => a.indexOf(v) === i).map((v) => (
          <g key={v}>
            <line x1={M.left} x2={width - M.right} y1={Y(v)} y2={Y(v)}
              stroke={v === 100 ? 'var(--baseline)' : 'var(--grid)'} strokeDasharray={v === 100 ? '' : '3 4'} />
            <text x={M.left - 4} y={Y(v) + 3} textAnchor="end" fontSize="9" fill="var(--muted)">{v}</text>
          </g>
        ))}
        {/* зоны сегментов */}
        <rect x={X(1992)} y={M.top} width={X(2011.5) - X(1992)} height={ih} fill="var(--surface-2)" opacity="0.35" />
        <rect x={X(2027)} y={M.top} width={X(2075) - X(2027)} height={ih} fill="var(--accent-2)" opacity="0.06" />
        <line x1={X(2027)} x2={X(2027)} y1={M.top} y2={M.top + ih} stroke="var(--accent-2)" strokeDasharray="3 4" opacity="0.7" />
        <text x={X(2002)} y={M.top - 4} fontSize="8.5" fill="var(--muted)" textAnchor="middle">{t('ретро (DMSP)')}</text>
        <text x={X(2051)} y={M.top - 4} fontSize="8.5" fill="var(--accent-2)" textAnchor="middle">{t('МОДЕЛЬ')}</text>
        <polyline fill="none" stroke="#e6a817" strokeWidth="2" points={pts(obsL, idxL)} />
        <polyline fill="none" stroke="#5698b9" strokeWidth="2" points={pts(obsP, idxP)} />
        <polyline fill="none" stroke="#e6a817" strokeWidth="2" strokeDasharray="5 4"
          points={pts(mod.map((p) => ({ y: p.y, v: p.ls })), idxL)} />
        <polyline fill="none" stroke="#5698b9" strokeWidth="1.6" strokeDasharray="2 4"
          points={pts(mod.map((p) => ({ y: p.y, v: p.ps })), idxP)} />
        {[1992, 2010, 2024, 2050, 2075].map((y) => (
          <text key={y} x={X(y)} y={height - 8} textAnchor="middle" fontSize="9" fill="var(--muted)">{y}</text>
        ))}
        <text x={M.left} y={height - 8} fontSize="8.5" fill="var(--muted)">{baseY} = 100</text>
        <g transform={`translate(${width - M.right - 150}, ${M.top + 2})`}>
          <line x1="0" y1="4" x2="18" y2="4" stroke="#e6a817" strokeWidth="2" />
          <text x="22" y="7" fontSize="9" fill="var(--ink-2)">{t('доля в свете')}</text>
          <line x1="0" y1="18" x2="18" y2="18" stroke="#5698b9" strokeWidth="2" />
          <text x="22" y="21" fontSize="9" fill="var(--ink-2)">{t('доля в населении')}</text>
        </g>
      </svg>
    </div>
  );
}

export default function NightlightsV2View() {
  const t = useT();
  const lang = useLang();
  const [night, setNight] = useState<NightV2 | null>(null);
  const [meta, setMeta] = useState<FramesMeta | null>(null);
  const [geo, setGeo] = useState<GeoFeature[] | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [idx, setIdx] = useState(0);
  const [scn, setScn] = useState('base');
  const [jmp, setJmp] = useState('official');
  const [sel, setSel] = useState<string | null>(null);
  const [ab, setAb] = useState(false);
  const [abFrom, setAbFrom] = useState(1997);
  const [playing, setPlaying] = useState(false);
  const [showBorders, setShowBorders] = useState(true);
  const prevSrcRef = useRef<string | null>(null);

  // загрузка данных + deep-link ?year=&scenario=&jumpoff=&sel=
  useEffect(() => {
    Promise.all([
      fetch('/data/nightlights_v2.json').then((r) => r.json()),
      fetch('/data/nl_frames/meta.json').then((r) => r.json()),
    ]).then(([n, m]: [NightV2, FramesMeta]) => {
      setNight(n); setMeta(m);
      const q = new URLSearchParams(window.location.search);
      const stops = [...n.yearsObs, ...n.nodes];
      const wantY = Number(q.get('year'));
      if (wantY) {
        let best = 0, dist = 1e9;
        stops.forEach((y, i) => { const d = Math.abs(y - wantY); if (d < dist) { dist = d; best = i; } });
        setIdx(best);
      } else {
        setIdx(n.yearsObs.length - 1); // старт: свежайшее наблюдение
      }
      if (n.scenarios.includes(q.get('scenario') ?? '')) setScn(q.get('scenario')!);
      if (n.jumpoffs.includes(q.get('jumpoff') ?? '')) setJmp(q.get('jumpoff')!);
      if (q.get('sel')) setSel(q.get('sel'));
    });
    Promise.all([
      fetch('/data/geo/adm2.geojson').then((r) => r.json()),
      fetch('/data/geo/adm1.geojson').then((r) => r.json()),
    ]).then(([g2, g1]) => setGeo([
      ...g2.features.filter((f: GeoFeature) => f.properties.id.startsWith('r-')),
      ...g1.features.filter((f: GeoFeature) => f.properties.id === 'BY-HM'),
    ]));
    fetch('/data/data.json').then((r) => r.json()).then((d: DataFile) => {
      const m: Record<string, string> = {};
      for (const tt of Object.values(d.territories)) m[tt.id] = lang === 'be' && tt.be ? tt.be : tt.ru;
      setNames(m);
    });
  }, [lang]);

  const stops = useMemo(
    () => (night ? [...night.yearsObs, ...night.nodes] : []), [night]);
  const obsCount = night?.yearsObs.length ?? 0;
  const isModel = idx >= obsCount;
  const stop = stops[idx] ?? 2024;
  const seg: 'dmsp' | 'vnl' | 'model' = isModel ? 'model'
    : stop <= (night?.segments.dmsp[1] ?? 2011) ? 'dmsp' : 'vnl';

  // deep-link sync
  useEffect(() => {
    if (!night) return;
    const url = new URL(window.location.href);
    url.searchParams.set('year', String(stop));
    url.searchParams.set('scenario', scn);
    url.searchParams.set('jumpoff', jmp);
    if (sel) url.searchParams.set('sel', sel); else url.searchParams.delete('sel');
    window.history.replaceState(null, '', url);
  }, [night, stop, scn, jmp, sel]);

  // префетч ±3 кадров
  useEffect(() => {
    if (!night) return;
    for (let d = -3; d <= 3; d++) {
      const i = idx + d;
      if (i < 0 || i >= stops.length || i === idx) continue;
      const im = new Image();
      im.src = frameSrc(stops[i], i >= obsCount, scn, jmp);
    }
  }, [night, idx, stops, obsCount, scn, jmp]);

  const src = frameSrc(stop, isModel, scn, jmp);
  useEffect(() => { prevSrcRef.current = src; }, [src]);

  const changeIdx = useCallback((i: number) => setIdx(i), []);

  if (!night || !meta) return <p className="hint">{t('Загрузка данных…')}</p>;

  const rowById: Record<string, Row> = {};
  for (const r of night.rows) rowById[r.id] = r;
  const rec = sel ? rowById[sel] : null;

  // топ-5 гаснущих/разгорающихся за окно (обсервации: от начала сегмента
  // VIIRS либо от 1992 до текущего года; в модели — 2024 → узел)
  const winFrom = isModel ? 2024 : 1992;
  const winTo = stop;
  const movers = (() => {
    const bright = [...night.rows]
      .sort((a, b) => (b.light['2024'] ?? 0) - (a.light['2024'] ?? 0))
      .slice(0, 30);
    const delta = (r: Row): number | null => {
      const s0 = r.lshare[String(winFrom)];
      const s1 = isModel ? r.model[jmp][scn][String(winTo)]?.ls : r.lshare[String(winTo)];
      return s0 && s1 ? Math.log(s1 / s0) : null;
    };
    const ranked = bright.map((r) => ({ r, d: delta(r) }))
      .filter((x): x is { r: Row; d: number } => x.d != null)
      .sort((a, b) => a.d - b.d);
    return { fading: ranked.slice(0, 5), rising: ranked.slice(-5).reverse() };
  })();

  const abStopB = stop; // «B» — текущая позиция слайдера
  const abSrcA = ab ? frameSrc(abFrom, false, scn, jmp) : null;

  const scnText = `${t(SCN_LABEL[scn])} · ${t('старт')}: ${t(JMP_LABEL[jmp])}`;

  return (
    <div className="nlv2">
      <div className="controls" style={{ marginBottom: 6 }}>
        <MethodDrawer slug="nightlights" />
        <a className="btn" href="/artifacts/by-maps-nightlights-v2.0.0.zip" download>
          ⬇ {t('Проверяемый пакет (ZIP)')}
        </a>
        <label className="nlv2-check">
          <input type="checkbox" checked={showBorders} onChange={(e) => setShowBorders(e.target.checked)} />
          {t('границы районов')}
        </label>
        <label className="nlv2-check">
          <input type="checkbox" checked={ab} onChange={(e) => { setAb(e.target.checked); setPlaying(false); }} />
          {t('сравнение A/B')}
        </label>
      </div>

      {ab && (
        <div className="controls nlv2-ab-controls">
          <span className="hint">{t('A (левая сторона):')}</span>
          {[1992, 1997, 2005, 2013, 2024].map((y) => (
            <button key={y} className={`btn ${abFrom === y ? 'primary' : ''}`}
              onClick={() => setAbFrom(y)}>{y}</button>
          ))}
          <span className="hint">{t('B — позиция слайдера')}: {abStopB}</span>
        </div>
      )}

      <FrameStage meta={meta} src={src} prevSrc={prevSrcRef.current !== src ? prevSrcRef.current : null}
        seg={seg} scnText={scnText}
        abSrc={abSrcA} abLabel={String(abFrom)} curLabel={String(abStopB)}
        geo={geo} sel={sel} onSelect={(id) => setSel(id === sel ? null : id)}
        names={names} showBorders={showBorders} />

      <SpaceTimebar stops={stops} idx={idx} obsCount={obsCount}
        onChange={changeIdx} playing={playing} setPlaying={setPlaying} />

      <div className="controls nlv2-scn" aria-hidden={!isModel && !ab}>
        <span className="hint">{t('Сценарий модели:')}</span>
        {night.scenarios.map((s) => (
          <button key={s} className={`btn scn-${s} ${scn === s ? 'active' : ''}`}
            onClick={() => setScn(s)}>{t(SCN_LABEL[s])}</button>
        ))}
        <span className="hint" style={{ marginLeft: 10 }}>{t('Стартовый ряд:')}</span>
        {night.jumpoffs.map((j) => (
          <button key={j} className={`btn ${jmp === j ? 'primary' : ''}`}
            onClick={() => setJmp(j)}>{t(JMP_LABEL[j])}</button>
        ))}
      </div>

      <div className="grid-2" style={{ marginTop: 12 }}>
        <div className="chart-block">
          <div className="chart-title">
            {t('Топ-5 гаснущих и разгорающихся (доля в свете),')} {winFrom} → {winTo}
            {isModel && <span className="forecast-flag" style={{ marginLeft: 6 }}>{t('модель')}</span>}
          </div>
          <div className="nlv2-movers">
            <div>
              <div className="nlv2-movers-h">{t('гаснут')}</div>
              {movers.fading.map(({ r, d }) => (
                <button key={r.id} className="nlv2-mover neg" onClick={() => setSel(r.id)}>
                  {(names[r.id] ?? r.id).replace(' район', '')} <span>{(Math.expm1(d) * 100).toFixed(0)}%</span>
                </button>
              ))}
            </div>
            <div>
              <div className="nlv2-movers-h">{t('разгораются')}</div>
              {movers.rising.map(({ r, d }) => (
                <button key={r.id} className="nlv2-mover pos" onClick={() => setSel(r.id)}>
                  {(names[r.id] ?? r.id).replace(' район', '')} <span>{d >= 0 ? '+' : ''}{(Math.expm1(d) * 100).toFixed(0)}%</span>
                </button>
              ))}
            </div>
          </div>
          <p className="hint">
            {t('Среди 30 крупнейших по светимости районов; малые сельские шумны. Доля в национальном свете, не абсолют.')}
            {isModel && ' ' + t('Будущее — модель: свет следует за населением прогноза при прочих равных.')}
          </p>
        </div>

        <div className="chart-block">
          <div className="chart-title">{t('Три природы данных на одном таймлайне')}</div>
          <table className="zone-table">
            <tbody>
              <tr><td><span className="nlv2-dot nlv2-dot-dmsp" /> DMSP</td>
                <td>{night.segments.dmsp[0]}–{night.segments.dmsp[1]}</td>
                <td>{t('ретро, грубее: сатурация центров, ~1 км')}</td></tr>
              <tr><td><span className="nlv2-dot nlv2-dot-vnl" /> VIIRS</td>
                <td>{night.segments.vnl[0]}–{night.segments.vnl[1]}</td>
                <td>{t('современный сенсор, 500 м, радиансность')}</td></tr>
              <tr><td><span className="nlv2-dot nlv2-dot-model" /> {t('МОДЕЛЬ')}</td>
                <td>{night.segments.model[0]}–{night.segments.model[1]}</td>
                <td>{t('иллюстрация прогноза населения v2026.4, не предсказание света')}</td></tr>
            </tbody>
          </table>
          <p className="hint">
            {t('Стык DMSP→VIIRS — калибровка-«мост» по перекрытию продуктов simVIIRS/VNL 2014–2024 (R² ')}{night.mapping.r2.toFixed(2)}
            {t('); прямое перекрытие сенсоров 2012–2013 грубее (R² долей ~0,78) и для стыковки не используется. Ряд един в радианс-эквиваленте, сегменты помечены. Годовой композит 2025 на дату выпуска не опубликован.')}
          </p>
        </div>
      </div>

      {rec && sel && (
        <div className="chart-block">
          <div className="chart-title">
            {names[sel] ?? sel} · <a href={`/map?sel=${sel}`}>{t('на карту')}</a>
            {t(' — доля в свете против доли в населении, 1992–2075')}
          </div>
          <LongSpark row={rec} night={night} scn={scn} jmp={jmp} />
          {rec.div != null && (
            <p className="hint">
              {t('Индекс расхождения 2022–2023 к тренду 2015–2019:')} {rec.div > 0 ? '+' : ''}{(rec.div * 100).toFixed(0)}%.
              {rec.div < -0.05 ? ' ' + t('Доля света отстаёт от доли населения — кандидат на недоучёт оттока или деиндустриализацию.')
                : rec.div > 0.05 ? ' ' + t('Доля света держится лучше доли населения — вероятно рост промышленной/инфраструктурной активности.')
                  : ' ' + t('Доля света и доля населения движутся согласованно.')}
              {' '}{t('Будущий сегмент кривой — модель (штрих), сценарий')} «{t(SCN_LABEL[scn])}».
            </p>
          )}
        </div>
      )}

      <div className="grid-2" style={{ marginTop: 12 }}>
        <div className="chart-block">
          <div className="chart-title">
            <span className="chip chip-data">{t('Данные')}</span> {t('Наблюдение, 1992–2024')}
          </div>
          <p className="hint" style={{ fontSize: 14 }}>
            {t('Ретро-сегмент (DMSP, до 2011) показывает, как страна тускнеет после распада СССР: суммарный свет проседает к началу 2000-х, малые города теряют яркость. С 2000-х разгорается Минская агломерация: доля Минска и Минского района в национальном свете устойчиво растёт. Современный сегмент (VIIRS) добавляет деталь: после 2020-го доля света индустриальных районов (Жодино, Солигорск, Борисов) отстаёт от их доли в населении, а самый быстрый рост света — Островецкий район (строительство и пуск БелАЭС). Ряд по районам надёжен с 2012 года; ретро — для страны и крупных зон, он грубее: сатурация центров, блюминг, межспутниковые скачки.')}
          </p>
        </div>
        <div className="chart-block">
          <div className="chart-title">
            <span className="chip chip-model">{t('Модель')}</span> {t('Иллюстрация будущего, 2030–2075')}
          </div>
          <p className="hint" style={{ fontSize: 14 }}>
            {t('Будущие кадры — не прогноз света и не предсказание. Это ответ на вопрос «как выглядела бы карта света, если бы светимость следовала за населением при прочих равных»: яркая часть света района масштабируется прогнозом населения (v2026.4, три сценария, два стартовых ряда) с межрайонной эластичностью, оценённой по данным; инфраструктурная подсветка (дороги, рассеянный свет) остаётся на месте. Санкции, энергетика, технологии освещения не моделируются. Каждый модельный кадр несёт впечатанный маркер «МОДЕЛЬ», штриховую рамку и подпись сценария — его невозможно выдать за снимок.')}
          </p>
        </div>
      </div>

      <p className="src-note">
        {t('Наблюдения: DMSP-OLS stable lights (калибровка Li et al. 2020, версия 1992–2024) и годовые композиты EOG VIIRS VNL v2.1 (зеркало OpenGeoHub); единая шкала — калибровка-«мост» через перекрытие продуктов simVIIRS/VNL 2014–2024, стык проверен out-of-sample, главная метрика — доля района в национальном свете. Будущее (2030–2075) — модель: светимость следует за прогнозом населения проекта (v2026.4) при прочих равных; санкции, энергетика и технологии освещения не моделируются. Свет ≠ население: расхождения — маркер для разбора, а не оценка численности. Полные оговорки — в методблоке и LIMITATIONS.md пакета.')}
      </p>
    </div>
  );
}
