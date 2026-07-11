'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

export interface ChartSeries {
  name: string;
  color: string;
  /** Точки: год -> значение; major=true - переписной год (точка);
   *  lo/hi - границы доверительной полосы (рисуется заливкой ~12%). */
  points: { year: number; value: number; major?: boolean; lo?: number; hi?: number }[];
}

interface Props {
  series: ChartSeries[];
  height?: number;
  yFormat?: (v: number) => string;
  yTooltip?: (v: number) => string;
  domain?: [number, number];
  yMax?: number;
  markYear?: number | null;
  /** Горизонтальная референс-линия (например, «ожидание Ципфа»). */
  refY?: { value: number; label: string } | null;
  /** Вертикальные аннотации событий (например, 1986 - авария на ЧАЭС). */
  refXs?: { value: number; label: string }[];
}

const M = { top: 10, right: 14, bottom: 22, left: 46 };

function niceTicks(max: number, n = 4): number[] {
  if (max <= 0) return [0];
  const raw = max / n;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => max / s <= n) ?? 10 * mag;
  const ticks: number[] = [];
  for (let v = 0; v <= max * 1.0001; v += step) ticks.push(v);
  return ticks;
}

export default function LineChart({ series, height = 190, yFormat, yTooltip, domain, yMax, markYear, refY, refXs }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [hoverYear, setHoverYear] = useState<number | null>(null);
  const [width, setWidth] = useState(388);

  const all = series.flatMap((s) => s.points);
  const [x0, x1] = domain ?? [
    Math.min(...all.map((p) => p.year)),
    Math.max(...all.map((p) => p.year)),
  ];
  const maxV = yMax ?? Math.max(...all.map((p) => p.value)) * 1.06;

  const iw = width - M.left - M.right;
  const ih = height - M.top - M.bottom;
  const X = (year: number) => M.left + ((year - x0) / (x1 - x0 || 1)) * iw;
  const Y = (v: number) => M.top + ih - (v / (maxV || 1)) * ih;

  const yTicks = useMemo(() => niceTicks(maxV), [maxV]);
  const xTicks = useMemo(() => {
    const span = x1 - x0;
    const step = span > 90 ? 30 : span > 40 ? 20 : span > 15 ? 10 : 5;
    const start = Math.ceil(x0 / step) * step;
    const t: number[] = [];
    for (let y = start; y <= x1; y += step) t.push(y);
    return t;
  }, [x0, x1]);

  // ширина контейнера через ResizeObserver (надёжно при поздней раскладке)
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const w = el.clientWidth;
      if (w > 40) setWidth(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const year = Math.round(x0 + ((px - M.left) / iw) * (x1 - x0));
    setHoverYear(Math.max(x0, Math.min(x1, year)));
  };

  const valueAtYear = (pts: ChartSeries['points'], year: number): number | null => {
    if (!pts.length || year < pts[0].year || year > pts[pts.length - 1].year) return null;
    let lo = pts[0];
    for (const p of pts) {
      if (p.year === year) return p.value;
      if (p.year < year) lo = p;
      else return lo.value + ((year - lo.year) / (p.year - lo.year)) * (p.value - lo.value);
    }
    return pts[pts.length - 1].value;
  };

  const fmt = yFormat ?? ((v: number) => v.toLocaleString('ru-RU'));
  const fmtT = yTooltip ?? fmt;

  const hover = hoverYear != null
    ? series
        .map((s) => ({ s, v: valueAtYear(s.points, hoverYear) }))
        .filter((r): r is { s: ChartSeries; v: number } => r.v != null)
    : [];

  const tooltipLeft = hoverYear != null ? X(hoverYear) : 0;

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg
        width={width}
        height={height}
        role="img"
        onPointerMove={onMove}
        onPointerLeave={() => setHoverYear(null)}
      >
        {/* сетка */}
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={M.left} x2={width - M.right} y1={Y(t)} y2={Y(t)}
              stroke="var(--grid)" strokeWidth="1" />
            <text x={M.left - 6} y={Y(t) + 3.5} textAnchor="end" fontSize="10"
              fill="var(--muted)" style={{ fontVariantNumeric: 'tabular-nums' }}>
              {fmt(t)}
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text key={t} x={X(t)} y={height - 6} textAnchor="middle" fontSize="10" fill="var(--muted)">
            {t}
          </text>
        ))}
        <line x1={M.left} x2={width - M.right} y1={Y(0)} y2={Y(0)} stroke="var(--baseline)" strokeWidth="1" />

        {/* маркер текущего года слайдера */}
        {markYear != null && markYear >= x0 && markYear <= x1 && (
          <line x1={X(markYear)} x2={X(markYear)} y1={M.top} y2={M.top + ih}
            stroke="var(--baseline)" strokeWidth="1" />
        )}

        {/* вертикальные аннотации событий */}
        {refXs?.filter((r) => r.value >= x0 && r.value <= x1).map((r, i) => (
          <g key={r.value}>
            <line x1={X(r.value)} x2={X(r.value)} y1={M.top + 10} y2={M.top + ih}
              stroke="var(--muted)" strokeWidth="1" strokeDasharray="2 3" />
            <text x={X(r.value) + 3} y={M.top + 9 + (i % 2) * 11} fontSize="9.5" fill="var(--muted)">
              {r.label}
            </text>
          </g>
        ))}

        {/* референс-линия */}
        {refY && refY.value <= maxV && (
          <g>
            <line x1={M.left} x2={width - M.right} y1={Y(refY.value)} y2={Y(refY.value)}
              stroke="var(--muted)" strokeWidth="1" strokeDasharray="5 4" />
            <text x={width - M.right} y={Y(refY.value) - 4} textAnchor="end" fontSize="10"
              fill="var(--muted)">{refY.label}</text>
          </g>
        )}

        {/* линии (+ доверительные полосы, если заданы lo/hi) */}
        {series.map((s) => {
          const d = s.points.map((p, i) => `${i ? 'L' : 'M'}${X(p.year).toFixed(1)},${Y(p.value).toFixed(1)}`).join('');
          const banded = s.points.filter((p) => p.lo != null && p.hi != null);
          const band = banded.length > 1
            ? banded.map((p, i) => `${i ? 'L' : 'M'}${X(p.year).toFixed(1)},${Y(p.hi!).toFixed(1)}`).join('')
              + banded.slice().reverse().map((p) => `L${X(p.year).toFixed(1)},${Y(p.lo!).toFixed(1)}`).join('')
              + 'Z'
            : null;
          return (
            <g key={s.name}>
              {band && <path d={band} fill={s.color} opacity="0.12" stroke="none" />}
              <path d={d} fill="none" stroke={s.color} strokeWidth="2"
                strokeLinejoin="round" strokeLinecap="round" />
              {s.points.filter((p) => p.major).map((p) => (
                <circle key={p.year} cx={X(p.year)} cy={Y(p.value)} r="3.2"
                  fill={s.color} stroke="var(--surface-1)" strokeWidth="2" />
              ))}
            </g>
          );
        })}

        {/* перекрестие */}
        {hoverYear != null && hover.length > 0 && (
          <g>
            <line x1={X(hoverYear)} x2={X(hoverYear)} y1={M.top} y2={M.top + ih}
              stroke="var(--muted)" strokeWidth="1" />
            {hover.map(({ s, v }) => (
              <circle key={s.name} cx={X(hoverYear)} cy={Y(v)} r="4"
                fill={s.color} stroke="var(--surface-1)" strokeWidth="2" />
            ))}
          </g>
        )}
      </svg>

      {hoverYear != null && hover.length > 0 && (
        <div
          className="chart-tooltip"
          style={{
            left: Math.min(Math.max(tooltipLeft + 10, 4), width - 150),
            top: 4,
          }}
        >
          <div className="ct-year">{hoverYear}</div>
          {hover.map(({ s, v }) => (
            <div className="ct-row" key={s.name}>
              <span className="ct-key" style={{ borderTopColor: s.color }} />
              <span className="ct-val">{fmtT(v)}</span>
              {series.length > 1 && <span className="ct-name">{s.name}</span>}
            </div>
          ))}
        </div>
      )}

      {series.length > 1 && (
        <div className="chart-legend">
          {series.map((s) => (
            <span className="cl-item" key={s.name}>
              <span className="cl-key" style={{ borderTopColor: s.color }} />
              {s.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
