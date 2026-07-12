'use client';

import { useEffect, useState } from 'react';
import type { DataFile, Territory, RaionMode } from '@/lib/types';
import type { ForecastFile, ScenarioId, JumpoffId } from '@/lib/forecast';
import { forecastAt, hasAdjusted, FORECAST_START, SCENARIO_LABEL, SCENARIO_STYLE } from '@/lib/forecast';
import { seriesPoints, valueAt, formatNumber, formatCompact, formatPct, DTYPE_LABEL } from '@/lib/series';
import { raionBreakdown, cityDensity } from '@/lib/metrics';
import { CAT } from '@/lib/scales';
import LineChart, { ChartSeries } from './LineChart';

interface Props {
  data: DataFile;
  forecast?: ForecastFile | null;
  scenario?: ScenarioId;
  jumpoff?: JumpoffId;
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

/** Районы классов 1-2 исследования INF-07 (для кросс-ссылки с карточки). */
let cherIdsPromise: Promise<Set<string>> | null = null;
function loadCherIds(): Promise<Set<string>> {
  cherIdsPromise ??= fetch('/data/chernobyl.json')
    .then((r) => r.json())
    .then((c) => new Set<string>(c.pairs.map((p: { id: string }) => p.id)))
    .catch(() => new Set<string>());
  return cherIdsPromise;
}

const FLAG_LABEL: Record<string, string> = {
  west1921: 'Польша, 1921–1939',
  oblCenter: 'областной центр',
  raionCenter: 'районный центр',
  top7: 'топ-7 городов',
  oblCity: 'город областного подчинения',
  capital: 'столица',
};

export default function TerritoryCard({ data, forecast, scenario = 'base', jumpoff = 'official', id, year, baseYear, raionMode, compare, onCompareAdd, onSelect }: Props) {
  const t: Territory | undefined = id ? data.territories[id] : data.territories['BY'];
  const [inChernobyl, setInChernobyl] = useState(false);
  const tid = t?.id;
  const tlevel = t?.level;
  useEffect(() => {
    let alive = true;
    if (tlevel === 'raion' && tid) {
      loadCherIds().then((ids) => alive && setInChernobyl(ids.has(tid)));
    } else {
      setInChernobyl(false);
    }
    return () => { alive = false; };
  }, [tid, tlevel]);
  if (!t) return <p className="hint">Выберите территорию на карте.</p>;

  const mainSeries = t.level === 'raion' && raionMode === 'noCenter' ? t.popNoCenter : t.pop;
  // исторические плитки не выходят за границу факта (прогноз - отдельной плиткой)
  const histYear = Math.min(year, FORECAST_START);
  const now = valueAt(mainSeries, histYear);
  const base = valueAt(mainSeries, baseYear);
  const change = now && base && base.value > 0 ? now.value / base.value - 1 : null;
  const abs = now && base ? now.value - base.value : null;

  const breakdown = t.level === 'raion' ? raionBreakdown(data, t, histYear) : null;

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
      color: 'var(--viz-urban)',
      points: seriesPoints(t.urban).map((p) => ({ year: p.year, value: p.value, major: p.dtype === 'c' })),
    });
  }

  // прогноз (веер q10-q90) для страны, областей и Минска
  const useAdj = jumpoff === 'adjusted' && hasAdjusted(forecast ?? null, t.id);
  const fentry = (useAdj ? forecast!.adjusted![t.id][scenario] : undefined)
    ?? forecast?.territories[t.id]?.[scenario];
  if (forecast && fentry) {
    chart.push({
      name: `Прогноз (${SCENARIO_LABEL[scenario]})`,
      color: SCENARIO_STYLE[scenario].color,
      dash: SCENARIO_STYLE[scenario].dash,
      points: fentry.years.map((y, i) => ({
        year: y,
        value: fentry.pop[i],
        major: false,
        ...(fentry.q10 && fentry.q90 ? { lo: fentry.q10[i], hi: fentry.q90[i] } : {}),
      })),
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

      {forecast && year > FORECAST_START && fentry && (
        <div className="stat-row" style={{ marginTop: 8 }}>
          <div className="stat-tile forecast-tile">
            <div className="st-label">Прогноз на {year} · «{SCENARIO_LABEL[scenario]}»</div>
            <div className="st-value">{formatCompact(forecastAt(forecast, t.id, scenario, year, 'pop', jumpoff) ?? 0)}</div>
            <div className="st-delta">
              {fentry.q10 && fentry.q90
                ? `80% интервал: ${formatCompact(forecastAt(forecast, t.id, scenario, year, 'q10', jumpoff) ?? 0)} – ${formatCompact(forecastAt(forecast, t.id, scenario, year, 'q90', jumpoff) ?? 0)}`
                : ''}
              {fentry.q05 && fentry.q95
                ? ` · 90%: ${formatCompact(forecastAt(forecast, t.id, scenario, year, 'q05', jumpoff) ?? 0)} – ${formatCompact(forecastAt(forecast, t.id, scenario, year, 'q95', jumpoff) ?? 0)}`
                : ''} · прогноз {forecast.version}{jumpoff === 'adjusted' ? (useAdj ? ' · ряд скорр.' : ' · ряд офиц.') : ''}
            </div>
          </div>
        </div>
      )}

      {forecast?.probabilistic && t.id === 'BY' && scenario === 'base' && (
        <div className="prob-panel">
          <div className="prob-head">
            Вероятностный слой · {forecast.probabilistic.stats.n} симуляций траекторий СКР/ОПЖ,
            калибр. по 80% PI WPP-2024
          </div>
          <div className="prob-rows">
            <span>Убыль населения к 2050 —{' '}
              <b>{formatPct(forecast.probabilistic.stats.pDecline2051, 0)}</b></span>
            <span>Ниже 7 млн к 2050 —{' '}
              <b>{formatPct(forecast.probabilistic.stats.pBelow7M_2051, 0)}</b></span>
            <span>Ниже 6 млн к 2075 —{' '}
              <b>{formatPct(forecast.probabilistic.stats.pBelow6M_2075, 0)}</b></span>
          </div>
          <div className="prob-note">
            Доли из {forecast.probabilistic.stats.n} реализаций при фиксированной
            миграции (внутримодельные частоты, не безусловные вероятности); ширина
            80%-полосы страны калибрована по WPP. Веер — эмпирические квантили
            того же CCMPP, а не перенос интервала WPP.
          </div>
        </div>
      )}

      <div className="stat-row" style={{ marginTop: 8 }}>
        <div className="stat-tile">
          <div className="st-label">Население, {Math.min(year, FORECAST_START)}{t.level === 'raion' && raionMode === 'noCenter' ? ', без центра' : ''}</div>
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
        {t.level === 'raion' && (
          <a className="btn" href={`/research/aging?sel=${t.id}`}>
            INF-02: старение района
          </a>
        )}
        {t.level === 'raion' && (
          <a className="btn" href={`/research/wages?sel=${t.id}`}>
            INF-03: зарплата района
          </a>
        )}
        {t.level === 'raion' && (
          <a className="btn" href={`/research/access?sel=${t.id}`}>
            INF-04: доступность района
          </a>
        )}
        {t.level === 'raion' && (
          <a className="btn" href={`/research/migration?sel=${t.id}`}>
            INF-05: миграция района
          </a>
        )}
        {t.level === 'raion' && (
          <a className="btn" href={`/research/nightlights?sel=${t.id}`}>
            INF-08: ночные огни
          </a>
        )}
        {inChernobyl && (
          <a className="btn" href={`/research/chernobyl?sel=${t.id}`}>
            INF-07: чернобыльский след
          </a>
        )}
      </div>

      <div className="chart-block">
        <div className="chart-title">
          Динамика населения, 1897–{forecast && fentry
            ? `2075 (с прогнозом${fentry.q10 ? ', полоса — 80% интервал' : ''})`
            : '2026'}
        </div>
        <LineChart
          series={chart}
          markYear={year}
          yFormat={(v) => formatCompact(v)}
          yTooltip={(v) => formatNumber(v) + ' чел.'}
          domain={[Math.min(...chart.flatMap((s) => s.points.map((p) => p.year))),
                   forecast && fentry ? 2075 : 2026]}
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
