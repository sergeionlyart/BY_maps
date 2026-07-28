'use client';

/** Мини-график под картой (INF-15 v3, доработка "готовый копирайтинг и
 *  доработка демонстрационной карты", раздел 5.1 п.6) - горизонтальные
 *  столбики для шагов 2-5 режима «История». Числа читаются из тех же
 *  данных, что и текст шага (ни одного литерала здесь), знак - цветом
 *  --pos/--neg (та же палитра, что и тренд-стрелки свободного режима). */
export interface MiniChartRow {
  label: string;
  value: number; // проценты, со знаком
  highlight?: boolean;
}

export default function MiniChart({ rows, unit = '%' }: { rows: MiniChartRow[]; unit?: string }) {
  const max = Math.max(1, ...rows.map((r) => Math.abs(r.value)));
  return (
    <div className="gv-minichart" role="img" aria-label="Мини-график изменения по группам">
      {rows.map((r) => {
        const widthPct = (Math.abs(r.value) / max) * 100;
        const sign = r.value > 0 ? '+' : '';
        return (
          <div key={r.label} className={`gv-minichart-row${r.highlight ? ' highlight' : ''}`}>
            <span className="gv-minichart-label">{r.label}</span>
            <span className="gv-minichart-track">
              <span
                className={`gv-minichart-bar ${r.value >= 0 ? 'pos' : 'neg'}`}
                style={{ width: `${widthPct}%` }}
              />
            </span>
            <span className="gv-minichart-value">{sign}{r.value.toFixed(1)}{unit}</span>
          </div>
        );
      })}
    </div>
  );
}
