'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import LineChart from '@/components/LineChart';
import { useLang, useT } from '@/lib/i18n';
import { fmtNum, ratePct, Story, StoryCity, CityYearPoint } from '@/components/urban/types';

interface Props {
  story: Story;
  selected: string | null;
  onSelect: (id: string) => void;
}

/** Цвета зон: ядро — медь (--accent-2), край — синий (--accent).
 *  Те же цвета переиспользуются в графике интенсивности для согласованности. */
const CORE_COLOR = 'var(--accent-2)';
const EDGE_COLOR = 'var(--accent)';

/** Регуляризаторы CEUR (как в расчёте ETL): +1 к свету, +10000 м² к фонду. */
const EPS_LIGHT = 1;
const EPS_FUND_M2 = 10000;

/** Минимальный размер зоны для оценки CEUR (согласован с etl/urban.py). */
const MIN_ZONE_KM2 = 0.05; // 5 га

/** Русские подписи ролей кейсов (единые для всех компонентов INF-12). */
const CASE_ROLE_RU: Record<string, string> = {
  satellite: 'Спутник Минска',
  monotown: 'Моногород',
  small_center: 'Малый райцентр',
  northeast: 'Северо-восток',
  cluster: 'Кластер',
  counterexample: 'Контрпример',
};

/* ------------------------------------------------------------------ */
/* Хуки инфраструктуры (ширина контейнера, prefers-reduced-motion)     */
/* ------------------------------------------------------------------ */

function useContainerWidth(initial = 388): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(initial);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const x = el.clientWidth;
      if (x > 40) setW(x);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const m = window.matchMedia('(prefers-reduced-motion: reduce)');
    const on = () => setReduced(m.matches);
    on();
    m.addEventListener('change', on);
    return () => m.removeEventListener('change', on);
  }, []);
  return reduced;
}

/* ------------------------------------------------------------------ */
/* Числовые помощники                                                  */
/* ------------------------------------------------------------------ */

function niceTicks(max: number, n = 4): number[] {
  if (max <= 0) return [0];
  const raw = max / n;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => max / s <= n) ?? 10 * mag;
  const ticks: number[] = [];
  for (let v = 0; v <= max * 1.0001; v += step) ticks.push(v);
  return ticks;
}

/** Линейная интерполяция builtCore/builtEdge (км²) на произвольный год.
 *  До первой эпохи — уровень первой; после последней (2020) — заморозка
 *  уровня 2020 (спутниковый ряд по построению накопительный). */
function interpBuilt(series: CityYearPoint[], key: 'builtCore' | 'builtEdge', year: number): number | null {
  const pts = series
    .filter((p) => p[key] != null)
    .map((p) => ({ year: p.year, v: p[key] as number }));
  if (!pts.length) return null;
  if (year <= pts[0].year) return pts[0].v;
  const last = pts[pts.length - 1];
  if (year >= last.year) return last.v; // заморозка после 2020
  for (let i = 1; i < pts.length; i++) {
    if (year <= pts[i].year) {
      const a = pts[i - 1];
      const b = pts[i];
      const span = b.year - a.year || 1;
      return a.v + ((year - a.year) / span) * (b.v - a.v);
    }
  }
  return last.v;
}

/** Доля края в застроенном фонде на эпоху: edge / (core + edge). */
function edgeShareAt(series: CityYearPoint[], year: number): number | null {
  const p = series.find((s) => s.year === year);
  if (!p || p.builtCore == null || p.builtEdge == null) return null;
  const tot = p.builtCore + p.builtEdge;
  return tot > 0 ? p.builtEdge / tot : null;
}

/* ------------------------------------------------------------------ */
/* Компонент stacked-area «состав фонда»                               */
/* ------------------------------------------------------------------ */

interface StackRow { year: number; core: number; edge: number }

function StackedFund({
  rows,
  width,
  reduced,
  markYears,
  ariaLabel,
}: {
  rows: StackRow[];
  width: number;
  reduced: boolean;
  markYears: number[];
  ariaLabel: string;
}) {
  const M = { top: 12, right: 14, bottom: 22, left: 46 };
  const height = 210;

  if (rows.length < 2) {
    return <p className="hint">{'—'}</p>;
  }

  const x0 = rows[0].year;
  const x1 = rows[rows.length - 1].year;
  const maxV = Math.max(...rows.map((r) => r.core + r.edge)) * 1.08;
  const iw = width - M.left - M.right;
  const ih = height - M.top - M.bottom;
  const X = (y: number) => M.left + ((y - x0) / (x1 - x0 || 1)) * iw;
  const Y = (v: number) => M.top + ih - (v / (maxV || 1)) * ih;

  const yTicks = niceTicks(maxV);
  const xTicks = rows.map((r) => r.year).filter((y) => y % 10 === 0 || y === x0 || y === x1);

  // нижняя область — ядро (0..core); верхняя — край (core..core+edge)
  const coreTop = rows.map((r, i) => `${i ? 'L' : 'M'}${X(r.year).toFixed(1)},${Y(r.core).toFixed(1)}`).join('');
  const coreArea = `${coreTop}L${X(x1).toFixed(1)},${Y(0).toFixed(1)}L${X(x0).toFixed(1)},${Y(0).toFixed(1)}Z`;

  const edgeTop = rows.map((r, i) => `${i ? 'L' : 'M'}${X(r.year).toFixed(1)},${Y(r.core + r.edge).toFixed(1)}`).join('');
  const edgeBottomRev = rows
    .slice()
    .reverse()
    .map((r) => `L${X(r.year).toFixed(1)},${Y(r.core).toFixed(1)}`)
    .join('');
  const edgeArea = `${edgeTop}${edgeBottomRev}Z`;

  const transition = reduced ? undefined : 'opacity 160ms ease';

  return (
    <svg width={width} height={height} role="img" aria-label={ariaLabel} style={{ display: 'block' }}>
      {/* сетка + подписи оси Y (км²) */}
      {yTicks.map((tk) => (
        <g key={tk}>
          <line x1={M.left} x2={width - M.right} y1={Y(tk)} y2={Y(tk)} stroke="var(--grid)" strokeWidth="1" />
          <text
            x={M.left - 6}
            y={Y(tk) + 3.5}
            textAnchor="end"
            fontSize="10"
            fill="var(--muted)"
            style={{ fontVariantNumeric: 'tabular-nums' }}
          >
            {fmtNum(tk, 1)}
          </text>
        </g>
      ))}
      {xTicks.map((tk) => (
        <text key={tk} x={X(tk)} y={height - 6} textAnchor="middle" fontSize="10" fill="var(--muted)">
          {tk}
        </text>
      ))}
      <line x1={M.left} x2={width - M.right} y1={Y(0)} y2={Y(0)} stroke="var(--baseline)" strokeWidth="1" />

      {/* заливки зон */}
      <path d={coreArea} fill={CORE_COLOR} opacity="0.55" stroke="none" style={{ transition }} />
      <path d={edgeArea} fill={EDGE_COLOR} opacity="0.42" stroke="none" style={{ transition }} />
      {/* контурные линии */}
      <path d={coreTop} fill="none" stroke={CORE_COLOR} strokeWidth="2" strokeLinejoin="round" />
      <path d={edgeTop} fill="none" stroke={EDGE_COLOR} strokeWidth="2" strokeLinejoin="round" />

      {/* отметки опорных лет для подписи долей (1990, 2020) */}
      {markYears
        .filter((y) => y >= x0 && y <= x1)
        .map((y) => (
          <line
            key={y}
            x1={X(y)}
            x2={X(y)}
            y1={M.top}
            y2={M.top + ih}
            stroke="var(--muted)"
            strokeWidth="1"
            strokeDasharray="2 3"
          />
        ))}
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* Основной компонент                                                  */
/* ------------------------------------------------------------------ */

export default function CoreEdgePanel({ story, selected, onSelect }: Props) {
  const t = useT();
  const lang = useLang();
  const reduced = useReducedMotion();
  const [stackRef, stackW] = useContainerWidth();

  const name = (id: string) =>
    lang === 'be' ? story.cities[id]?.be || story.cities[id]?.ru : story.cities[id]?.ru;

  // выбранный город: prop → фолбэк на первый кейс → первый город
  const fallbackId = story.cases[0]?.city_id ?? Object.keys(story.cities)[0];
  const cityId = selected && story.cities[selected] ? selected : fallbackId;
  const city: StoryCity | undefined = story.cities[cityId];

  // отсортированный список всех городов для select
  const options = useMemo(
    () =>
      Object.values(story.cities)
        .map((c) => ({ id: c.id, label: lang === 'be' ? c.be || c.ru : c.ru }))
        .sort((a, b) => a.label.localeCompare(b.label, 'ru')),
    [story.cities, lang],
  );

  // ---- производные для выбранного города (хуки до любых return) ----
  const stackRows: StackRow[] = useMemo(() => {
    if (!city) return [];
    return city.series
      .filter((p) => p.builtCore != null && p.builtEdge != null)
      .map((p) => ({ year: p.year, core: p.builtCore as number, edge: p.builtEdge as number }));
  }, [city]);

  const uSeries = useMemo(() => {
    if (!city) return { core: [] as { year: number; value: number }[], edge: [] as { year: number; value: number }[] };
    const core: { year: number; value: number }[] = [];
    const edge: { year: number; value: number }[] = [];
    for (const v of city.vnl) {
      const bC = interpBuilt(city.series, 'builtCore', v.year); // км²
      const bE = interpBuilt(city.series, 'builtEdge', v.year);
      // U = свет / (built_km² · 1e6 м²) · 1e6  =  свет / built_km²  (усл. ед./м² ×1e6)
      if (bC != null && bC > 0) core.push({ year: v.year, value: v.core / bC });
      if (bE != null && bE > 0) edge.push({ year: v.year, value: v.edge / bE });
    }
    return { core, edge };
  }, [city]);

  // CEUR: отношение интенсивности ядро/край, ранний (2012–14) → поздний (2022–24)
  const ceur = useMemo(() => {
    if (!city) return { early: null as number | null, late: null as number | null };
    const vnlByYear = new Map(city.vnl.map((v) => [v.year, v]));
    const mean = (ys: number[], fn: (y: number) => number | null): number | null => {
      const vs = ys.map(fn).filter((x): x is number => x != null && Number.isFinite(x));
      return vs.length ? vs.reduce((a, b) => a + b, 0) / vs.length : null;
    };
    const ceurFor = (years: number[]): number | null => {
      const cL = mean(years, (y) => vnlByYear.get(y)?.core ?? null);
      const eL = mean(years, (y) => vnlByYear.get(y)?.edge ?? null);
      const cB = mean(years, (y) => interpBuilt(city.series, 'builtCore', y)); // км²
      const eB = mean(years, (y) => interpBuilt(city.series, 'builtEdge', y));
      if (cL == null || eL == null || cB == null || eB == null) return null;
      // гейт минимального размера зон - как в конвейере (иначе CEUR = шум)
      if (cB < MIN_ZONE_KM2 || eB < MIN_ZONE_KM2) return null;
      const iCore = (cL + EPS_LIGHT) / (cB * 1e6 + EPS_FUND_M2);
      const iEdge = (eL + EPS_LIGHT) / (eB * 1e6 + EPS_FUND_M2);
      return iEdge > 0 ? iCore / iEdge : null;
    };
    return { early: ceurFor([2012, 2013, 2014]), late: ceurFor([2022, 2023, 2024]) };
  }, [city]);

  if (!city) return <p className="hint">{t('Нет данных по выбранному городу.')}</p>;

  const main = city.main;
  const ihs = city.lightMetrics.ihs;
  const es90 = edgeShareAt(city.series, 1990);
  const es20 = edgeShareAt(city.series, 2020);

  const signed = (v: number, digits = 2) => (v > 0 ? '+' : '') + fmtNum(v, digits);

  // ---- критерии ярлыка «опустошение изнутри» ----
  type St = 'yes' | 'no' | 'na';
  const SYM: Record<St, string> = { yes: '✓', no: '✗', na: '—' };
  const WORD: Record<St, string> = { yes: t('да'), no: t('нет'), na: t('н/д') };

  const criteria: { label: string; state: St; note: string }[] = [
    {
      label: t('население сокращается'),
      state: main ? (main.pgr < -0.001 ? 'yes' : 'no') : 'na',
      note: main
        ? `${fmtNum(main.pgr * 100, 2)} ${t('%/год')} (${ratePct(main.pgr, 30)} ${t('за 30 лет')})`
        : t('нет данных'),
    },
    {
      label: t('IHS положителен и выше порога шума (> 0,1)'),
      state: ihs == null ? 'na' : ihs > 0.1 ? 'yes' : 'no',
      note: ihs == null ? t('оценка недоступна') : `IHS = ${signed(ihs)}`,
    },
    {
      label: t('доля края в фонде растёт (1990 → 2020)'),
      state: es90 != null && es20 != null ? (es20 > es90 ? 'yes' : 'no') : 'na',
      note:
        es90 != null && es20 != null
          ? `${fmtNum(es90 * 100, 1)}% → ${fmtNum(es20 * 100, 1)}%`
          : t('нет данных'),
    },
    {
      label: t('устойчивость к исключению промышленности'),
      state: 'na',
      note: t('не проверяемо в MVP (нет разметки RES/NRES)'),
    },
    {
      label: t('визуальная проверка кадров'),
      state: 'na',
      note: t('вручную, материалы в пакете'),
    },
  ];
  const labelAssigned = criteria.every((c) => c.state === 'yes');

  // серии для LineChart «свет на единицу фонда»
  const lightSeries = [
    uSeries.core.length ? { name: t('ядро'), color: CORE_COLOR, points: uSeries.core } : null,
    uSeries.edge.length ? { name: t('край'), color: EDGE_COLOR, points: uSeries.edge } : null,
  ].filter((s): s is { name: string; color: string; points: { year: number; value: number }[] } => s != null);

  const cases = story.cases.filter((c) => story.cities[c.city_id]);

  return (
    <div className="chart-block">
      {/* -------- выбор города -------- */}
      <div className="urban-controls">
        <div className="seg urban-seg" role="group" aria-label={t('Города-кейсы')}>
          {cases.map((c) => (
            <button
              key={c.city_id}
              type="button"
              className={c.city_id === cityId ? 'on' : ''}
              aria-pressed={c.city_id === cityId}
              onClick={() => onSelect(c.city_id)}
            >
              {name(c.city_id)}
              <span className="hint" style={{ marginLeft: 5 }}>
                {t(CASE_ROLE_RU[c.role] ?? c.role)}
              </span>
            </button>
          ))}
        </div>
        <label>
          <span className="hint" style={{ marginRight: 6 }}>
            {t('Город')}
          </span>
          <select value={cityId} onChange={(e) => onSelect(e.target.value)}>
            {options.map((o) => (
              <option key={o.id} value={o.id}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* -------- 1. состав фонда: stacked-area -------- */}
      <h3>{t('Из чего сложен застроенный фонд')}</h3>
      <p className="hint">
        <span className="chip-tag chip-data">{t('данные')}</span>{' '}
        {t('Накопленная застройка GHS-BUILT-S, км². Ядро — контур 1975 года; край — всё, что вошло в фонд позже. Наблюдение раз в 5 лет.')}
      </p>
      <div className="chart-svg-wrap" ref={stackRef}>
        <StackedFund
          rows={stackRows}
          width={stackW}
          reduced={reduced}
          markYears={[1990, 2020]}
          ariaLabel={t('Состав застроенного фонда по эпохам: ядро и край, км²')}
        />
      </div>
      <div className="urban-legend">
        <span className="lg">
          <span className="sw" style={{ background: CORE_COLOR }} /> {t('ядро — контур 1975')}
        </span>
        <span className="lg">
          <span className="sw" style={{ background: EDGE_COLOR }} /> {t('край — вошло в фонд после 1975')}
        </span>
      </div>
      <p className="hint">
        {t('Доля края в фонде')}: {es90 != null ? `${fmtNum(es90 * 100, 1)}%` : '—'}{' '}
        {t('(1990)')} → {es20 != null ? `${fmtNum(es20 * 100, 1)}%` : '—'} {t('(2020)')}.
      </p>

      {/* -------- 2. свет на единицу фонда -------- */}
      <h3>{t('Свет на единицу фонда')}</h3>
      <p className="hint">
        <span className="chip-tag chip-calc">{t('расчёт')}</span>{' '}
        {t('Ночная светимость VIIRS на единицу застройки, ×10⁶ усл. ед./м². Фонд по годам интерполирован линейно между эпохами (2010/2015/2020).')}{' '}
        <span className="urban-badge model">{t('фонд после 2020 заморожен на уровне 2020')}</span>
      </p>
      {lightSeries.length ? (
        <LineChart
          series={lightSeries}
          height={200}
          domain={[2012, 2024]}
          yFormat={(v) => fmtNum(v, 0)}
          yTooltip={(v) => `${fmtNum(v, 0)} ${t('усл. ед.')}`}
        />
      ) : (
        <p className="hint">{t('Недостаточно данных для оценки интенсивности.')}</p>
      )}

      {/* -------- 3. плашки CEUR / IHS -------- */}
      <div className="stat-row" role="list" style={{ marginTop: 12 }}>
        <div className="stat-tile" role="listitem">
          <div className="st-label">{t('CEUR: интенсивность ядро/край, ранний → поздний')}</div>
          <div className="st-value">
            {ceur.early != null ? fmtNum(ceur.early, 2) : '—'}
            {' → '}
            {ceur.late != null ? fmtNum(ceur.late, 2) : '—'}
          </div>
          <div className="st-delta hint">{t('ранний 2012–2014 · поздний 2022–2024')}</div>
        </div>
        <div className="stat-tile" role="listitem">
          <div className="st-label">{t('IHS: сдвиг интенсивности')}</div>
          <div className="st-value">{ihs == null ? t('зоны слишком малы для оценки') : signed(ihs)}</div>
          <div className="st-delta hint">{t('IHS > 0 — сдвиг интенсивности от ядра к краю')}</div>
        </div>
      </div>

      {/* -------- 4. критерии ярлыка -------- */}
      <h3>{t('Критерии ярлыка «опустошение изнутри»')}</h3>
      <ul className="limit-list" aria-label={t('Критерии ярлыка «опустошение изнутри»')}>
        {criteria.map((c) => (
          <li key={c.label}>
            <span
              aria-hidden="true"
              style={{ fontVariantNumeric: 'tabular-nums', marginRight: 6, fontWeight: 700 }}
            >
              {SYM[c.state]}
            </span>
            <span className="sr-only">{WORD[c.state]}: </span>
            {c.label} — <span className="hint">{c.note}</span>
          </li>
        ))}
      </ul>
      <p className="hint">
        {labelAssigned
          ? t('ярлык «опустошение изнутри» присваивается')
          : t('ярлык не присваивается — смотрите компоненты')}
      </p>

      {/* -------- фолбэк-таблицы -------- */}
      <details className="urban-fallback">
        <summary>{t('Таблицы: состав фонда и свет по зонам')}</summary>
        <div className="zone-table-wrap">
          <table className="zone-table">
            <caption className="hint" style={{ textAlign: 'left', padding: '4px 0' }}>
              {t('Застроенный фонд по эпохам, км²')}
            </caption>
            <thead>
              <tr>
                <th>{t('Эпоха')}</th>
                <th>{t('Ядро, км²')}</th>
                <th>{t('Край, км²')}</th>
                <th>{t('Доля края, %')}</th>
              </tr>
            </thead>
            <tbody>
              {city.series.map((p) => {
                const share =
                  p.builtCore != null && p.builtEdge != null && p.builtCore + p.builtEdge > 0
                    ? (p.builtEdge / (p.builtCore + p.builtEdge)) * 100
                    : null;
                return (
                  <tr key={p.year}>
                    <td>{p.year}</td>
                    <td>{fmtNum(p.builtCore, 3)}</td>
                    <td>{fmtNum(p.builtEdge, 3)}</td>
                    <td>{share != null ? fmtNum(share, 1) : '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="zone-table-wrap" style={{ marginTop: 10 }}>
          <table className="zone-table">
            <caption className="hint" style={{ textAlign: 'left', padding: '4px 0' }}>
              {t('Свет и интенсивность по годам')}
            </caption>
            <thead>
              <tr>
                <th>{t('Год')}</th>
                <th>{t('Свет ядра')}</th>
                <th>{t('Свет края')}</th>
                <th>{t('U ядра')}</th>
                <th>{t('U края')}</th>
              </tr>
            </thead>
            <tbody>
              {city.vnl.map((v) => {
                const bC = interpBuilt(city.series, 'builtCore', v.year);
                const bE = interpBuilt(city.series, 'builtEdge', v.year);
                const uC = bC != null && bC > 0 ? v.core / bC : null;
                const uE = bE != null && bE > 0 ? v.edge / bE : null;
                return (
                  <tr key={v.year}>
                    <td>{v.year}</td>
                    <td>{fmtNum(v.core, 1)}</td>
                    <td>{fmtNum(v.edge, 1)}</td>
                    <td>{uC != null ? fmtNum(uC, 0) : '—'}</td>
                    <td>{uE != null ? fmtNum(uE, 0) : '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </details>

      <p className="hint">
        {t('Свет — прокси интенсивности использования, не численности; вклад энергоэффективности и промышленных источников не устранён.')}
      </p>
    </div>
  );
}
