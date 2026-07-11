'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { DataFile } from '@/lib/types';
import { formatNumber } from '@/lib/series';
import { CAT } from '@/lib/scales';
import LineChart, { ChartSeries } from './LineChart';
import MethodDrawer from './MethodDrawer';

interface ZipfData {
  version: string;
  baselineN: number;
  sensitivityN: number[];
  years: number[];
  perYear: Record<string, {
    n: number;
    dtype: string;
    slopes: Record<string, { b: number; se: number; a: number }>;
    primacy: number;
    top: [string, number][];
  }>;
}

const M = { top: 12, right: 16, bottom: 34, left: 58 };

/** Скаттер rank-size в лог-лог осях + линия фита Габэ-Ибрагимова. */
function RankSizeScatter({ zipf, year, names, onCity }: {
  zipf: ZipfData; year: number;
  names: Record<string, string>;
  onCity: (id: string) => void;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(560);
  const [hover, setHover] = useState<{ id: string; pop: number; rank: number } | null>(null);
  const height = 380;

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => el.clientWidth > 40 && setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const d = zipf.perYear[String(year)];
  const top = d.top;
  const N = zipf.baselineN;
  const fit = d.slopes[String(N)];

  // оси: X - ранг (лог), Y - население (лог)
  const maxRank = top.length;
  const [minPop, maxPop] = [Math.min(...top.map(t => t[1])), Math.max(...top.map(t => t[1]))];
  const lx = (r: number) => Math.log10(r);
  const ly = (p: number) => Math.log10(p);
  const x0 = 0, x1 = Math.log10(maxRank);
  const y0 = Math.floor(ly(minPop) * 2) / 2 - 0.1;
  const y1 = Math.ceil(ly(maxPop) * 10) / 10 + 0.12;
  const iw = width - M.left - M.right;
  const ih = height - M.top - M.bottom;
  const X = (r: number) => M.left + ((lx(r) - x0) / (x1 - x0)) * iw;
  const Y = (p: number) => M.top + ih - ((ly(p) - y0) / (y1 - y0)) * ih;

  // линия фита: log(rank - 1/2) = a + b*log(pop)  =>  pop(r) = exp((ln(r-1/2) - a)/b)
  const fitPop = (r: number) => Math.exp((Math.log(r - 0.5) - fit.a) / fit.b);

  const xTicks = [1, 2, 3, 5, 10, 20, 30, 50].filter((r) => r <= maxRank);
  const yTicks = [5_000, 10_000, 20_000, 50_000, 100_000, 200_000, 500_000, 1_000_000, 2_000_000]
    .filter((p) => ly(p) >= y0 && ly(p) <= y1);
  const fmtPop = (p: number) =>
    p >= 1_000_000 ? `${p / 1_000_000} млн` : `${p / 1000} тыс.`;

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg width={width} height={height} role="img">
        {yTicks.map((p) => (
          <g key={p}>
            <line x1={M.left} x2={width - M.right} y1={Y(p)} y2={Y(p)} stroke="var(--grid)" />
            <text x={M.left - 6} y={Y(p) + 3} textAnchor="end" fontSize="10" fill="var(--muted)">
              {fmtPop(p)}
            </text>
          </g>
        ))}
        {xTicks.map((r) => (
          <g key={r}>
            <line x1={X(r)} x2={X(r)} y1={M.top} y2={M.top + ih} stroke="var(--grid)" />
            <text x={X(r)} y={height - 18} textAnchor="middle" fontSize="10" fill="var(--muted)">{r}</text>
          </g>
        ))}
        <text x={M.left + iw / 2} y={height - 4} textAnchor="middle" fontSize="10.5" fill="var(--ink-2)">
          ранг города (логарифмическая шкала)
        </text>

        {/* линия фита по топ-N */}
        <path
          d={Array.from({ length: 40 }, (_, i) => {
            const r = Math.pow(10, x0 + ((x1 - x0) * i) / 39);
            return `${i ? 'L' : 'M'}${X(r).toFixed(1)},${Y(fitPop(r)).toFixed(1)}`;
          }).join('')}
          fill="none" stroke="var(--muted)" strokeWidth="1.5" strokeDasharray="6 4"
        />

        {/* города */}
        {top.map(([id, pop], i) => {
          const rank = i + 1;
          const inFit = rank <= N;
          return (
            <circle
              key={id}
              cx={X(rank)} cy={Y(pop)}
              r={hover?.id === id ? 7 : inFit ? 5 : 3.5}
              fill={inFit ? CAT[0] : 'var(--baseline)'}
              stroke="var(--surface-1)" strokeWidth="1.5"
              style={{ cursor: 'pointer' }}
              onPointerEnter={() => setHover({ id, pop, rank })}
              onPointerLeave={() => setHover(null)}
              onClick={() => onCity(id)}
            />
          );
        })}
        {/* подписи якорных городов */}
        {top.slice(0, 2).map(([id, pop], i) => (
          <text key={id} x={X(i + 1) + 9} y={Y(pop) + 4} fontSize="11" fill="var(--ink-2)">
            {names[id] ?? id}
          </text>
        ))}
      </svg>
      {hover && (
        <div className="chart-tooltip" style={{ left: Math.min(X(hover.rank) + 12, width - 170), top: Y(hover.pop) - 10 }}>
          <div className="ct-row">
            <span className="ct-val">{names[hover.id] ?? hover.id}</span>
          </div>
          <div className="ct-year">ранг {hover.rank} · {formatNumber(hover.pop)} чел. · клик — на карту</div>
        </div>
      )}
    </div>
  );
}

export default function ZipfView() {
  const [zipf, setZipf] = useState<ZipfData | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [year, setYear] = useState(2019);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    fetch('/data/zipf.json').then((r) => r.json()).then(setZipf);
    fetch('/data/data.json').then((r) => r.json()).then((d: DataFile) => {
      const m: Record<string, string> = {};
      for (const t of Object.values(d.territories)) if (t.level === 'city') m[t.id] = t.ru;
      setNames(m);
    });
  }, []);

  // анимация: автопереключение срезов
  useEffect(() => {
    if (!playing || !zipf) return;
    const id = window.setInterval(() => {
      setYear((y) => {
        const i = zipf.years.indexOf(y);
        if (i >= zipf.years.length - 1) { setPlaying(false); return y; }
        return zipf.years[i + 1];
      });
    }, 1200);
    return () => window.clearInterval(id);
  }, [playing, zipf]);

  const slopeSeries: ChartSeries[] = useMemo(() => {
    if (!zipf) return [];
    return zipf.sensitivityN.map((n, i) => ({
      name: `топ-${n}${n === zipf.baselineN ? ' (базовый)' : ''}`,
      color: CAT[i],
      points: zipf.years
        .filter((y) => zipf.perYear[String(y)].slopes[String(n)])
        .map((y) => {
          const s = zipf.perYear[String(y)].slopes[String(n)];
          const alpha = -s.b;
          const isBase = n === zipf.baselineN;
          return {
            year: y, value: alpha, major: true,
            ...(isBase ? { lo: alpha - 1.96 * s.se, hi: alpha + 1.96 * s.se } : {}),
          };
        }),
    }));
  }, [zipf]);

  const primacySeries: ChartSeries[] = useMemo(() => {
    if (!zipf) return [];
    return [{
      name: 'Минск / второй город',
      color: CAT[3],
      points: zipf.years.map((y) => ({ year: y, value: zipf.perYear[String(y)].primacy, major: true })),
    }];
  }, [zipf]);

  if (!zipf) return <p className="hint">Загрузка данных…</p>;

  const d = zipf.perYear[String(year)];
  const fit = d.slopes[String(zipf.baselineN)];

  return (
    <div>
      <div className="controls" style={{ marginBottom: 6 }}>
        <div className="control-group">
          <button
            className="play-btn"
            onClick={() => {
              if (!playing && year >= zipf.years[zipf.years.length - 1]) setYear(zipf.years[0]);
              setPlaying(!playing);
            }}
            aria-label={playing ? 'пауза' : 'воспроизвести по срезам'}
          >
            {playing ? '❚❚' : '▶'}
          </button>
          <span className="control-label">Срез</span>
          <div className="seg seg-wrap">
            {zipf.years.map((y) => (
              <button key={y} className={y === year ? 'on' : ''}
                onClick={() => { setPlaying(false); setYear(y); }}>
                {y}
              </button>
            ))}
          </div>
        </div>
        <MethodDrawer slug="zipf" />
        <a className="btn" href="/artifacts/by-maps-zipf-v1.0.0.zip" download>
          ⬇ Проверяемый пакет (ZIP, 68 КБ)
        </a>
      </div>

      <div className="stat-row">
        <div className="stat-tile">
          <div className="st-label">Наклон rank-size, {year} (топ-{zipf.baselineN})</div>
          <div className="st-value">{fit.b.toFixed(2)}</div>
          <div className="st-delta">±{(1.96 * fit.se).toFixed(2)} (95% ДИ) · закон Ципфа = −1</div>
        </div>
        <div className="stat-tile">
          <div className="st-label">Примация: Минск / второй город, {year}</div>
          <div className="st-value">{d.primacy.toFixed(2)}×</div>
          <div className="st-delta">ожидание по Ципфу ≈ 2</div>
        </div>
        <div className="stat-tile">
          <div className="st-label">Городов с данными, {year}</div>
          <div className="st-value">{d.n}</div>
          <div className="st-delta">{d.dtype === 'c' ? 'перепись' : 'оценка Белстата'}</div>
        </div>
      </div>

      <div className="chart-block">
        <div className="chart-title">
          Ранг × размер, {year} (лог-лог); пунктир — фит Габэ–Ибрагимова по топ-{zipf.baselineN};
          серые точки — города за пределами топ-{zipf.baselineN}
        </div>
        <RankSizeScatter
          zipf={zipf} year={year} names={names}
          onCity={(id) => { window.location.href = `/?sel=${id}`; }}
        />
      </div>

      <div className="grid-2">
        <div className="chart-block">
          <div className="chart-title">Показатель Ципфа α = −наклон (1 — точный закон; полоса — 95% ДИ базовой оценки)</div>
          <LineChart
            series={slopeSeries}
            height={220}
            domain={[1897, 2026]}
            yMax={1.6}
            markYear={year}
            refY={{ value: 1, label: 'закон Ципфа' }}
            yFormat={(v) => v.toFixed(1)}
            yTooltip={(v) => v.toFixed(3)}
          />
        </div>
        <div className="chart-block">
          <div className="chart-title">Примация: во сколько раз Минск больше второго города</div>
          <LineChart
            series={primacySeries}
            height={220}
            domain={[1897, 2026]}
            yMax={4.6}
            markYear={year}
            refY={{ value: 2, label: 'ожидание Ципфа' }}
            yFormat={(v) => v.toFixed(0)}
            yTooltip={(v) => v.toFixed(2) + '×'}
          />
        </div>
      </div>

      <p className="src-note">
        До 1959 года источник покрывает не все городские НП (1897 — 43 города):
        наклон описывает верхушку иерархии. Точки — переписи; срез 2026 —
        текущая оценка. Полные ограничения — в методблоке и LIMITATIONS.md
        пакета.
      </p>
    </div>
  );
}
