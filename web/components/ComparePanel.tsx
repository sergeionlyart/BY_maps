'use client';

import { useState } from 'react';
import type { DataFile } from '@/lib/types';
import { seriesPoints, formatCompact, formatNumber } from '@/lib/series';
import { CAT } from '@/lib/scales';
import { useT } from '@/lib/i18n';
import LineChart, { ChartSeries } from './LineChart';

interface Props {
  data: DataFile;
  compare: string[];
  onRemove: (id: string) => void;
}

export default function ComparePanel({ data, compare, onRemove }: Props) {
  const t = useT();
  const [mode, setMode] = useState<'abs' | 'index'>('abs');

  const terrs = compare.map((id) => data.territories[id]).filter(Boolean);
  if (!terrs.length) {
    return (
      <p className="hint">
        {t('Выберите территорию на карте и нажмите «+ В сравнение» — сюда можно добавить до четырёх территорий любого уровня (район, город, область).')}
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
        {terrs.map((terr, i) => (
          <div className="compare-item" key={terr.id}>
            <span className="ci-key" style={{ background: CAT[i] }} />
            {terr.ru}
            <button className="ci-x" onClick={() => onRemove(terr.id)} aria-label={`${t('убрать')} ${terr.ru}`}>×</button>
          </div>
        ))}
      </div>

      <div className="seg" role="tablist" style={{ marginBottom: 8 }}>
        <button className={mode === 'abs' ? 'on' : ''} onClick={() => setMode('abs')}>{t('Численность')}</button>
        <button className={mode === 'index' ? 'on' : ''} onClick={() => setMode('index')}>
          {t('Индекс')}, {firstCommon} = 100
        </button>
      </div>

      <LineChart
        series={series}
        height={230}
        yFormat={(v) => (mode === 'abs' ? formatCompact(v) : String(Math.round(v)))}
        yTooltip={(v) => (mode === 'abs' ? formatNumber(v) + t(' чел.') : Math.round(v) + '')}
      />
      {mode === 'index' && (
        <p className="src-note">
          {t('Индекс показывает относительную динамику: 100 = уровень')} {firstCommon} {t('года.')}
        </p>
      )}
    </div>
  );
}
