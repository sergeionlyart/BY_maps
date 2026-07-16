'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useLang, useT } from '@/lib/i18n';
import { useMedia } from '@/lib/useMedia';
import {
  fmtNum,
  ratePct,
  REGION_LABELS,
  Story,
  TYPE_COLORS,
  TYPE_LABELS,
  type CityMain,
} from '@/components/urban/types';

interface Props {
  story: Story;
  selected: string | null;
  onSelect: (id: string) => void;
}

/** Одна точка диаграммы: город с рассчитанными координатами. */
interface PPoint {
  id: string;
  ru: string;
  be: string;
  region: string;
  quality: 'A' | 'B' | 'C';
  type: string;
  x: number; // изменение населения 1990→2020, %
  y: number; // изменение фонда 1990→2020, %
  r: number; // радиус, px (∝ √населения 2020)
  m: CityMain;
}

const M = { top: 18, right: 20, bottom: 44, left: 54 };
const R_MIN = 3;
const R_MAX = 24;
const TYPE_ORDER = ['T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'TX'];

/** Приятный шаг оси для домена [min,max] (кратный 1/2/2.5/5·10ⁿ). */
function niceStep(rough: number): number {
  if (rough <= 0) return 1;
  const mag = Math.pow(10, Math.floor(Math.log10(rough)));
  for (const m of [1, 2, 2.5, 5, 10]) if (rough <= m * mag) return m * mag;
  return 10 * mag;
}

/** Тики оси, включающие 0, от min до max. */
function axisTicks(min: number, max: number, n = 5): number[] {
  const step = niceStep((max - min) / n);
  const start = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= max + step * 1e-6; v += step) {
    ticks.push(Math.abs(v) < step * 1e-6 ? 0 : v);
  }
  return ticks;
}

interface Box { x: number; y: number; w: number; h: number; }
function overlaps(a: Box, b: Box): boolean {
  return !(a.x + a.w < b.x || b.x + b.w < a.x || a.y + a.h < b.y || b.y + b.h < a.y);
}

export default function OverhangScatter({ story, selected, onSelect }: Props) {
  const t = useT();
  const lang = useLang();
  const reduced = useMedia('(prefers-reduced-motion: reduce)');
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [active, setActive] = useState<string | null>(null);
  const [region, setRegion] = useState<string>('all');
  const [showC, setShowC] = useState(false);
  const [query, setQuery] = useState('');

  // ширина через ResizeObserver (как в LineChart)
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

  const name = (p: { ru: string; be: string }) => (lang === 'be' ? p.be || p.ru : p.ru);

  // все города с main → точки с координатами и радиусом (домен и размеры стабильны при фильтрах)
  const all = useMemo<PPoint[]>(() => {
    const list = Object.values(story.cities).filter((c) => c.main != null);
    const sq = list.map((c) => Math.sqrt(c.main!.p2020));
    const sMin = Math.min(...sq);
    const sMax = Math.max(...sq);
    return list.map((c) => {
      const m = c.main!;
      const x = (Math.exp(m.pgr * 30) - 1) * 100;
      const y = (Math.exp(m.bgr * 30) - 1) * 100;
      const s = Math.sqrt(m.p2020);
      const r = R_MIN + (sMax > sMin ? (s - sMin) / (sMax - sMin) : 0) * (R_MAX - R_MIN);
      return {
        id: c.id, ru: c.ru, be: c.be, region: c.region,
        quality: c.quality, type: c.type, x, y, r, m,
      };
    });
  }, [story]);

  const byId = useMemo(() => {
    const map = new Map<string, PPoint>();
    for (const p of all) map.set(p.id, p);
    return map;
  }, [all]);

  // регионы, реально присутствующие в данных (в порядке словаря)
  const regions = useMemo(() => {
    const present = new Set(all.map((p) => p.region));
    return Object.keys(REGION_LABELS).filter((k) => present.has(k));
  }, [all]);

  // видимый набор: фильтр по региону и классу C; выбранный город обходит фильтр C
  const visible = useMemo(
    () =>
      all.filter((p) => {
        const passRegion = region === 'all' || p.region === region;
        const passC = showC || p.quality !== 'C';
        return passRegion && (passC || p.id === selected);
      }),
    [all, region, showC, selected],
  );

  // домен по всем данным + паддинг; ноль всегда виден на обеих осях
  const [xMin, xMax, yMin, yMax] = useMemo(() => {
    const xv = all.map((p) => p.x);
    const yv = all.map((p) => p.y);
    let x0 = Math.min(...xv), x1 = Math.max(...xv);
    let y0 = Math.min(...yv), y1 = Math.max(...yv);
    const xp = (x1 - x0) * 0.08 || 1;
    const yp = (y1 - y0) * 0.08 || 1;
    x0 = Math.min(0, x0 - xp); x1 = Math.max(0, x1 + xp);
    y0 = Math.min(0, y0 - yp); y1 = Math.max(0, y1 + yp);
    return [x0, x1, y0, y1];
  }, [all]);

  const height = Math.round(Math.min(470, Math.max(330, width * 0.6)));
  const iw = Math.max(1, width - M.left - M.right);
  const ih = Math.max(1, height - M.top - M.bottom);
  const X = (v: number) => M.left + ((v - xMin) / (xMax - xMin || 1)) * iw;
  const Y = (v: number) => M.top + ih - ((v - yMin) / (yMax - yMin || 1)) * ih;

  const xTicks = useMemo(() => axisTicks(xMin, xMax), [xMin, xMax]);
  const yTicks = useMemo(() => axisTicks(yMin, yMax), [yMin, yMax]);

  // диагональ y=x (равный темп): отрезок в пределах пересечения доменов
  const diagLo = Math.max(xMin, yMin);
  const diagHi = Math.min(xMax, yMax);

  // подписываемые города: кейсы + Минск + выбранный (те, что видимы и имеют main)
  const labelled = useMemo(() => {
    const ids = new Set<string>(story.cases.map((c) => c.city_id));
    ids.add('c-minsk');
    if (selected) ids.add(selected);
    const vis = new Set(visible.map((p) => p.id));
    return [...ids]
      .map((id) => byId.get(id))
      .filter((p): p is PPoint => p != null && vis.has(p.id))
      .sort((a, b) => a.x - b.x || a.id.localeCompare(b.id));
  }, [story.cases, selected, visible, byId]);

  // раскладка подписей с простым уклонением от коллизий
  const labels = useMemo(() => {
    const placed: Box[] = [];
    const out: { id: string; tx: number; ty: number; anchor: 'start' | 'middle' | 'end'; text: string; sel: boolean }[] = [];
    for (const p of labelled) {
      const cx = X(p.x), cy = Y(p.y);
      const text = name(p);
      const w = text.length * 6.4 + 4;
      const cands: { dx: number; dy: number; anchor: 'start' | 'middle' | 'end' }[] = [
        { dx: p.r + 6, dy: 4, anchor: 'start' },
        { dx: -(p.r + 6), dy: 4, anchor: 'end' },
        { dx: 0, dy: -(p.r + 7), anchor: 'middle' },
        { dx: 0, dy: p.r + 15, anchor: 'middle' },
      ];
      let chosen = cands[0];
      let chosenBox: Box | null = null;
      for (const c of cands) {
        const tx = cx + c.dx, ty = cy + c.dy;
        const bx = c.anchor === 'end' ? tx - w : c.anchor === 'middle' ? tx - w / 2 : tx;
        const box: Box = { x: bx, y: ty - 11, w, h: 14 };
        if (!placed.some((q) => overlaps(box, q))) { chosen = c; chosenBox = box; break; }
        if (!chosenBox) chosenBox = box;
      }
      if (chosenBox) placed.push(chosenBox);
      out.push({
        id: p.id, tx: cx + chosen.dx, ty: cy + chosen.dy,
        anchor: chosen.anchor, text, sel: p.id === selected,
      });
    }
    return out;
  }, [labelled, selected, xMin, xMax, yMin, yMax, width, height]);

  // сопоставление имени из поиска → выбор города
  const onSearch = (val: string) => {
    setQuery(val);
    const q = val.trim().toLocaleLowerCase('ru-RU');
    if (!q) return;
    const hit = all.find((p) => name(p).toLocaleLowerCase('ru-RU') === q);
    if (hit) onSelect(hit.id);
  };

  // таблица-фолбэк: видимый набор, сортировка по MOR убыв.
  const tableRows = useMemo(
    () => [...visible].sort((a, b) => b.m.mor - a.m.mor),
    [visible],
  );

  const activePt = active ? byId.get(active) : null;
  const trans = reduced ? 'none' : 'opacity .12s ease, stroke-width .12s ease';

  const key = (id: string) => (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
      e.preventDefault();
      onSelect(id);
    }
  };

  const qualityWord = (q: string) => `${t('класс')} ${q}`;
  const pDigits = (pop: number) => (pop >= 100000 ? 0 : 1);

  const pointAria = (p: PPoint) =>
    `${name(p)}. ${t('изменение населения')} ${ratePct(p.m.pgr, 30)}, ` +
    `${t('изменение фонда')} ${ratePct(p.m.bgr, 30)}. ` +
    `${t('навес')} ${fmtNum(p.m.mor * 100, 2)} ${t('%/год')}. ` +
    `${t(TYPE_LABELS[p.type] ?? p.type)}, ${qualityWord(p.quality)}. ` +
    t('Нажмите, чтобы выбрать город.');

  const svgAria =
    `${t('Диаграмма рассеяния «Люди и физический город».')} ${visible.length} ` +
    t('городов; по горизонтали — изменение населения 1990→2020 в процентах, по вертикали — изменение застроенного фонда в процентах. Точки выше диагонали означают рост фонда на жителя.');

  // позиция тултипа
  const ttLeft = activePt ? Math.min(Math.max(X(activePt.x) + 14, 6), Math.max(6, width - 210)) : 0;
  const ttTop = activePt ? Math.min(Math.max(Y(activePt.y) - 12, 6), Math.max(6, height - 132)) : 0;

  /** Маркер по классу качества: A — круг, B — ромб, C — полый штриховой круг. */
  const marker = (p: PPoint, opts: { color: string; sel: boolean; act: boolean }) => {
    const cx = X(p.x), cy = Y(p.y), r = p.r;
    const ink = 'var(--ink)';
    const stroke = opts.sel ? ink : opts.act ? ink : undefined;
    const sw = opts.sel ? 2 : opts.act ? 1.5 : undefined;
    if (p.quality === 'C') {
      return (
        <circle cx={cx} cy={cy} r={r} fill="none"
          stroke={stroke ?? opts.color} strokeWidth={sw ?? 1.5}
          strokeDasharray="3 2" opacity={0.9} style={{ pointerEvents: 'none', transition: trans }} />
      );
    }
    if (p.quality === 'B') {
      const rr = r * 1.15;
      return (
        <path d={`M${cx},${cy - rr} L${cx + rr},${cy} L${cx},${cy + rr} L${cx - rr},${cy} Z`}
          fill={opts.color} fillOpacity={0.75} stroke={stroke} strokeWidth={sw}
          style={{ pointerEvents: 'none', transition: trans }} />
      );
    }
    return (
      <circle cx={cx} cy={cy} r={r} fill={opts.color} fillOpacity={0.75}
        stroke={stroke} strokeWidth={sw}
        style={{ pointerEvents: 'none', transition: trans }} />
    );
  };

  // порядок отрисовки: крупные снизу, мелкие сверху; выбранный/активный поверх
  const drawOrder = useMemo(() => {
    const arr = [...visible].sort((a, b) => b.r - a.r);
    const lift = (id: string | null) => {
      if (!id) return;
      const i = arr.findIndex((p) => p.id === id);
      if (i >= 0) arr.push(arr.splice(i, 1)[0]);
    };
    lift(selected);
    lift(active);
    return arr;
  }, [visible, selected, active]);

  return (
    <div className="chart-block">
      {/* -------- фильтры -------- */}
      <div className="urban-controls">
        <label>
          {t('Регион')}:{' '}
          <select value={region} onChange={(e) => setRegion(e.target.value)}>
            <option value="all">{t('Все регионы')}</option>
            {regions.map((k) => (
              <option key={k} value={k}>{t(REGION_LABELS[k])}</option>
            ))}
          </select>
        </label>
        <label>
          <input type="checkbox" checked={showC} onChange={(e) => setShowC(e.target.checked)} />{' '}
          {t('Показывать класс качества C')}
        </label>
        <label>
          {t('Найти город')}:{' '}
          <input type="search" list="overhang-scatter-cities" value={query}
            placeholder={t('название…')}
            onChange={(e) => onSearch(e.target.value)} />
        </label>
        <datalist id="overhang-scatter-cities">
          {all.map((p) => <option key={p.id} value={name(p)} />)}
        </datalist>
        <span className="urban-badge">{t('Показано городов:')} {visible.length}</span>
      </div>

      {/* -------- диаграмма -------- */}
      <div className="chart-svg-wrap" ref={wrapRef}>
        <svg width={width} height={height} role="img" aria-label={svgAria}>
          <defs>
            <clipPath id="overhang-plot">
              <rect x={M.left} y={M.top} width={iw} height={ih} />
            </clipPath>
          </defs>

          {/* сетка + тики */}
          {yTicks.map((tk) => (
            <g key={`y${tk}`}>
              <line x1={M.left} x2={width - M.right} y1={Y(tk)} y2={Y(tk)}
                stroke="var(--grid)" strokeWidth="1" />
              <text x={M.left - 6} y={Y(tk) + 3.5} textAnchor="end" fontSize="10"
                fill="var(--muted)" style={{ fontVariantNumeric: 'tabular-nums' }}>
                {tk.toLocaleString('ru-RU')}
              </text>
            </g>
          ))}
          {xTicks.map((tk) => (
            <g key={`x${tk}`}>
              <line x1={X(tk)} x2={X(tk)} y1={M.top} y2={M.top + ih}
                stroke="var(--grid)" strokeWidth="1" />
              <text x={X(tk)} y={M.top + ih + 15} textAnchor="middle" fontSize="10"
                fill="var(--muted)" style={{ fontVariantNumeric: 'tabular-nums' }}>
                {tk.toLocaleString('ru-RU')}
              </text>
            </g>
          ))}

          {/* нулевые оси */}
          <line x1={X(0)} x2={X(0)} y1={M.top} y2={M.top + ih}
            stroke="var(--baseline)" strokeWidth="1.5" />
          <line x1={M.left} x2={width - M.right} y1={Y(0)} y2={Y(0)}
            stroke="var(--baseline)" strokeWidth="1.5" />

          {/* диагональ равного темпа y=x */}
          {diagHi > diagLo && (
            <g clipPath="url(#overhang-plot)">
              <line x1={X(diagLo)} y1={Y(diagLo)} x2={X(diagHi)} y2={Y(diagHi)}
                stroke="var(--muted)" strokeWidth="1" strokeDasharray="5 4" />
              <text x={X(diagHi) - 4} y={Y(diagHi) - 5} textAnchor="end"
                fontSize="10.5" fill="var(--muted)">
                {t('фонд растёт в темп населения')}
              </text>
            </g>
          )}

          {/* точки */}
          {drawOrder.map((p) => {
            const color = TYPE_COLORS[p.type] ?? 'var(--muted)';
            const isSel = p.id === selected;
            const isAct = p.id === active;
            const cx = X(p.x), cy = Y(p.y);
            return (
              <g key={p.id}>
                {marker(p, { color, sel: isSel, act: isAct })}
                {/* прозрачная зона захвата + фокус/клик */}
                <circle
                  cx={cx} cy={cy} r={Math.max(p.r + 4, 11)}
                  fill="transparent"
                  tabIndex={0}
                  role="button"
                  aria-label={pointAria(p)}
                  aria-pressed={isSel}
                  style={{ cursor: 'pointer', outline: 'none' }}
                  onMouseEnter={() => setActive(p.id)}
                  onMouseLeave={() => setActive((a) => (a === p.id ? null : a))}
                  onFocus={() => setActive(p.id)}
                  onBlur={() => setActive((a) => (a === p.id ? null : a))}
                  onClick={() => onSelect(p.id)}
                  onKeyDown={key(p.id)}
                />
              </g>
            );
          })}

          {/* подписи городов */}
          {labels.map((l) => (
            <text key={l.id} x={l.tx} y={l.ty} textAnchor={l.anchor}
              fontSize={l.sel ? '11.5' : '10.5'}
              fontWeight={l.sel ? 650 : 500}
              fill={l.sel ? 'var(--ink)' : 'var(--ink-2)'}
              style={{ pointerEvents: 'none', paintOrder: 'stroke' }}
              stroke="var(--page)" strokeWidth={l.sel ? 3 : 2.5} strokeLinejoin="round">
              {l.text}
            </text>
          ))}
          {/* дубль подписей поверх обводки (paint-order fallback) */}
          {labels.map((l) => (
            <text key={`t${l.id}`} x={l.tx} y={l.ty} textAnchor={l.anchor}
              fontSize={l.sel ? '11.5' : '10.5'}
              fontWeight={l.sel ? 650 : 500}
              fill={l.sel ? 'var(--ink)' : 'var(--ink-2)'}
              style={{ pointerEvents: 'none' }}>
              {l.text}
            </text>
          ))}

          {/* заголовки осей */}
          <text x={M.left + iw / 2} y={height - 4} textAnchor="middle"
            fontSize="11" fill="var(--ink-2)">
            {t('изменение населения 1990→2020, %')}
          </text>
          <text transform={`translate(13,${M.top + ih / 2}) rotate(-90)`} textAnchor="middle"
            fontSize="11" fill="var(--ink-2)">
            {t('изменение фонда 1990→2020, %')}
          </text>
        </svg>

        {/* тултип */}
        {activePt && (
          <div className="chart-tooltip" style={{ left: ttLeft, top: ttTop }}>
            <div style={{ fontWeight: 650, marginBottom: 2 }}>{name(activePt)}</div>
            <div className="ct-year">
              {t('Население')}: {fmtNum(activePt.m.p1990 / 1000, pDigits(activePt.m.p1990))} → {fmtNum(activePt.m.p2020 / 1000, pDigits(activePt.m.p2020))} {t('тыс.')}
            </div>
            <div className="ct-year">
              {t('Фонд')}: {fmtNum(activePt.m.b1990, 1)} → {fmtNum(activePt.m.b2020, 1)} {t('км²')}
            </div>
            <div className="ct-year">
              {t('Навес (MOR)')}: {fmtNum(activePt.m.mor * 100, 2)} {t('%/год')} · [{fmtNum(activePt.m.morLo * 100, 2)}; {fmtNum(activePt.m.morHi * 100, 2)}]
            </div>
            <div className="ct-year" style={{ color: activePt.m.robust ? 'var(--pos)' : 'var(--neg)' }}>
              {activePt.m.robust ? t('устойчив к 9 сценариям границ') : t('неустойчиво')}
            </div>
            <div className="ct-year">{t(TYPE_LABELS[activePt.type] ?? activePt.type)}</div>
            <div className="ct-year">{qualityWord(activePt.quality)}</div>
          </div>
        )}
      </div>

      {/* -------- легенда -------- */}
      <div className="urban-legend">
        <b style={{ color: 'var(--ink-2)', fontWeight: 600 }}>{t('Тип траектории')}:</b>
        {TYPE_ORDER.filter((ty) => story.national.type_counts[ty] != null).map((ty) => (
          <span className="lg" key={ty}>
            <span className="sw" style={{ background: TYPE_COLORS[ty] ?? 'var(--muted)' }} />
            {t(TYPE_LABELS[ty] ?? ty)} <b>{story.national.type_counts[ty]}</b>
          </span>
        ))}
      </div>
      <div className="urban-legend">
        <b style={{ color: 'var(--ink-2)', fontWeight: 600 }}>{t('Класс качества')}:</b>
        <span className="lg">
          <svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="5" fill="var(--ink-2)" /></svg>
          {t('Класс A')}
        </span>
        <span className="lg">
          <svg width="14" height="14" aria-hidden="true"><path d="M7,1 L13,7 L7,13 L1,7 Z" fill="var(--ink-2)" /></svg>
          {t('Класс B')}
        </span>
        <span className="lg">
          <svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="5" fill="none" stroke="var(--ink-2)" strokeWidth="1.4" strokeDasharray="3 2" /></svg>
          {t('Класс C')}
        </span>
      </div>

      <p className="hint">
        {t('Площадь круга пропорциональна населению 2020 года. Δ — изменение за 30 лет (1990→2020). Население — переписи и оценки (наблюдение); фонд — спутниковая оценка GHS-BUILT-S. Города класса C не участвуют в рейтингах.')}
      </p>

      {/* -------- таблица-фолбэк -------- */}
      <details className="urban-fallback">
        <summary>{t('Показать данные таблицей')}</summary>
        <div className="zone-table-wrap">
          <table className="zone-table">
            <caption className="sr-only">{t('Города: изменение населения и фонда, материальный навес')}</caption>
            <thead>
              <tr>
                <th>{t('Город')}</th>
                <th>{t('Δ населения, %')}</th>
                <th>{t('Δ фонда, %')}</th>
                <th>{t('MOR, %/год')}</th>
                <th>{t('Тип')}</th>
                <th>{t('Качество')}</th>
              </tr>
            </thead>
            <tbody>
              {tableRows.map((p) => (
                <tr key={p.id} className={p.id === selected ? 'sel' : undefined}>
                  <td>
                    <button type="button"
                      style={{ background: 'none', border: 'none', padding: 0, color: 'var(--accent)', cursor: 'pointer', font: 'inherit', textAlign: 'left' }}
                      onClick={() => onSelect(p.id)}>
                      {name(p)}
                    </button>
                  </td>
                  <td className={p.x < 0 ? 'neg' : 'pos'}>{ratePct(p.m.pgr, 30)}</td>
                  <td className={p.m.bgr < 0 ? 'neg' : 'pos'}>{ratePct(p.m.bgr, 30)}</td>
                  <td>{fmtNum(p.m.mor * 100, 2)}</td>
                  <td>{t(TYPE_LABELS[p.type] ?? p.type)}</td>
                  <td>{p.quality}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
