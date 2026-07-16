'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useLang, useT } from '@/lib/i18n';
import {
  fmtNum,
  Story,
  StoryCity,
  TYPE_LABELS,
  TYPE_COLORS,
  REGION_LABELS,
} from '@/components/urban/types';

/** INF-12 «Карта типов и уверенности».
 *  Точки городов на самодельном контуре Беларуси (adm1.geojson) в общей
 *  равнопромежуточной проекции x∝lon·cos(53.7°), y∝−lat. Два режима:
 *  «Тип траектории» (цвет+форма) и «Качество данных» (форма A/B/C).
 *  Карта — не единственный путь к выводу: полная таблица-фолбэк ниже. */

type LonLat = [number, number];
type Ring = LonLat[];
type Mode = 'type' | 'quality';

/* --- проекция: фиксированная геогр. рамка Беларуси, чтобы контур и точки
 *     жили в одной системе координат независимо от загрузки geojson. --- */
const LON_MIN = 23.15, LON_MAX = 32.8, LAT_MIN = 51.25, LAT_MAX = 56.2;
const LAT0 = 53.7;
const K = Math.cos((LAT0 * Math.PI) / 180);
const PAD = 14;
const VBW = 600;
const GEO_W = (LON_MAX - LON_MIN) * K;
const GEO_H = LAT_MAX - LAT_MIN;
const SCALE = (VBW - 2 * PAD) / GEO_W;
const VBH = GEO_H * SCALE + 2 * PAD;
const projX = (lon: number) => PAD + (lon - LON_MIN) * K * SCALE;
const projY = (lat: number) => PAD + (LAT_MAX - lat) * SCALE;

/* Порядок и текстовые символы типов (текстовая альтернатива цвету). */
const TYPE_ORDER = ['T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'TX'] as const;
const TYPE_SYMBOL: Record<string, string> = {
  T1: '●', T2: '▲', T3: '■', T4: '◆', T5: '✕', T6: '⬢', TX: '·',
};
const QUALITY_SYMBOL: Record<string, string> = { A: '●', B: '◯', C: '◌' };
const QUALITY_COLOR: Record<string, string> = {
  A: 'var(--accent)', B: 'var(--accent-2)', C: 'var(--muted)',
};

/** Форма маркера типа (центр в 0,0). Цвет — TYPE_COLORS. */
function typeGlyph(type: string, r: number) {
  const color = TYPE_COLORS[type] ?? 'var(--muted)';
  switch (type) {
    case 'T2': // треугольник
      return <polygon points={`0,${-r} ${(-0.87 * r).toFixed(1)},${(0.55 * r).toFixed(1)} ${(0.87 * r).toFixed(1)},${(0.55 * r).toFixed(1)}`} fill={color} />;
    case 'T3': { // квадрат
      const s = r * 0.9;
      return <rect x={-s} y={-s} width={2 * s} height={2 * s} rx={1} fill={color} />;
    }
    case 'T4': // ромб
      return <polygon points={`0,${-r} ${r},0 0,${r} ${-r},0`} fill={color} />;
    case 'T5': { // крест
      const w = Math.max(2, r * 0.5);
      return (
        <g stroke={color} strokeWidth={w} strokeLinecap="round">
          <line x1={-r} y1={-r} x2={r} y2={r} />
          <line x1={-r} y1={r} x2={r} y2={-r} />
        </g>
      );
    }
    case 'T6': { // шестиугольник
      const pts = Array.from({ length: 6 }, (_, i) => {
        const a = (Math.PI / 3) * i - Math.PI / 2;
        return `${(Math.cos(a) * r).toFixed(1)},${(Math.sin(a) * r).toFixed(1)}`;
      }).join(' ');
      return <polygon points={pts} fill={color} />;
    }
    case 'TX': // точка
      return <circle r={Math.max(1.6, r * 0.55)} fill={color} />;
    default: // T1 — круг
      return <circle r={r} fill={color} />;
  }
}

/** Форма маркера качества: A заполненный круг, B кольцо, C пунктирное кольцо. */
function qualityGlyph(quality: string, r: number) {
  const color = QUALITY_COLOR[quality] ?? 'var(--muted)';
  if (quality === 'A') return <circle r={r} fill={color} />;
  if (quality === 'B') return <circle r={r} fill="none" stroke={color} strokeWidth={2} />;
  return <circle r={r} fill="none" stroke={color} strokeWidth={2} strokeDasharray="3 3" />;
}

/** Мини-глиф для легенды/таблицы. */
function LegendGlyph({ mode, code }: { mode: Mode; code: string }) {
  return (
    <svg width={18} height={18} viewBox="-10 -10 20 20" aria-hidden="true" style={{ flex: '0 0 auto' }}>
      {mode === 'type' ? typeGlyph(code, 7) : qualityGlyph(code, 6.5)}
    </svg>
  );
}

/** Реакция на prefers-reduced-motion через matchMedia. */
function useReducedMotion(): boolean {
  const [reduce, setReduce] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const on = () => setReduce(mq.matches);
    on();
    mq.addEventListener?.('change', on);
    return () => mq.removeEventListener?.('change', on);
  }, []);
  return reduce;
}

export default function ConfidenceMap({
  story,
  selected,
  onSelect,
}: {
  story: Story;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const t = useT();
  const lang = useLang();
  const reduce = useReducedMotion();

  const [mode, setMode] = useState<Mode>('type');
  const [region, setRegion] = useState<string>('all');
  const [rings, setRings] = useState<Ring[] | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [renderW, setRenderW] = useState(VBW);
  const wrapRef = useRef<HTMLDivElement>(null);

  const name = (c: StoryCity) => (lang === 'be' ? c.be || c.ru : c.ru);

  /* --- контур страны из adm1.geojson (внешние и внутренние кольца) --- */
  useEffect(() => {
    let alive = true;
    fetch('/data/geo/adm1.geojson')
      .then((r) => r.json())
      .then((g: { features?: { geometry?: { type: string; coordinates: unknown } }[] }) => {
        if (!alive) return;
        const out: Ring[] = [];
        for (const f of g.features ?? []) {
          const geom = f.geometry;
          if (!geom) continue;
          const polys: unknown[] =
            geom.type === 'Polygon' ? [geom.coordinates]
            : geom.type === 'MultiPolygon' ? (geom.coordinates as unknown[])
            : [];
          for (const poly of polys) for (const ring of poly as Ring[]) out.push(ring as Ring);
        }
        setRings(out);
      })
      .catch(() => { if (alive) setRings([]); });
    return () => { alive = false; };
  }, []);

  /* фактическая ширина отрисовки — для перевода координат viewBox в пиксели тултипа */
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const w = el.clientWidth;
      if (w > 40) setRenderW(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const cities = useMemo(() => Object.values(story.cities), [story]);

  const contourD = useMemo(() => {
    if (!rings || rings.length === 0) return null;
    return rings
      .map((ring) =>
        ring
          .map((p, i) => `${i ? 'L' : 'M'}${projX(p[0]).toFixed(1)},${projY(p[1]).toFixed(1)}`)
          .join('') + 'Z',
      )
      .join(' ');
  }, [rings]);

  /* нормировка размера маркера: sqrt(popNow) → 3..20 px */
  const rFor = useMemo(() => {
    const sq = cities.map((c) => Math.sqrt(c.popNow ?? 0)).filter((v) => v > 0);
    const lo = sq.length ? Math.min(...sq) : 0;
    const hi = sq.length ? Math.max(...sq) : 1;
    const span = hi - lo || 1;
    return (pop: number | null) => {
      if (pop == null || pop <= 0) return 3;
      return 3 + ((Math.sqrt(pop) - lo) / span) * 17;
    };
  }, [cities]);

  const regionCodes = useMemo(() => {
    const set = new Set(cities.map((c) => c.region));
    return (['BY-BR', 'BY-VI', 'BY-HO', 'BY-HR', 'BY-MA', 'BY-MI', 'BY-HM'] as const).filter((r) => set.has(r));
  }, [cities]);

  const shown = useMemo(
    () => (region === 'all' ? cities : cities.filter((c) => c.region === region)),
    [cities, region],
  );

  /* порядок отрисовки: крупные снизу, мелкие сверху (кликабельность), выбранный — последним */
  const drawOrder = useMemo(() => {
    const rest = shown
      .filter((c) => c.id !== selected)
      .sort((a, b) => (b.popNow ?? 0) - (a.popNow ?? 0));
    const sel = shown.find((c) => c.id === selected);
    return sel ? [...rest, sel] : rest;
  }, [shown, selected]);

  const tableRows = useMemo(
    () => [...cities].sort((a, b) => a.ru.localeCompare(b.ru, 'ru')),
    [cities],
  );

  const qCount = useMemo(() => {
    const c = { A: 0, B: 0, C: 0 } as Record<string, number>;
    for (const city of cities) c[city.quality] = (c[city.quality] ?? 0) + 1;
    return c;
  }, [cities]);

  const scale = renderW / VBW;
  const activeCity = active ? story.cities[active] : null;
  const pct = (v: number) => `${fmtNum(v * 100, 0)}%`;

  const modeDesc =
    mode === 'type'
      ? t('Режим «тип траектории»: цвет и форма маркера кодируют тип.')
      : t('Режим «качество данных»: форма маркера кодирует класс A, B или C.');
  const mapLabel = `${t('Карта городов Беларуси: каждый маркер — город, размер — по числу жителей.')} ${modeDesc}`;

  const legendTypes = TYPE_ORDER.filter((ty) => (story.national.type_counts[ty] ?? 0) > 0);

  return (
    <div className="chart-block">
      {/* ------- управление ------- */}
      <div className="urban-controls">
        <div className="seg urban-seg" role="group" aria-label={t('Режим карты')}>
          <button type="button" className={mode === 'type' ? 'on' : ''}
            aria-pressed={mode === 'type'} onClick={() => setMode('type')}>
            {t('Тип траектории')}
          </button>
          <button type="button" className={mode === 'quality' ? 'on' : ''}
            aria-pressed={mode === 'quality'} onClick={() => setMode('quality')}>
            {t('Качество данных')}
          </button>
        </div>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12.5 }}>
          <span style={{ color: 'var(--muted)' }}>{t('Область')}</span>
          <select value={region} onChange={(e) => setRegion(e.target.value)}>
            <option value="all">{t('Все области')}</option>
            {regionCodes.map((r) => (
              <option key={r} value={r}>{t(REGION_LABELS[r])}</option>
            ))}
          </select>
        </label>
      </div>

      {/* ------- карта ------- */}
      <div className="urban-canvas-wrap" ref={wrapRef} style={{ position: 'relative' }}>
        <svg
          viewBox={`0 0 ${VBW} ${VBH.toFixed(1)}`}
          width="100%"
          style={{ height: 'auto', display: 'block' }}
          role="img"
          aria-label={mapLabel}
          preserveAspectRatio="xMidYMid meet"
        >
          {contourD && (
            <path d={contourD} fill="none" stroke="var(--border)" strokeWidth={1.2}
              strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
          )}

          {drawOrder.map((c) => {
            const x = projX(c.lon);
            const y = projY(c.lat);
            const isSel = c.id === selected;
            const isActive = c.id === active;
            const r = rFor(c.popNow) + (!reduce && (isActive || isSel) ? 2 : 0);
            const label =
              `${name(c)}. ${t('Тип')}: ${t(TYPE_LABELS[c.type] ?? c.type)}. ` +
              `${t('Согласие сценариев')}: ${pct(c.agreement)}. ` +
              `${t('Класс данных')}: ${c.quality}.` +
              (c.qualityReasons ? ` ${t('Оговорки')}: ${c.qualityReasons}.` : '');
            return (
              <g
                key={c.id}
                transform={`translate(${x.toFixed(1)} ${y.toFixed(1)})`}
                role="button"
                tabIndex={0}
                aria-label={label}
                aria-pressed={isSel}
                style={{ cursor: 'pointer', outline: 'none' }}
                onClick={() => onSelect(c.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(c.id); }
                }}
                onPointerEnter={() => setActive(c.id)}
                onPointerLeave={() => setActive((a) => (a === c.id ? null : a))}
                onFocus={() => setActive(c.id)}
                onBlur={() => setActive((a) => (a === c.id ? null : a))}
              >
                {/* невидимая зона захвата — надёжный клик/hover даже для тонкого креста */}
                <circle r={r + 5} fill="transparent" />
                {mode === 'type' ? typeGlyph(c.type, r) : qualityGlyph(c.quality, r)}
                {isSel && <circle r={r + 4} fill="none" stroke="var(--ink)" strokeWidth={2} />}
                {isActive && !isSel && (
                  <circle r={r + 4} fill="none" stroke="var(--ink-2)" strokeWidth={1.5} />
                )}
              </g>
            );
          })}
        </svg>

        {activeCity && (
          <div
            className="chart-tooltip"
            style={{
              left: Math.min(Math.max(projX(activeCity.lon) * scale + 10, 4), Math.max(4, renderW - 190)),
              top: Math.max(4, projY(activeCity.lat) * scale - 8),
            }}
          >
            <div style={{ fontWeight: 650 }}>{name(activeCity)}</div>
            <div style={{ color: 'var(--muted)', fontSize: 11 }}>
              {t(REGION_LABELS[activeCity.region] ?? activeCity.region)}
            </div>
            <div className="ct-row" style={{ marginTop: 2 }}>
              <LegendGlyph mode="type" code={activeCity.type} />
              <span>{t(TYPE_LABELS[activeCity.type] ?? activeCity.type)}</span>
            </div>
            <div style={{ fontSize: 11.5 }}>
              {t('Согласие сценариев')}: <b>{pct(activeCity.agreement)}</b>
            </div>
            <div style={{ fontSize: 11.5 }}>
              {t('Класс данных')}: <b>{activeCity.quality}</b>
            </div>
            {activeCity.qualityReasons && (
              <div style={{ fontSize: 11, color: 'var(--muted)', whiteSpace: 'normal', maxWidth: 200 }}>
                {activeCity.qualityReasons}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ------- счётчики ------- */}
      <div className="urban-counters">
        <span>
          {t('Показано на карте')}: <b>{shown.length}</b> {t('из')} <b>{cities.length}</b>
        </span>
        <span>
          {t('Класс данных')}: <b>A {qCount.A}</b> · <b>B {qCount.B}</b> · <b>C {qCount.C}</b>
        </span>
        <span>{t('Размер маркера — по числу текущих жителей')}</span>
      </div>

      {/* ------- легенда ------- */}
      {mode === 'type' ? (
        <div className="urban-legend" aria-hidden="true">
          {legendTypes.map((ty) => (
            <span className="lg" key={ty}>
              <LegendGlyph mode="type" code={ty} />
              {t(TYPE_LABELS[ty])} <b style={{ fontVariantNumeric: 'tabular-nums' }}>({story.national.type_counts[ty] ?? 0})</b>
            </span>
          ))}
        </div>
      ) : (
        <div className="urban-legend" aria-hidden="true">
          <span className="lg"><LegendGlyph mode="quality" code="A" /> {t('A — полные ряды и устойчивые границы')} <b>({qCount.A})</b></span>
          <span className="lg"><LegendGlyph mode="quality" code="B" /> {t('B — есть оговорки в данных')} <b>({qCount.B})</b></span>
          <span className="lg"><LegendGlyph mode="quality" code="C" /> {t('C — не участвует в рейтингах')} <b>({qCount.C})</b></span>
        </div>
      )}

      <p className="hint" style={{ marginTop: 8 }}>
        {t('Тип — классификация траектории по прозрачным правилам (расчёт). Класс данных — полнота и надёжность рядов (наблюдение и оценка). Карта — не единственный способ прочитать вывод: полная таблица ниже.')}
      </p>

      {/* ------- обязательная текстовая альтернатива ------- */}
      <details className="urban-fallback">
        <summary>{t('Таблица всех городов (текстовая альтернатива карте)')}</summary>
        <div className="zone-table-wrap">
          <table className="zone-table">
            <thead>
              <tr>
                <th>{t('Город')}</th>
                <th>{t('Область')}</th>
                <th>{t('Тип траектории')}</th>
                <th>{t('Согласие сценариев')}</th>
                <th>{t('Класс данных')}</th>
                <th>{t('Оговорки')}</th>
              </tr>
            </thead>
            <tbody>
              {tableRows.map((c) => (
                <tr key={c.id} className={c.id === selected ? 'sel' : undefined}>
                  <td>
                    <button
                      type="button"
                      className="btn"
                      style={{ padding: '2px 8px' }}
                      aria-pressed={c.id === selected}
                      onClick={() => onSelect(c.id)}
                    >
                      {name(c)}
                    </button>
                  </td>
                  <td>{t(REGION_LABELS[c.region] ?? c.region)}</td>
                  <td>
                    <span aria-hidden="true" style={{ color: TYPE_COLORS[c.type] ?? 'var(--muted)' }}>
                      {TYPE_SYMBOL[c.type] ?? '·'}
                    </span>{' '}
                    {t(TYPE_LABELS[c.type] ?? c.type)}
                  </td>
                  <td style={{ fontVariantNumeric: 'tabular-nums' }}>{pct(c.agreement)}</td>
                  <td>
                    <span aria-hidden="true" style={{ color: QUALITY_COLOR[c.quality] }}>
                      {QUALITY_SYMBOL[c.quality] ?? ''}
                    </span>{' '}
                    {c.quality}
                  </td>
                  <td style={{ whiteSpace: 'normal', color: 'var(--muted)' }}>
                    {c.qualityReasons || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
