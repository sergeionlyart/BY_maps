'use client';

import type { DataFile } from '@/lib/types';
import { formatPct, valueAt } from '@/lib/series';
import { CAT } from '@/lib/scales';
import LineChart, { ChartSeries } from './LineChart';

interface Props {
  data: DataFile;
  year: number;
}

/** Панель урбанизации и концентрации населения (по стране). */
export default function UrbanPanel({ data, year }: Props) {
  const byPop = data.territories['BY'].pop;
  // знаменатель: население страны в современных границах; для годов без
  // прямой оценки (1923, 1926, 1939) - линейная интерполяция
  const rows = data.panel
    .map((r) => ({ ...r, pop: r.pop ?? valueAt(byPop, r.year)?.value ?? null }))
    .filter((r) => r.pop);

  const mk = (key: 'urban' | 'minsk' | 'oblCenters' | 'top7', name: string, color: string): ChartSeries => ({
    name,
    color,
    points: rows
      .filter((r) => r[key] != null)
      .map((r) => ({ year: r.year, value: (r[key]! / r.pop!) * 100, major: true })),
  });

  const series: ChartSeries[] = [
    mk('urban', 'Городское население', CAT[1]),
    mk('top7', '7 крупнейших городов', CAT[2]),
    mk('oblCenters', 'Минск + обл. центры', CAT[3]),
    mk('minsk', 'Минск', CAT[0]),
  ];

  const last = rows[rows.length - 1];
  const nearest = rows.reduce((a, b) => (Math.abs(b.year - year) < Math.abs(a.year - year) ? b : a), rows[0]);

  return (
    <div>
      <div className="stat-row">
        <div className="stat-tile">
          <div className="st-label">Доля городского населения, {nearest.year}</div>
          <div className="st-value">{nearest.urban && nearest.pop ? formatPct(nearest.urban / nearest.pop) : '—'}</div>
          <div className="st-delta">
            {rows[0].urban && rows[0].pop ? `в ${rows[0].year} — ${formatPct(rows[0].urban / rows[0].pop)}` : ''}
          </div>
        </div>
        <div className="stat-tile">
          <div className="st-label">Живёт в Минске, {nearest.year}</div>
          <div className="st-value">{nearest.minsk && nearest.pop ? formatPct(nearest.minsk / nearest.pop) : '—'}</div>
          <div className="st-delta">
            {rows[0].minsk && rows[0].pop ? `в ${rows[0].year} — ${formatPct(rows[0].minsk / rows[0].pop)}` : ''}
          </div>
        </div>
        <div className="stat-tile">
          <div className="st-label">В 7 крупнейших городах, {nearest.year}</div>
          <div className="st-value">{nearest.top7 && nearest.pop ? formatPct(nearest.top7 / nearest.pop) : '—'}</div>
          <div className="st-delta">
            {rows[0].top7 && rows[0].pop ? `в ${rows[0].year} — ${formatPct(rows[0].top7 / rows[0].pop)}` : ''}
          </div>
        </div>
      </div>

      <div className="chart-block">
        <div className="chart-title">Доля в населении страны, % (по переписным годам)</div>
        <LineChart
          series={series}
          height={240}
          markYear={year}
          yFormat={(v) => v + '%'}
          yTooltip={(v) => v.toLocaleString('ru-RU', { maximumFractionDigits: 1 }) + '%'}
          yMax={85}
          domain={[1897, 2026]}
        />
      </div>

      <p className="src-note">
        Доли считаются к населению страны в современных границах; для 1923–1939
        годов знаменатель интерполирован между ретроспективными оценками (1913,
        1940). Городское население до 1959 года — сумма городских НП из таблицы
        переписей; топ-7: Минск, Гомель, Могилёв, Витебск, Гродно, Брест,
        Бобруйск (современный состав, фиксированный во времени).
      </p>
    </div>
  );
}
