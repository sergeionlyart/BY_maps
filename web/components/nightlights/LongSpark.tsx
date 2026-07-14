'use client';

/** Карточка района: доли в свете и населении 1992→2075 (аналитический
 *  слой; будущий сегмент — модель, штрих). */

import { useEffect, useRef, useState } from 'react';
import { useT } from '@/lib/i18n';
import type { Analytic, AnalyticRow } from '@/lib/nightlightsV3';

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

export default function LongSpark({ row, night, scn, jmp }: {
  row: AnalyticRow; night: Analytic; scn: string; jmp: string;
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
