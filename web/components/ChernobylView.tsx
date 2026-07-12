'use client';

import { useEffect, useMemo, useState } from 'react';
import type { DataFile, Territory } from '@/lib/types';
import { seriesPoints } from '@/lib/series';
import { CAT } from '@/lib/scales';
import LineChart, { ChartSeries } from './LineChart';
import MethodDrawer from './MethodDrawer';

interface Pair {
  id: string;
  ru: string;
  klass: 1 | 2;
  control: string;
  controlRu: string;
  pop1979: number;
  controlPop1979: number;
  closedHa: number | null;
  np2021: Record<string, number>;
  np2016: Record<string, number>;
}

interface CherData {
  version: string;
  baseYear: number;
  npa: { current: string; y2016: string };
  events: { year: number; label: string }[];
  classLabels: Record<string, string>;
  borderline: Record<string, string>;
  pairs: Pair[];
}

const AFF_COLOR = '#d03b3b'; // красная ветвь дивергентной шкалы проекта

/** Индекс населения: base=100 в базовом году. */
function indexSeries(t: Territory, baseYear: number): ChartSeries['points'] {
  const base = t.pop[String(baseYear)]?.[0];
  if (!base) return [];
  return seriesPoints(t.pop)
    .filter((p) => p.year >= 1970)
    .map((p) => ({ year: p.year, value: (p.value / base) * 100, major: p.dtype === 'c' }));
}

function idx2019(t: Territory, base: number): number | null {
  const v = t.pop['2019']?.[0];
  return v ? (v / base) * 100 : null;
}

export default function ChernobylView() {
  const [cher, setCher] = useState<CherData | null>(null);
  const [data, setData] = useState<DataFile | null>(null);
  const [sel, setSel] = useState<string>(() => {
    if (typeof window === 'undefined') return 'r-chojnicki';
    return new URLSearchParams(window.location.search).get('sel') ?? 'r-chojnicki';
  });

  useEffect(() => {
    fetch('/data/chernobyl.json').then((r) => r.json()).then(setCher);
    fetch('/data/data.json').then((r) => r.json()).then(setData);
  }, []);

  const pair = useMemo(() => {
    if (!cher) return null;
    return cher.pairs.find((p) => p.id === sel) ?? cher.pairs[0];
  }, [cher, sel]);

  if (!cher || !data || !pair) return <p className="hint">Загрузка данных…</p>;

  const t = data.territories;
  const chart: ChartSeries[] = [
    { name: `${pair.ru} (класс ${pair.klass})`, color: AFF_COLOR, points: indexSeries(t[pair.id], cher.baseYear) },
    { name: `${pair.controlRu} (контроль)`, color: CAT[0], points: indexSeries(t[pair.control], cher.baseYear) },
  ];

  const select = (id: string) => {
    setSel(id);
    const url = new URL(window.location.href);
    url.searchParams.set('sel', id);
    window.history.replaceState(null, '', url);
  };

  const gap = (p: Pair): number | null => {
    const a = idx2019(t[p.id], p.pop1979);
    const c = idx2019(t[p.control], p.controlPop1979);
    return a != null && c != null ? a - c : null;
  };

  const k1 = cher.pairs.filter((p) => p.klass === 1);
  const totalClosedKm2 = Math.round(cher.pairs.reduce((s, p) => s + (p.closedHa ?? 0), 0) / 100);
  const npSum = (np: Record<string, number>) => Object.values(np).reduce((s, v) => s + v, 0);

  return (
    <div>
      <div className="controls" style={{ marginBottom: 6 }}>
        <MethodDrawer slug="chernobyl" />
        <a className="btn" href="/artifacts/by-maps-chernobyl-v1.0.0.zip" download>
          ⬇ Проверяемый пакет (ZIP)
        </a>
      </div>

      <div className="stat-row">
        <div className="stat-tile">
          <div className="st-label">Зона эвакуации/отселения (класс 1)</div>
          <div className="st-value">{k1.map((p) => p.ru.replace(' район', '')).join(', ')}</div>
          <div className="st-delta">эвакуация 1986 г.; ныне — Полесский заповедник</div>
        </div>
        <div className="stat-tile">
          <div className="st-label">Закрытые отселённые территории</div>
          <div className="st-value">{totalClosedKm2.toLocaleString('ru-RU')} км²</div>
          <div className="st-delta">в 12 районах классов 1–2 (КПП-режим, 2022)</div>
        </div>
        <div className="stat-tile">
          <div className="st-label">НП в зонах загрязнения</div>
          <div className="st-value">2193 → 2022</div>
          <div className="st-delta">перечни 2016 и 2021 гг. (зоны сужаются)</div>
        </div>
      </div>

      <div className="chart-block">
        <div className="chart-title">
          Население, индекс: перепись {cher.baseYear} = 100 · {pair.ru} против контроля
          {' · '}
          <a href={`/map?sel=${pair.id}`}>показать на карте</a>
        </div>
        <div className="controls" style={{ margin: '2px 0 6px' }}>
          <select value={pair.id} onChange={(e) => select(e.target.value)} aria-label="пара район-контроль">
            <optgroup label={`Класс 1 — ${cher.classLabels['1']}`}>
              {cher.pairs.filter((p) => p.klass === 1).map((p) => (
                <option key={p.id} value={p.id}>{p.ru} ↔ {p.controlRu}</option>
              ))}
            </optgroup>
            <optgroup label={`Класс 2 — ${cher.classLabels['2']}`}>
              {cher.pairs.filter((p) => p.klass === 2).map((p) => (
                <option key={p.id} value={p.id}>{p.ru} ↔ {p.controlRu}</option>
              ))}
            </optgroup>
          </select>
        </div>
        <LineChart
          series={chart}
          height={300}
          domain={[1970, 2026]}
          yFormat={(v) => String(Math.round(v))}
          yTooltip={(v) => v.toFixed(1) + ' (1979 = 100)'}
          refXs={cher.events.map((e) => ({ value: e.year, label: String(e.year) }))}
          refY={{ value: 100, label: '1979 = 100' }}
        />
        <p className="hint" style={{ marginTop: 4 }}>
          {cher.events.map((e) => `${e.year} — ${e.label}`).join(' · ')}
        </p>
      </div>

      <div className="stat-row">
        <div className="stat-tile">
          <div className="st-label">{pair.ru}: население 2019 к 1979</div>
          <div className="st-value">{idx2019(t[pair.id], pair.pop1979)?.toFixed(0)}%</div>
          <div className="st-delta down">контроль ({pair.controlRu}): {idx2019(t[pair.control], pair.controlPop1979)?.toFixed(0)}%</div>
        </div>
        {pair.closedHa != null && (
          <div className="stat-tile">
            <div className="st-label">Закрытые отселённые территории</div>
            <div className="st-value">{Math.round(pair.closedHa / 100).toLocaleString('ru-RU')} км²</div>
            <div className="st-delta">КПП-режим, 2022 (табл. 12 МЧС)</div>
          </div>
        )}
        <div className="stat-tile">
          <div className="st-label">НП в зонах загрязнения</div>
          <div className="st-value">{npSum(pair.np2016)} → {npSum(pair.np2021)}</div>
          <div className="st-delta">
            перечень-2016 → перечень-2021
            {pair.np2021.POSL ? ` · ${pair.np2021.POSL} НП — зона последующего отселения` : ''}
          </div>
        </div>
      </div>

      <div className="chart-block">
        <div className="chart-title">Все пары: отставание от контроля к 2019 г. (проценты индекса 1979 = 100)</div>
        <div className="zone-table-wrap">
        <table className="zone-table">
          <thead>
            <tr>
              <th>Район</th><th>Класс</th><th>Закрыто, км²</th>
              <th>НП в зонах 2016→2021</th><th>Контроль</th><th>Отставание</th>
            </tr>
          </thead>
          <tbody>
            {cher.pairs.map((p) => {
              const g = gap(p);
              return (
                <tr key={p.id} className={p.id === pair.id ? 'sel' : ''}
                  onClick={() => select(p.id)} style={{ cursor: 'pointer' }}>
                  <td>{p.ru.replace(' район', '')}</td>
                  <td>{p.klass}</td>
                  <td>{p.closedHa != null ? Math.round(p.closedHa / 100) : '—'}</td>
                  <td>{npSum(p.np2016)} → {npSum(p.np2021)}</td>
                  <td>{p.controlRu.replace(' район', '')}</td>
                  <td className={g != null && g < 0 ? 'neg' : 'pos'}>
                    {g != null ? `${g > 0 ? '+' : ''}${g.toFixed(0)} п.п.` : '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        </div>
        <p className="hint" style={{ marginTop: 4 }}>
          Отрицательное отставание — район сократился сильнее контроля.
          Исключения информативны: Добрушский и Костюковичский держались лучше
          контролей за счёт райцентров-городов.
        </p>
      </div>

      <p className="src-note">
        Классификация — по официальным перечням НП в зонах радиоактивного
        загрязнения ({cher.npa.current}; ранее {cher.npa.y2016}) и данным о
        закрытых территориях с контрольно-пропускным режимом (МЧС, «Беларусь
        и Чернобыль: 36 лет», табл. 12). Пограничные случаи вне классов:{' '}
        {Object.entries(cher.borderline).map(([k, v]) => `${k} — ${v}`).join('; ')}.
        Контроль подобран по населению переписи-1979 среди районов вне
        перечней. Полные ограничения — в методблоке и LIMITATIONS.md пакета.
      </p>
    </div>
  );
}
