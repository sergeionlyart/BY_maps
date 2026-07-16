'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useLang, useT } from '@/lib/i18n';
import { fmtNum, Story, StoryCity } from '@/components/urban/types';

/** INF-12 «Инфраструктура сегодня»: современный срез OSM (снимок июля 2026).
 *  Горизонтальный дот-плот — км улично-дорожной сети выбранного класса на 1000
 *  текущих жителей; цвет по динамике населения 1990–2020. Ниже — таблица точек
 *  сервисов (POI) выбранного города против медианы по всем городам.
 *  Всё описательное: OSM неполон и не датирует строительство. */

type RoadClass = 'all' | 'major' | 'local';
type Group = 'declining' | 'growing' | 'stable' | 'unknown';

interface Props {
  story: Story;
  selected: string | null;
  onSelect: (id: string) => void;
}

const CLASS_KEYS: RoadClass[] = ['all', 'major', 'local'];
const CLASS_LABEL: Record<RoadClass, string> = {
  all: 'Все',
  major: 'Магистральные',
  local: 'Локальные улицы',
};

const GROUP_LABEL: Record<Group, string> = {
  declining: 'сокращающиеся',
  growing: 'растущие',
  stable: 'стабильные',
  unknown: 'нет данных о динамике',
};
const GROUP_COLOR: Record<Group, string> = {
  declining: 'var(--accent-2)', // медь
  growing: 'var(--accent)',     // синий
  stable: 'var(--muted)',
  unknown: 'var(--muted)',
};

/** Категории точек сервисов (POI) в порядке показа. Ключ = поле в city.poi. */
const POI_ORDER: { key: string; label: string }[] = [
  { key: 'grocery', label: 'продуктовые магазины' },
  { key: 'pharmacy', label: 'аптеки' },
  { key: 'primary_care', label: 'первичная медицина' },
  { key: 'school', label: 'школы' },
  { key: 'kindergarten', label: 'детские сады' },
  { key: 'transport_stop', label: 'остановки транспорта' },
  { key: 'admin_service', label: 'административные услуги' },
  { key: 'emergency', label: 'экстренные службы' },
];

const M = { top: 30, right: 16, bottom: 30, left: 16 };
const ROW_H = 5;

function groupOf(c: StoryCity): Group {
  const p = c.main?.pgr;
  if (p == null) return 'unknown';
  if (p < -0.001) return 'declining';
  if (p > 0.001) return 'growing';
  return 'stable';
}

function median(xs: number[]): number | null {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

function niceTicks(max: number, n = 5): number[] {
  if (max <= 0) return [0];
  const raw = max / n;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((k) => k * mag).find((s) => max / s <= n) ?? 10 * mag;
  const t: number[] = [];
  for (let v = 0; v <= max * 1.0001; v += step) t.push(Math.round(v * 1000) / 1000);
  return t;
}

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const on = () => setReduced(mq.matches);
    on();
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);
  return reduced;
}

export default function RoadsNow({ story, selected, onSelect }: Props) {
  const t = useT();
  const lang = useLang();
  const reduced = usePrefersReducedMotion();

  const [roadClass, setRoadClass] = useState<RoadClass>('all');
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [tip, setTip] = useState<{ x: number; y: number } | null>(null);

  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(380);
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

  const name = (id: string): string => {
    const c = story.cities[id];
    if (!c) return id;
    return lang === 'be' ? c.be || c.ru : c.ru;
  };

  const sel = selected && story.cities[selected] ? selected : null;

  // города панели A/B с данными о дорогах (класс C - только карточка,
  // в ранжированный дот-плот не входит); производные не зависят от языка
  const base = useMemo(() => {
    return Object.values(story.cities)
      .filter((c) => c.roads?.per1000?.all != null && c.quality !== 'C')
      .map((c) => ({
        id: c.id,
        group: groupOf(c),
        pop: c.popNow,
        all: c.roads.per1000.all as number,
        major: c.roads.per1000.major,
        local: c.roads.per1000.local,
      }));
  }, [story]);

  // строки текущего класса, отсортированные по значению (по убыванию)
  const rows = useMemo(() => {
    return base
      .map((r) => ({ ...r, value: r[roadClass] }))
      .filter((r): r is typeof r & { value: number } => r.value != null)
      .sort((a, b) => b.value - a.value);
  }, [base, roadClass]);

  const medDecl = useMemo(
    () => median(rows.filter((r) => r.group === 'declining').map((r) => r.value)),
    [rows],
  );
  const medGrow = useMemo(
    () => median(rows.filter((r) => r.group === 'growing').map((r) => r.value)),
    [rows],
  );

  // медианы POI по всем городам (не зависят от выбранного класса)
  const poiMed = useMemo(() => {
    const out: Record<string, number | null> = {};
    for (const { key } of POI_ORDER) {
      const vals: number[] = [];
      for (const c of Object.values(story.cities)) {
        const v = c.poi?.[key]?.per10k;
        if (v != null) vals.push(v);
      }
      out[key] = median(vals);
    }
    return out;
  }, [story]);

  const nCities = rows.length;
  const groupCounts = useMemo(() => {
    const g: Record<Group, number> = { declining: 0, growing: 0, stable: 0, unknown: 0 };
    for (const r of rows) g[r.group] += 1;
    return g;
  }, [rows]);

  // геометрия дот-плота
  const plotLeft = M.left;
  const plotRight = width - M.right;
  const plotW = Math.max(1, plotRight - plotLeft);
  const plotTop = M.top;
  const plotBottom = plotTop + nCities * ROW_H;
  const height = plotBottom + M.bottom;

  const maxV = Math.max(...rows.map((r) => r.value), 0.001) * 1.06;
  const X = (v: number) => plotLeft + (v / maxV) * plotW;
  const rowY = (i: number) => plotTop + i * ROW_H + ROW_H / 2;
  const idxById = useMemo(() => {
    const m = new Map<string, number>();
    rows.forEach((r, i) => m.set(r.id, i));
    return m;
  }, [rows]);

  const caseIds = useMemo(() => new Set(story.cases.map((c) => c.city_id)), [story]);
  // подписываем: топ-3, низ-3, кейсы, выбранный
  const labeledIds = useMemo(() => {
    const s = new Set<string>();
    rows.slice(0, 3).forEach((r) => s.add(r.id));
    rows.slice(-3).forEach((r) => s.add(r.id));
    caseIds.forEach((id) => idxById.has(id) && s.add(id));
    if (sel && idxById.has(sel)) s.add(sel);
    return s;
  }, [rows, caseIds, idxById, sel]);

  // разводим подписи по вертикали, чтобы не наезжали
  const labels = useMemo(() => {
    const items = rows
      .map((r, i) => ({ id: r.id, value: r.value, group: r.group, i, y: rowY(i) }))
      .filter((x) => labeledIds.has(x.id))
      .sort((a, b) => a.y - b.y)
      .map((x) => ({ ...x, ly: x.y }));
    const gap = 12;
    for (let k = 1; k < items.length; k++) {
      if (items[k].ly < items[k - 1].ly + gap) items[k].ly = items[k - 1].ly + gap;
    }
    if (items.length) {
      const overflow = items[items.length - 1].ly - (plotBottom - 2);
      if (overflow > 0) {
        for (const it of items) it.ly -= overflow;
        for (let k = items.length - 2; k >= 0; k--) {
          if (items[k].ly > items[k + 1].ly - gap) items[k].ly = items[k + 1].ly - gap;
        }
      }
    }
    return items;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, labeledIds, plotBottom, maxV, width]);

  const xTicks = useMemo(() => niceTicks(maxV), [maxV]);

  // --- взаимодействие мышью по строкам ---
  const rowAt = (clientY: number, rect: DOMRect): number => {
    const py = clientY - rect.top;
    return Math.floor((py - plotTop) / ROW_H);
  };
  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const idx = rowAt(e.clientY, rect);
    if (idx < 0 || idx >= nCities) {
      setHoverId(null);
      setTip(null);
      return;
    }
    setHoverId(rows[idx].id);
    setTip({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };
  const onLeave = () => {
    setHoverId(null);
    setTip(null);
  };
  const onClick = (e: React.PointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const idx = rowAt(e.clientY, rect);
    if (idx >= 0 && idx < nCities) onSelect(rows[idx].id);
  };

  const activeId = hoverId ?? sel;
  const activeRow = activeId ? rows.find((r) => r.id === activeId) : null;

  const classLabel = t(CLASS_LABEL[roadClass]);
  const ariaLabel =
    `${t('Точечный график')}: ${nCities} ${t('городов')}, ` +
    `${t('км дорог на 1000 жителей')} (${classLabel}). ` +
    `${t('сокращающиеся')}: ${groupCounts.declining}` +
    (medDecl != null ? `, ${t('медиана')} ${fmtNum(medDecl, 1)}` : '') + '. ' +
    `${t('растущие')}: ${groupCounts.growing}` +
    (medGrow != null ? `, ${t('медиана')} ${fmtNum(medGrow, 1)}` : '') + '. ' +
    `${t('стабильные')}: ${groupCounts.stable}. ` +
    (rows.length
      ? `${t('Значения от')} ${fmtNum(rows[rows.length - 1].value, 1)} ${t('до')} ${fmtNum(rows[0].value, 1)} ${t('км/1000 жит.')}`
      : '');

  const dotTransition = reduced ? 'none' : 'r .12s ease, opacity .12s ease';

  const selCity = sel ? story.cities[sel] : null;

  return (
    <div className="chart-block">
      {/* переключатель класса дорог */}
      <div className="urban-controls">
        <span className="seg-label" id="roadclass-lbl">{t('Класс дорог')}</span>
        <div className="seg urban-seg" role="group" aria-labelledby="roadclass-lbl">
          {CLASS_KEYS.map((k) => (
            <button
              key={k}
              type="button"
              className={roadClass === k ? 'on' : ''}
              aria-pressed={roadClass === k}
              onClick={() => setRoadClass(k)}
            >
              {t(CLASS_LABEL[k])}
            </button>
          ))}
        </div>
      </div>

      {/* дот-плот */}
      <div className="chart-svg-wrap" ref={wrapRef}>
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={ariaLabel}
          style={{ touchAction: 'pan-y', cursor: 'pointer' }}
          onPointerMove={onMove}
          onPointerLeave={onLeave}
          onClick={onClick}
        >
          {/* сетка + ось значений */}
          {xTicks.map((tk) => (
            <g key={tk}>
              <line x1={X(tk)} x2={X(tk)} y1={plotTop} y2={plotBottom} stroke="var(--grid)" strokeWidth="1" />
              <text x={X(tk)} y={plotBottom + 14} textAnchor="middle" fontSize="10" fill="var(--muted)"
                style={{ fontVariantNumeric: 'tabular-nums' }}>
                {fmtNum(tk, Number.isInteger(tk) ? 0 : 1)}
              </text>
            </g>
          ))}
          <text x={(plotLeft + plotRight) / 2} y={height - 2} textAnchor="middle" fontSize="10.5" fill="var(--muted)">
            {t('км дорог на 1000 жителей')}
          </text>

          {/* подсветка активной строки */}
          {activeRow && idxById.has(activeRow.id) && (
            <rect x={plotLeft} y={rowY(idxById.get(activeRow.id)!) - ROW_H / 2} width={plotW} height={ROW_H}
              fill="var(--surface-2)" opacity="0.9" />
          )}

          {/* медианы групп (пунктир) */}
          {medDecl != null && (
            <g>
              <line x1={X(medDecl)} x2={X(medDecl)} y1={plotTop - 6} y2={plotBottom}
                stroke="var(--accent-2)" strokeWidth="1.4" strokeDasharray="4 3" />
              <text x={X(medDecl)} y={plotTop - 18} textAnchor="middle" fontSize="10" fill="var(--accent-2)"
                style={{ fontVariantNumeric: 'tabular-nums', paintOrder: 'stroke' }}
                stroke="var(--surface-1)" strokeWidth="3">
                {t('медиана сокр.')} {fmtNum(medDecl, 1)}
              </text>
            </g>
          )}
          {medGrow != null && (
            <g>
              <line x1={X(medGrow)} x2={X(medGrow)} y1={plotTop - 6} y2={plotBottom}
                stroke="var(--accent)" strokeWidth="1.4" strokeDasharray="4 3" />
              <text x={X(medGrow)} y={plotTop - 6} textAnchor="middle" fontSize="10" fill="var(--accent)"
                style={{ fontVariantNumeric: 'tabular-nums', paintOrder: 'stroke' }}
                stroke="var(--surface-1)" strokeWidth="3">
                {t('медиана раст.')} {fmtNum(medGrow, 1)}
              </text>
            </g>
          )}

          {/* точки-города */}
          {rows.map((r, i) => {
            const isSel = r.id === sel;
            const isHover = r.id === hoverId;
            return (
              <circle
                key={r.id}
                cx={X(r.value)}
                cy={rowY(i)}
                r={isSel ? 3.4 : isHover ? 3 : 2.1}
                fill={GROUP_COLOR[r.group]}
                opacity={r.group === 'stable' || r.group === 'unknown' ? 0.75 : 0.92}
                stroke={isSel ? 'var(--ink)' : isHover ? 'var(--ink)' : 'none'}
                strokeWidth={isSel ? 1.5 : isHover ? 1 : 0}
                style={{ transition: dotTransition }}
              />
            );
          })}

          {/* подписи топ-3 / низ-3 / кейсов / выбранного */}
          {labels.map((lb) => {
            const cx = X(lb.value);
            const cy = rowY(lb.i);
            const right = cx < plotLeft + plotW * 0.5;
            const lx = right ? cx + 6 : cx - 6;
            const anchor = right ? 'start' : 'end';
            const isSel = lb.id === sel;
            return (
              <g key={`lb-${lb.id}`}>
                <line x1={cx} y1={cy} x2={lx} y2={lb.ly} stroke="var(--baseline)" strokeWidth="0.8" />
                <text
                  x={lx + (right ? 2 : -2)}
                  y={lb.ly + 3}
                  textAnchor={anchor}
                  fontSize="10"
                  fontWeight={isSel ? 700 : 400}
                  fill={isSel ? 'var(--ink)' : 'var(--muted)'}
                  style={{ paintOrder: 'stroke' }}
                  stroke="var(--surface-1)"
                  strokeWidth="2.6"
                >
                  {name(lb.id)}
                </text>
              </g>
            );
          })}
        </svg>

        {/* тултип */}
        {activeRow && tip && (
          <div
            className="chart-tooltip"
            style={{ left: Math.min(Math.max(tip.x + 12, 4), width - 168), top: Math.max(tip.y - 8, 4) }}
          >
            <div className="ct-year">{name(activeRow.id)}</div>
            <div className="ct-row">
              <span className="ct-key" style={{ borderTopColor: GROUP_COLOR[activeRow.group] }} />
              <span className="ct-val">{fmtNum(activeRow.value, 2)}</span>
              <span className="ct-name">{t('км/1000 жит.')}</span>
            </div>
            <div className="ct-row">
              <span className="ct-val">{fmtNum(activeRow.pop, 0)}</span>
              <span className="ct-name">{t('текущее население')}</span>
            </div>
            <div className="ct-row">
              <span className="ct-name">{t(GROUP_LABEL[activeRow.group])}</span>
            </div>
          </div>
        )}
      </div>

      {/* легенда */}
      <div className="urban-legend" aria-hidden="true">
        <span className="lg-title" style={{ color: 'var(--muted)' }}>{t('Динамика населения 1990–2020:')}</span>
        {(['declining', 'growing', 'stable'] as Group[]).map((g) => (
          <span className="lg" key={g}>
            <span className="sw" style={{ background: GROUP_COLOR[g], borderRadius: '50%' }} />
            {t(GROUP_LABEL[g])}
          </span>
        ))}
        <span className="lg">
          <span aria-hidden="true" style={{ display: 'inline-block', width: 14, borderTop: '1.4px dashed var(--muted)' }} />
          {t('медианы групп (пунктир)')}
        </span>
      </div>
      <p className="hint">
        {t('Каждая строка — город; по горизонтали — км улично-дорожной сети выбранного класса на 1000 текущих жителей. Города отсортированы по значению; подписаны только крайние, ключевые кейсы и выбранный. Клик выбирает город.')}
      </p>

      {/* дисклеймеры OSM */}
      <p className="hint">
        <span className="urban-badge">{t('снимок OSM · июль 2026')}</span>{' '}
        {t('Срез OSM на июль 2026 — современная география, не история строительства.')}
      </p>

      {/* блок POI выбранного города */}
      {selCity ? (
        <div className="chart-block">
          <h3 className="poi-head" style={{ fontSize: 15, margin: '10px 0 4px' }}>
            {t('Сервисы и точки OSM')}: {name(selCity.id)}
            {selCity.popNow != null && (
              <span className="hint" style={{ marginLeft: 8, fontWeight: 400 }}>
                {t('текущее население')} — {fmtNum(selCity.popNow, 0)}
              </span>
            )}
          </h3>
          <div className="zone-table-wrap">
            <table className="zone-table">
              <thead>
                <tr>
                  <th scope="col">{t('Категория')}</th>
                  <th scope="col">{t('Точек OSM')}</th>
                  <th scope="col">{t('На 10 тыс. жителей')}</th>
                  <th scope="col">{t('Медиана по городам')}</th>
                </tr>
              </thead>
              <tbody>
                {POI_ORDER.map(({ key, label }) => {
                  const cell = selCity.poi?.[key];
                  const per = cell?.per10k ?? null;
                  const med = poiMed[key] ?? null;
                  const below = per != null && med != null && per < med;
                  return (
                    <tr key={key}>
                      <th scope="row" style={{ fontWeight: 400 }}>{t(label)}</th>
                      <td style={{ fontVariantNumeric: 'tabular-nums' }}>{fmtNum(cell?.count ?? null, 0)}</td>
                      <td style={{ fontVariantNumeric: 'tabular-nums' }}>
                        {fmtNum(per, 2)}
                        {below && (
                          <span aria-hidden="true" title={t('ниже медианы')} style={{ marginLeft: 4, color: 'var(--muted)' }}>▼</span>
                        )}
                      </td>
                      <td style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--muted)' }}>{fmtNum(med, 2)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="hint">{t('▼ — значение ниже медианы по всем городам. «На 10 тыс. жителей» — точки OSM, делённые на текущее население; счётчик описательный.')}</p>
        </div>
      ) : (
        <p className="hint">{t('Выберите город на графике, чтобы увидеть его дороги и точки сервисов OSM.')}</p>
      )}

      <p className="hint">
        <span className="urban-badge">OSM</span>{' '}
        {t('Полнота OSM неоднородна: отсутствие точки не означает отсутствия сервиса; счётчики описательные, не сверены с официальными реестрами.')}
      </p>

      {/* текстовый фолбэк */}
      <details className="urban-fallback">
        <summary>{t('Таблица: км дорог на 1000 жителей по классам')}</summary>
        <div className="zone-table-wrap">
          <table className="zone-table">
            <thead>
              <tr>
                <th scope="col">{t('Город')}</th>
                <th scope="col">{t('Все')}</th>
                <th scope="col">{t('Магистральные')}</th>
                <th scope="col">{t('Локальные')}</th>
                <th scope="col">{t('Динамика 1990–2020')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className={r.id === sel ? 'sel' : undefined}>
                  <th scope="row" style={{ fontWeight: 400 }}>
                    <button
                      type="button"
                      className="linkish"
                      aria-pressed={r.id === sel}
                      onClick={() => onSelect(r.id)}
                      onFocus={() => setHoverId(r.id)}
                      onBlur={() => setHoverId(null)}
                      style={{ background: 'none', border: 'none', padding: 0, color: 'inherit', cursor: 'pointer', font: 'inherit', textAlign: 'left' }}
                    >
                      {name(r.id)}
                    </button>
                  </th>
                  <td style={{ fontVariantNumeric: 'tabular-nums' }}>{fmtNum(r.all, 1)}</td>
                  <td style={{ fontVariantNumeric: 'tabular-nums' }}>{fmtNum(r.major, 1)}</td>
                  <td style={{ fontVariantNumeric: 'tabular-nums' }}>{fmtNum(r.local, 1)}</td>
                  <td style={{ color: GROUP_COLOR[r.group] }}>{t(GROUP_LABEL[r.group])}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
