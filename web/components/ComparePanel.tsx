'use client';

import { useState } from 'react';
import type { DataFile } from '@/lib/types';
import { seriesPoints, formatCompact, formatNumber } from '@/lib/series';
import { CAT } from '@/lib/scales';
import LineChart, { ChartSeries } from './LineChart';

interface Props {
  data: DataFile;
  compare: string[];
  onRemove: (id: string) => void;
}

export default function ComparePanel({ data, compare, onRemove }: Props) {
  const [mode, setMode] = useState<'abs' | 'index'>('abs');

  const terrs = compare.map((id) => data.territories[id]).filter(Boolean);
  if (!terrs.length) {
    return (
      <p className="hint">
        Выберите территорию на карте и нажмите «+ В сравнение» — сюда можно
        добавить до четырёх территорий любого уровня (район, город, область).
      </p>
    );
  }

  // индекс: база = первый год, доступный во всех сериях
  const firstCommon = Math.max(...terrs.map((t) => seriesPoints(t.pop)[0]?.year ?? 1897));

  const series: ChartSeries[] = terrs.map((t, i) => {
    const pts = seriesPoints(t.pop);
    const basePt = pts.find((p) => p.year >= firstCommon);
    return {
      name: t.ru,
      color: CAT[i],
      points: pts
        .filter((p) => mode === 'abs' || p.year >= firstCommon)
        .map((p) => ({
          year: p.year,
          value: mode === 'abs' ? p.value : (p.value / (basePt?.value || 1)) * 100,
          major: p.dtype === 'c',
        })),
    };
  });

  return (
    <div>
      <div className="compare-list">
        {terrs.map((t, i) => (
          <div className="compare-item" key={t.id}>
            <span className="ci-key" style={{ background: CAT[i] }} />
            {t.ru}
            <button className="ci-x" onClick={() => onRemove(t.id)} aria-label={`убрать ${t.ru}`}>×</button>
          </div>
        ))}
      </div>

      <div className="seg" role="tablist" style={{ marginBottom: 8 }}>
        <button className={mode === 'abs' ? 'on' : ''} onClick={() => setMode('abs')}>Численность</button>
        <button className={mode === 'index' ? 'on' : ''} onClick={() => setMode('index')}>
          Индекс, {firstCommon} = 100
        </button>
      </div>

      <LineChart
        series={series}
        height={230}
        yFormat={(v) => (mode === 'abs' ? formatCompact(v) : String(Math.round(v)))}
        yTooltip={(v) => (mode === 'abs' ? formatNumber(v) + ' чел.' : Math.round(v) + '')}
      />
      {mode === 'index' && (
        <p className="src-note">
          Индекс показывает относительную динамику: 100 = уровень {firstCommon} года.
        </p>
      )}
    </div>
  );
}
