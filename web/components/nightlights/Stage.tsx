'use client';

/**
 * Сцена карты света: два независимых слоя (абсолютная яркость + delta),
 * SVG-оверлей районов (hit-test, событийный акцент реальным контуром,
 * затемнение остального, мягкий зум ≤7%), бейдж происхождения данных,
 * маркировка МОДЕЛЬ, A/B-шторка режима «Анализ».
 *
 * prefers-reduced-motion: без зума, импульса и кроссфейда.
 */

import { useCallback, useMemo, useRef, useState } from 'react';
import { useT } from '@/lib/i18n';
import type { GeoFeature, Manifest, NlEvent } from '@/lib/nightlightsV3';

export type Layer = 'abs' | 'delta' | 'both';

export interface StageProps {
  manifest: Manifest;
  absSrc: string;
  deltaSrc: string | null;
  layer: Layer;
  sourceBadge: string;
  modelBadge: string | null;   // «МОДЕЛЬ · сценарий · старт» либо null
  geo: GeoFeature[] | null;
  names: Record<string, string>;
  sel: string | null;
  onSelect: (id: string) => void;
  showBorders: boolean;
  event: NlEvent | null;       // активный акцент (контур+затемнение+зум)
  reducedMotion: boolean;
  abSrc?: string | null;       // A/B: левая сторона
  abLabel?: string;
  curLabel?: string;
  dirGlyphs?: boolean;         // знаки +/− у акцентированных районов
}

function useWidth(init: number): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(init);
  if (typeof window !== 'undefined' && ref.current && ref.current.clientWidth > 40
      && Math.abs(ref.current.clientWidth - width) > 2) {
    setWidth(ref.current.clientWidth);
  }
  return [ref, width];
}

export default function Stage(p: StageProps) {
  const t = useT();
  const [wrapRef, width] = useWidth(720);
  const [split, setSplit] = useState(0.5);
  const dragging = useRef(false);
  const [hover, setHover] = useState<string | null>(null);

  const [W, S, E, N] = p.manifest.grid.bounds;
  const kx = Math.cos(((S + N) / 2) * Math.PI / 180);
  const aspect = ((E - W) * kx) / (N - S);
  const height = Math.round(width / aspect);
  const X = useCallback((lon: number) => ((lon - W) / (E - W)) * width, [W, E, width]);
  const Y = useCallback((lat: number) => ((N - lat) / (N - S)) * height, [N, S, height]);

  const paths = useMemo(() => {
    if (!p.geo) return [];
    return p.geo.map((f) => {
      const polys = f.geometry.type === 'Polygon'
        ? [f.geometry.coordinates as number[][][]]
        : (f.geometry.coordinates as number[][][][]);
      let d = '';
      const xs: number[] = []; const ys: number[] = [];
      for (const poly of polys) for (const ring of poly) {
        d += ring.map(([lon, lat], i) => {
          const x = X(lon); const y = Y(lat);
          xs.push(x); ys.push(y);
          return `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`;
        }).join('') + 'Z';
      }
      const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
      const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
      return { id: f.properties.id, d, cx, cy };
    });
  }, [p.geo, X, Y]);

  const byId = useMemo(() => Object.fromEntries(paths.map((q) => [q.id, q])), [paths]);
  const mainRegion = p.event?.regions?.[0] ?? null;
  const focus = mainRegion ? byId[mainRegion.id] : null;

  // мягкий зум к событию (<= 7%), отключается prefers-reduced-motion
  const zoom = focus && !p.reducedMotion
    ? { transform: `scale(1.07)`, transformOrigin: `${focus.cx}px ${focus.cy}px` }
    : undefined;

  const onDrag = useCallback((e: React.PointerEvent) => {
    if (!dragging.current || !wrapRef.current) return;
    const box = wrapRef.current.getBoundingClientRect();
    setSplit(Math.min(0.98, Math.max(0.02, (e.clientX - box.left) / box.width)));
  }, [wrapRef]);

  const showAbs = p.layer !== 'delta';
  const showDelta = p.layer !== 'abs' && p.deltaSrc != null;
  const isModel = p.modelBadge != null;

  return (
    <div ref={wrapRef} className="nlv2-stage nlv3-stage" style={{ height }}
      onPointerMove={p.abSrc ? onDrag : undefined}
      onPointerUp={() => { dragging.current = false; }}>
      <div className={p.reducedMotion ? 'nlv3-frame-wrap' : 'nlv3-frame-wrap nlv3-animated'} style={zoom}>
        {showAbs && (
          <img key={p.absSrc} src={p.absSrc} alt={t('карта ночной светимости')}
            className={p.reducedMotion ? 'nlv2-frame' : 'nlv2-frame nlv2-frame-fade'} draggable={false} />
        )}
        {!showAbs && <div className="nlv3-abs-off" />}
        {showDelta && (
          <img key={p.deltaSrc} src={p.deltaSrc!} alt={t('слой изменения светимости')}
            className={'nlv2-frame nlv3-delta' + (p.event && !p.reducedMotion ? ' nlv3-pulse' : '')}
            draggable={false} />
        )}
        {p.abSrc && (
          <div className="nlv2-ab-top" style={{ clipPath: `inset(0 ${100 - split * 100}% 0 0)` }}>
            <img src={p.abSrc} alt="" className="nlv2-frame" draggable={false} />
          </div>
        )}
      </div>

      {p.abSrc && (
        <>
          <div className="nlv2-ab-divider" style={{ left: `${split * 100}%` }}
            onPointerDown={(e) => { dragging.current = true; (e.target as HTMLElement).setPointerCapture(e.pointerId); }}>
            <span>⇔</span>
          </div>
          <div className="nlv2-ab-label" style={{ left: 8 }}>{p.abLabel}</div>
          <div className="nlv2-ab-label" style={{ right: 8 }}>{p.curLabel}</div>
        </>
      )}

      {!p.abSrc && (
        <svg className="nlv2-overlay" width={width} height={height} style={zoom}
          aria-label={t('районы')}>
          {focus && (
            <path d={`M0,0H${width}V${height}H0Z ${focus.d}`} fillRule="evenodd"
              fill="rgba(4,3,2,0.45)" pointerEvents="none" />
          )}
          {paths.map((q) => {
            const isMain = mainRegion?.id === q.id;
            const isSecondary = p.event?.regions?.slice(1).some((r) => r.id === q.id) ?? false;
            return (
              <path key={q.id} d={q.d} fill="transparent"
                stroke={q.id === p.sel ? 'var(--accent-2)'
                  : isMain ? '#ffd28a' : isSecondary ? 'rgba(255,210,138,0.6)'
                  : hover === q.id ? '#e8c896'
                  : p.showBorders ? 'rgba(180,160,130,0.25)' : 'transparent'}
                strokeWidth={isMain ? 2.5 : q.id === p.sel ? 2 : isSecondary ? 1.5 : 1}
                style={{ cursor: 'pointer' }}
                onPointerEnter={() => setHover(q.id)}
                onPointerLeave={() => setHover(null)}
                onClick={() => p.onSelect(q.id)}>
                <title>{p.names[q.id] ?? q.id}</title>
              </path>
            );
          })}
          {p.dirGlyphs && p.event?.regions?.map((r) => {
            const q = byId[r.id];
            if (!q) return null;
            return (
              <text key={r.id} x={q.cx} y={q.cy} textAnchor="middle"
                fontSize="22" fontWeight={700} pointerEvents="none"
                fill={r.direction === 'rise' ? 'var(--pos)' : 'var(--neg)'}
                stroke="rgba(0,0,0,0.7)" strokeWidth="4" paintOrder="stroke">
                {r.direction === 'rise' ? '+' : '−'}
              </text>
            );
          })}
        </svg>
      )}

      <div className={`nlv2-badge nlv3-badge-${p.modelBadge ? 'model' : 'obs'}`}>
        {p.sourceBadge}
      </div>
      {isModel && (
        <>
          <div className="nlv2-badge nlv2-badge-model nlv3-model-badge">{p.modelBadge}</div>
          <div className="nlv2-model-border" />
        </>
      )}
    </div>
  );
}
