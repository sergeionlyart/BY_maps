'use client';

import type { DataFile, Territory, RaionMode } from '@/lib/types';
import { seriesPoints, valueAt, formatNumber, formatCompact, formatPct, DTYPE_LABEL } from '@/lib/series';
import { raionBreakdown, cityDensity } from '@/lib/metrics';
import { CAT } from '@/lib/scales';
import LineChart, { ChartSeries } from './LineChart';

interface Props {
  data: DataFile;
  id: string | null;
  year: number;
  baseYear: number;
  raionMode: RaionMode;
  compare: string[];
  onCompareAdd: (id: string) => void;
  onSelect: (id: string) => void;
}

const LEVEL_LABEL: Record<string, string> = {
  country: 'страна', oblast: 'область / город респ. подчинения',
  raion: 'район', city: 'город / гп',
};

const FLAG_LABEL: Record<string, string> = {
  west1921: 'Польша, 1921–1939',
  oblCenter: 'областной центр',
  raionCenter: 'районный центр',
  top7: 'топ-7 городов',
  oblCity: 'город областного подчинения',
  capital: 'столица',
};

export default function TerritoryCard({ data, id, year, baseYear, raionMode, compare, onCompareAdd, onSelect }: Props) {
  const t: Territory | undefined = id ? data.territories[id] : data.territories['BY'];
  if (!t) return <p className="hint">Выберите территорию на карте.</p>;

  const mainSeries = t.level === 'raion' && raionMode === 'noCenter' ? t.popNoCenter : t.pop;
  const now = valueAt(mainSeries, year);
  const base = valueAt(mainSeries, baseYear);
  const change = now && base && base.value > 0 ? now.value / base.value - 1 : null;
  const abs = now && base ? now.value - base.value : null;

  const breakdown = t.level === 'raion' ? raionBreakdown(data, t, year) : null;

  const chart: ChartSeries[] = [];
  chart.push({
    name: t.level === 'raion' ? 'Весь район' : 'Население',
    color: CAT[0],
    points: seriesPoints(t.pop).map((p) => ({ year: p.year, value: p.value, major: p.dtype === 'c' })),
  });
  if (t.level === 'raion' && breakdown && breakdown.centers.length) {
    const centerSeries = breakdown.centers
      .map((c) => data.territories[c.id])
      .filter((c) => c && Object.keys(c.pop).length > 1);
    if (centerSeries.length) {
      // суммарная серия центров: по годам, где есть данные у всех
      const years = Object.keys(centerSeries[0].pop)
        .filter((y) => centerSeries.every((c) => y in c.pop));
      chart.push({
        name: breakdown.centers.length > 1 ? 'Городские центры' : `${breakdown.centers[0].ru} (центр)`,
        color: CAT[1],
        points: years
          .map((y) => ({
            year: +y,
            value: centerSeries.reduce((s, c) => s + c.pop[y][0], 0),
            major: centerSeries[0].pop[y][1] === 'c',
          }))
          .sort((a, b) => a.year - b.year),
      });
    }
  }
  if (t.level === 'raion' && t.popNoCenter && Object.keys(t.popNoCenter).length) {
    chart.push({
      name: 'Без городских центров',
      color: CAT[2],
      points: seriesPoints(t.popNoCenter).map((p) => ({ year: p.year, value: p.value, major: p.dtype === 'c' })),
    });
  }
  if ((t.level === 'oblast' || t.level === 'country') && t.urban && Object.keys(t.urban).length > 1 && t.id !== 'BY-HM') {
    chart.push({
      name: 'Городское население',
      color: CAT[1],
      points: seriesPoints(t.urban).map((p) => ({ year: p.year, value: p.value, major: p.dtype === 'c' })),
    });
  }

  const density = now && t.area ? now.value / t.area : null;
  const centerCities = (t.center ?? []).map((cid) => data.territories[cid]).filter(Boolean);

  return (
    <div>
      <h2 className="terr-title">{t.ru}</h2>
      <div className="terr-sub">
        {LEVEL_LABEL[t.level]}{t.be !== t.ru ? ` · бел. ${t.be}` : ''}
        {t.area ? ` · ${formatNumber(t.area)} км²` : ''}
      </div>

      <div>
        {t.flags.map((f) => FLAG_LABEL[f] && <span className="badge" key={f}>{FLAG_LABEL[f]}</span>)}
      </div>

      <div className="stat-row" style={{ marginTop: 8 }}>
        <div className="stat-tile">
          <div className="st-label">Население, {year}{t.level === 'raion' && raionMode === 'noCenter' ? ', без центра' : ''}</div>
          <div className="st-value">{now ? formatCompact(now.value) : '—'}</div>
          {change != null && abs != null && (
            <div className={`st-delta ${change >= 0 ? 'up' : 'down'}`}>
              {change >= 0 ? '+' : ''}{formatPct(change)} ({abs >= 0 ? '+' : '−'}{formatCompact(Math.abs(abs))}) к {baseYear}
            </div>
          )}
        </div>
        {breakdown && breakdown.centersPop != null && breakdown.centersShare != null && (
          <div className="stat-tile">
            <div className="st-label">
              {breakdown.centers.length > 1
                ? `В центрах (${breakdown.centers.map((c) => c.ru).join(', ')})`
                : `В центре (${breakdown.centers[0].ru})`}
            </div>
            <div className="st-value">{formatCompact(breakdown.centersPop)}</div>
            <div className="st-delta">{formatPct(breakdown.centersShare)} населения района</div>
          </div>
        )}
        {t.level !== 'raion' && t.level !== 'city' && density != null && (
          <div className="stat-tile">
            <div className="st-label">Плотность</div>
            <div className="st-value">{density.toLocaleString('ru-RU', { maximumFractionDigits: 1 })}</div>
            <div className="st-delta">чел./км²</div>
          </div>
        )}
        {t.level === 'city' && cityDensity(t, year) != null && (
          <div className="stat-tile">
            <div className="st-label">Плотность города</div>
            <div className="st-value">{cityDensity(t, year)!.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}</div>
            <div className="st-delta">чел./км² ({t.area} км², Wikidata)</div>
          </div>
        )}
        {t.urban && valueAt(t.urban, year) && t.id !== 'BY-HM' && now && (
          <div className="stat-tile">
            <div className="st-label">Городское население</div>
            <div className="st-value">{formatPct(valueAt(t.urban, year)!.value / now.value)}</div>
          </div>
        )}
      </div>

      {breakdown && (
        <div className="stat-row">
          <div className="stat-tile">
            <div className="st-label">Плотность: весь район</div>
            <div className="st-value">
              {breakdown.densityWhole != null ? breakdown.densityWhole.toLocaleString('ru-RU', { maximumFractionDigits: 1 }) : '—'}
            </div>
            <div className="st-delta">чел./км²</div>
          </div>
          {breakdown.densityCenters != null && (
            <div className="stat-tile">
              <div className="st-label">В городских центрах</div>
              <div className="st-value">{breakdown.densityCenters.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}</div>
              <div className="st-delta">чел./км² (площадь — Wikidata)</div>
            </div>
          )}
          {breakdown.densityNoCenter != null && (
            <div className="stat-tile">
              <div className="st-label">Без городских центров</div>
              <div className="st-value">{breakdown.densityNoCenter.toLocaleString('ru-RU', { maximumFractionDigits: 1 })}</div>
              <div className="st-delta">чел./км² — сельская часть и малые НП</div>
            </div>
          )}
        </div>
      )}

      <div className="card-actions">
        <button
          className="btn primary"
          disabled={compare.includes(t.id) || compare.length >= 4}
          onClick={() => onCompareAdd(t.id)}
        >
          {compare.includes(t.id) ? 'В сравнении' : '+ В сравнение'}
        </button>
        {t.raion && data.territories[t.raion] && (
          <button className="btn" onClick={() => onSelect(t.raion!)}>
            район: {data.territories[t.raion].ru}
          </button>
        )}
        {centerCities.map((c) => (
          <button className="btn" key={c.id} onClick={() => onSelect(c.id)}>
            центр: {c.ru}
          </button>
        ))}
      </div>

      <div className="chart-block">
        <div className="chart-title">Динамика населения, 1897–2026</div>
        <LineChart
          series={chart}
          markYear={year}
          yFormat={(v) => formatCompact(v)}
          yTooltip={(v) => formatNumber(v) + ' чел.'}
          domain={[Math.min(...chart.flatMap((s) => s.points.map((p) => p.year))), 2026]}
        />
      </div>

      <p className="src-note">
        Точки — переписи; линии между ними — официальные оценки или линейная
        интерполяция. {t.note ? `Примечание: ${t.note}. ` : ''}
        Типы данных: {Object.values(DTYPE_LABEL).join(', ')}. См. «Методика».
      </p>
    </div>
  );
}
