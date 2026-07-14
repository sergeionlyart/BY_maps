'use client';

/**
 * Событийный таймлайн: линия национальной интенсивности, маркеры событий
 * (размер = сила, цвет/форма = направление и тип), полосы происхождения
 * данных (реконструкция / наблюдения / прогноз), маркеры качества и
 * методологических переходов, визуальный разрыв наблюдения→прогноз.
 */

import { useMemo, useRef, useState } from 'react';
import { useT } from '@/lib/i18n';
import type { Analytic, EventsFile, NlEvent } from '@/lib/nightlightsV3';

export interface TimelineProps {
  night: Analytic;
  events: EventsFile;
  stops: number[];
  idx: number;
  scn: string;
  jmp: string;
  onChange: (i: number) => void;
  onEvent: (e: NlEvent) => void;
  playing: boolean;
  setPlaying: (p: boolean) => void;
}

const GAP_PX = 26;   // визуальный разрыв наблюдения → прогноз

export default function Timeline(p: TimelineProps) {
  const t = useT();
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(860);
  if (typeof window !== 'undefined' && wrapRef.current
      && wrapRef.current.clientWidth > 40
      && Math.abs(wrapRef.current.clientWidth - width) > 2) {
    setWidth(wrapRef.current.clientWidth);
  }
  const height = 118;
  const M = { top: 8, bottom: 34, left: 8, right: 8 };
  const obsSpan = 2024 - 1992;
  const modSpan = 2075 - 2030;
  const innerW = width - M.left - M.right - GAP_PX;
  const pxPerYearObs = (innerW * 0.72) / obsSpan;
  const pxPerYearMod = (innerW * 0.28) / modSpan;

  const X = useMemo(() => (y: number) => {
    if (y <= 2024) return M.left + (y - 1992) * pxPerYearObs;
    return M.left + obsSpan * pxPerYearObs + GAP_PX + (y - 2030) * pxPerYearMod;
  }, [M.left, pxPerYearObs, pxPerYearMod, obsSpan]);

  const ih = height - M.top - M.bottom;

  const natPts = useMemo(() => {
    const pts: { y: number; v: number }[] = [];
    for (const [k, v] of Object.entries(p.night.natLight)) pts.push({ y: +k, v });
    const mod = p.night.natModel[p.jmp]?.[p.scn] ?? {};
    for (const [k, v] of Object.entries(mod)) pts.push({ y: +k, v });
    pts.sort((a, b) => a.y - b.y);
    const vmax = Math.max(...pts.map((q) => q.v)) * 1.06;
    return { pts, vmax };
  }, [p.night, p.scn, p.jmp]);

  const Yv = (v: number) => M.top + ih - (v / natPts.vmax) * ih;

  const evByYear = useMemo(() => {
    const m: Record<number, NlEvent[]> = {};
    for (const e of p.events.events) (m[e.year] ??= []).push(e);
    return m;
  }, [p.events]);

  const obsLine = natPts.pts.filter((q) => q.y <= 2024)
    .map((q) => `${X(q.y).toFixed(1)},${Yv(q.v).toFixed(1)}`).join(' ');
  const modLine = natPts.pts.filter((q) => q.y >= 2030)
    .map((q) => `${X(q.y).toFixed(1)},${Yv(q.v).toFixed(1)}`).join(' ');

  const curYear = p.stops[p.idx];

  return (
    <div className="nlv3-timeline" ref={wrapRef}>
      <div className="nlv3-tl-controls">
        <button className="play-btn" onClick={() => {
          if (!p.playing && p.idx >= p.stops.length - 1) p.onChange(0);
          p.setPlaying(!p.playing);
        }} aria-label={p.playing ? t('пауза') : t('воспроизвести')}>
          {p.playing ? '❚❚' : '▶'}
        </button>
        <div className="year-display">
          {curYear}
          {curYear > 2024 && <span className="forecast-flag">{t('модель')}</span>}
        </div>
      </div>
      <svg width={width} height={height} className="nlv3-tl-svg" role="img"
        aria-label={t('таймлайн событий ночной светимости')}>
        {/* полосы происхождения данных */}
        <rect x={X(1992)} y={height - 22} width={X(2011.9) - X(1992)} height={7} rx={2}
          fill="color-mix(in srgb, var(--muted) 40%, transparent)" />
        <rect x={X(2012)} y={height - 22} width={X(2024) - X(2012)} height={7} rx={2}
          fill="color-mix(in srgb, var(--accent) 55%, transparent)" />
        <rect x={X(2030)} y={height - 22} width={X(2075) - X(2030)} height={7} rx={2}
          fill="none" stroke="var(--accent-2)" strokeDasharray="4 3" />
        <text x={X(2002)} y={height - 2} fontSize="9" fill="var(--muted)" textAnchor="middle">
          {t('реконструкция')}
        </text>
        <text x={X(2018)} y={height - 2} fontSize="9" fill="var(--muted)" textAnchor="middle">
          {t('наблюдения')}
        </text>
        <text x={X(2052)} y={height - 2} fontSize="9" fill="var(--accent-2)" textAnchor="middle">
          {t('прогноз')}
        </text>
        {/* визуальный разрыв наблюдения -> прогноз */}
        <g transform={`translate(${X(2024) + GAP_PX / 2 + 2}, 0)`}>
          <line x1={0} x2={0} y1={M.top} y2={height - 12}
            stroke="var(--accent-2)" strokeDasharray="3 4" opacity={0.8} />
          <text x={0} y={M.top + 8} fontSize="10" fill="var(--accent-2)" textAnchor="middle">⇢</text>
        </g>
        {/* линия национальной интенсивности (аналитический слой) */}
        <polyline points={obsLine} fill="none" stroke="var(--ink-2)" strokeWidth="1.6" opacity={0.9} />
        <polyline points={modLine} fill="none" stroke="var(--accent-2)" strokeWidth="1.4"
          strokeDasharray="4 3" opacity={0.9} />
        {/* маркеры событий */}
        {Object.entries(evByYear).map(([ys, evs]) => {
          const y = +ys;
          const main = evs.find((e) => e.kind === 'regional_change')
            ?? evs.find((e) => e.kind === 'national_change') ?? evs[0];
          const x = X(y);
          const isMethod = main.kind === 'source_transition'
            || main.kind === 'forecast_boundary' || main.kind === 'quality_note';
          if (isMethod) {
            return (
              <g key={ys} transform={`translate(${x}, ${M.top + 6})`}
                className="nlv3-ev" onClick={() => p.onEvent(main)}>
                <rect x={-5.5} y={-5.5} width={11} height={11}
                  transform="rotate(45)" fill="var(--surface-1)"
                  stroke="var(--muted)" strokeWidth="1.4" />
                <title>{`${y}: ${t('методологический переход / качество данных')}`}</title>
              </g>
            );
          }
          const score = main.score ?? 1;
          const r = Math.max(4, Math.min(9, 3 + score * 0.55));
          const dir = main.kind === 'national_change'
            ? main.direction : main.regions[0]?.direction;
          const col = dir === 'rise' ? 'var(--pos)' : 'var(--neg)';
          const yy = Yv(natPts.pts.find((q) => q.y === y)?.v ?? 0);
          return (
            <g key={ys} className="nlv3-ev" onClick={() => p.onEvent(main)}>
              <circle cx={x} cy={yy} r={r} fill={col} opacity={0.85}
                stroke="var(--surface-1)" strokeWidth="1.2" />
              <text x={x} y={yy + 3} textAnchor="middle" fontSize="9"
                fontWeight={700} fill="#fff" pointerEvents="none">
                {dir === 'rise' ? '+' : '−'}
              </text>
              <title>{`${y}: ${main.kind === 'national_change'
                ? t('общенациональное изменение')
                : t('региональное событие')} (${t('сила')} ${score})`}</title>
            </g>
          );
        })}
        {/* курсор */}
        <line x1={X(curYear)} x2={X(curYear)} y1={M.top - 2} y2={height - 14}
          stroke="var(--ink)" strokeWidth="1.5" opacity={0.85} />
        {[1992, 2000, 2012, 2024, 2050, 2075].map((y) => (
          <text key={y} x={X(y)} y={height - 12} fontSize="9.5" fill="var(--muted)"
            textAnchor="middle" className="nlv3-tick" onClick={() => {
              const i = p.stops.indexOf(y);
              if (i >= 0) p.onChange(i);
            }}>{y}</text>
        ))}
      </svg>
      <input type="range" min={0} max={p.stops.length - 1} step={1} value={p.idx}
        onChange={(e) => p.onChange(+e.target.value)} aria-label={t('год')}
        className="nlv3-range" />
    </div>
  );
}
