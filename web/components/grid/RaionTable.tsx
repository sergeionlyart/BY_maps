'use client';

import { useMemo, useState } from 'react';
import type { GridData } from '@/lib/grid';
import type { GridStoryData } from '@/lib/gridStory';
import { useT } from '@/lib/i18n';

type SortKey = 'name' | 'change' | 'roadPerCapita' | 'emptyShare';

interface Row {
  id: string;
  name: string;
  change_pct: number | null;
  road_km_per_1000: number | null;
  empty_share_2020: number | null;
}

/** Таблица всех 118 районов + Минска (INF-15 v3, доработка "готовый
 *  копирайтинг раздела", раздел 5.3 п.3) - прямой ответ на "а что у моего
 *  района", отсортировать/скачать CSV. Числа - те же источники, что и
 *  остальная карта (grid.json + grid_story.json), не отдельный расчёт. */
export default function RaionTable({ data, story, lang }: { data: GridData; story: GridStoryData | null; lang: 'ru' | 'be' }) {
  const t = useT();
  const [sortKey, setSortKey] = useState<SortKey>('change');
  const [sortDir, setSortDir] = useState<1 | -1>(1);
  const [open, setOpen] = useState(false);

  const rows: Row[] = useMemo(() => {
    if (!story) return [];
    const names = story.raions.by_id;
    return Object.entries(data.territories).map(([id, tv]) => {
      const nm = names[id];
      const p75 = tv.pop_grid_sum['1975'];
      const p20 = tv.pop_grid_sum['2020'];
      const change_pct = p75 && p20 ? ((p20 - p75) / p75) * 100 : null;
      return {
        id,
        name: nm ? (lang === 'be' ? nm.name_be : nm.name_ru) : id,
        change_pct,
        road_km_per_1000: tv.network_per_capita?.road_km_per_1000 ?? null,
        empty_share_2020: tv.area_share_below['5']['2020'] ?? null,
      };
    });
  }, [data, story, lang]);

  const sorted = useMemo(() => {
    const withVal = (r: Row): number | string => {
      if (sortKey === 'name') return r.name;
      if (sortKey === 'change') return r.change_pct ?? Infinity;
      if (sortKey === 'roadPerCapita') return r.road_km_per_1000 ?? -Infinity;
      return r.empty_share_2020 ?? -Infinity;
    };
    return [...rows].sort((a, b) => {
      const va = withVal(a), vb = withVal(b);
      if (typeof va === 'string' || typeof vb === 'string') {
        return String(va).localeCompare(String(vb), lang === 'be' ? 'be' : 'ru') * sortDir;
      }
      return (va - vb) * sortDir;
    });
  }, [rows, sortKey, sortDir, lang]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) { setSortDir((d) => (d === 1 ? -1 : 1)); return; }
    setSortKey(key);
    setSortDir(key === 'name' ? 1 : -1);
  }

  function exportCsv() {
    const header = ['id', 'name', 'change_pct_1975_2020', 'road_km_per_1000', 'empty_share_2020'];
    const lines = [header.join(',')];
    for (const r of sorted) {
      lines.push([
        r.id, `"${r.name.replace(/"/g, '""')}"`,
        r.change_pct != null ? r.change_pct.toFixed(2) : '',
        r.road_km_per_1000 != null ? r.road_km_per_1000.toFixed(2) : '',
        r.empty_share_2020 != null ? (r.empty_share_2020 * 100).toFixed(2) : '',
      ].join(','));
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'grid_raions.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  if (!story) return null;

  return (
    <div className="gv-raion-table-wrap">
      <button className="btn gv-raion-table-toggle" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        {open ? t('Скрыть таблицу районов') : t('Показать таблицу всех районов')}
      </button>
      {open && (
        <>
          <div className="gv-raion-table-scroll">
            <table className="gv-raion-table">
              <thead>
                <tr>
                  <th><button onClick={() => toggleSort('name')}>{t('район')}</button></th>
                  <th><button onClick={() => toggleSort('change')}>{t('изменение 1975→2020, %')}</button></th>
                  <th><button onClick={() => toggleSort('roadPerCapita')}>{t('км дороги / 1000 жит.')}</button></th>
                  <th><button onClick={() => toggleSort('emptyShare')}>{t('доля пустой территории, 2020')}</button></th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((r) => (
                  <tr key={r.id}>
                    <td>{r.name}</td>
                    <td className={r.change_pct != null && r.change_pct < 0 ? 'gv-trend-down' : 'gv-trend-up'}>
                      {r.change_pct != null ? `${r.change_pct > 0 ? '+' : ''}${r.change_pct.toFixed(1)}` : '—'}
                    </td>
                    <td>{r.road_km_per_1000 != null ? r.road_km_per_1000.toFixed(1) : '—'}</td>
                    <td>{r.empty_share_2020 != null ? `${(r.empty_share_2020 * 100).toFixed(0)}%` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button className="btn gv-raion-table-csv" onClick={exportCsv}>{t('Скачать CSV')}</button>
        </>
      )}
    </div>
  );
}
