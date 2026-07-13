'use client';

import type { DataFile } from '@/lib/types';
import type { ForecastFile, ScenarioId } from '@/lib/forecast';
import { SCENARIO_LABEL } from '@/lib/forecast';
import { formatPct, valueAt } from '@/lib/series';
import { CAT } from '@/lib/scales';
import { useT } from '@/lib/i18n';
import LineChart, { ChartSeries } from './LineChart';

interface Props {
  data: DataFile;
  year: number;
  forecast?: ForecastFile | null;
  scenario?: ScenarioId;
}

const TOP7 = ['c-minsk', 'c-homiel', 'c-mahilou', 'c-viciebsk', 'c-hrodna', 'c-brest', 'c-babrujsk'];
const OBL_CENTERS = ['c-minsk', 'c-homiel', 'c-mahilou', 'c-viciebsk', 'c-hrodna', 'c-brest'];

/** Панель урбанизации и концентрации населения (по стране). */
export default function UrbanPanel({ data, year, forecast, scenario = 'base' }: Props) {
  const t = useT();
  const byPop = data.territories['BY'].pop;
  // знаменатель: население страны в современных границах; для годов без
  // прямой оценки (1923, 1926, 1939) - линейная интерполяция
  const rows = data.panel
    .map((r) => ({ ...r, pop: r.pop ?? valueAt(byPop, r.year)?.value ?? null }))
    .filter((r) => r.pop);

  // прогнозный слой (этап 5): городское население = сумма прогнозов городов
  // (покрытие полное: города проекта = городское население официального ряда)
  const fterrs = forecast?.territories;
  const fyears = fterrs?.['BY']?.[scenario]?.years ?? [];
  const fshare = (ids: 'all' | string[]) => {
    if (!fterrs) return [];
    const cityIds = ids === 'all'
      ? Object.keys(fterrs).filter((t) => t.startsWith('c-'))
      : ids;
    return fyears.map((y, i) => {
      const num = cityIds.reduce((s, t) => s + (fterrs[t]?.[scenario]?.pop[i] ?? 0), 0);
      return { year: y, value: (num / fterrs['BY'][scenario].pop[i]) * 100, major: false };
    }).filter((p) => p.year > 2026);
  };

  const mk = (key: 'urban' | 'minsk' | 'oblCenters' | 'top7', name: string, color: string,
              fids: 'all' | string[]): ChartSeries => ({
    name,
    color,
    points: [
      ...rows
        .filter((r) => r[key] != null)
        .map((r) => ({ year: r.year, value: (r[key]! / r.pop!) * 100, major: true })),
      ...fshare(fids),
    ],
  });

  const series: ChartSeries[] = [
    mk('urban', t('Городское население'), 'var(--viz-urban)', 'all'),
    mk('top7', t('7 крупнейших городов'), CAT[2], TOP7),
    mk('oblCenters', t('Минск + обл. центры'), CAT[3], OBL_CENTERS),
    mk('minsk', t('Минск'), CAT[0], ['c-minsk']),
  ];

  const last = rows[rows.length - 1];
  const nearest = rows.reduce((a, b) => (Math.abs(b.year - year) < Math.abs(a.year - year) ? b : a), rows[0]);

  return (
    <div>
      <div className="stat-row">
        <div className="stat-tile">
          <div className="st-label">{t('Доля городского населения')}, {nearest.year}</div>
          <div className="st-value">{nearest.urban && nearest.pop ? formatPct(nearest.urban / nearest.pop) : '—'}</div>
          <div className="st-delta">
            {rows[0].urban && rows[0].pop ? `${t('в')} ${rows[0].year} — ${formatPct(rows[0].urban / rows[0].pop)}` : ''}
          </div>
        </div>
        <div className="stat-tile">
          <div className="st-label">{t('Живёт в Минске')}, {nearest.year}</div>
          <div className="st-value">{nearest.minsk && nearest.pop ? formatPct(nearest.minsk / nearest.pop) : '—'}</div>
          <div className="st-delta">
            {rows[0].minsk && rows[0].pop ? `${t('в')} ${rows[0].year} — ${formatPct(rows[0].minsk / rows[0].pop)}` : ''}
          </div>
        </div>
        <div className="stat-tile">
          <div className="st-label">{t('В 7 крупнейших городах')}, {nearest.year}</div>
          <div className="st-value">{nearest.top7 && nearest.pop ? formatPct(nearest.top7 / nearest.pop) : '—'}</div>
          <div className="st-delta">
            {rows[0].top7 && rows[0].pop ? `${t('в')} ${rows[0].year} — ${formatPct(rows[0].top7 / rows[0].pop)}` : ''}
          </div>
        </div>
      </div>

      <div className="chart-block">
        <div className="chart-title">
          {t('Доля в населении страны, % (по переписным годам')}
          {forecast ? `${t('; за 2026 — прогноз')} ${forecast.version}${t(', сценарий «')}${t(SCENARIO_LABEL[scenario])}»` : ''})
        </div>
        <LineChart
          series={series}
          height={240}
          markYear={year}
          yFormat={(v) => v + '%'}
          yTooltip={(v) => v.toLocaleString('ru-RU', { maximumFractionDigits: 1 }) + '%'}
          yMax={85}
          domain={[1897, forecast ? 2075 : 2026]}
          refXs={forecast ? [{ value: 2026, label: t('прогноз →') }] : undefined}
        />
      </div>

      <p className="src-note">
        {t('Доли считаются к населению страны в современных границах; для 1923–1939 годов знаменатель интерполирован между ретроспективными оценками (1913, 1940). Городское население до 1959 года — сумма городских НП из таблицы переписей; топ-7: Минск, Гомель, Могилёв, Витебск, Гродно, Брест, Бобруйск (современный состав, фиксированный во времени).')}
        {forecast ? t(' Прогнозная часть — сумма городских прогнозов этапа 5 (199 городов; гп с рядами, оборванными до 2019 г., не прогнозируются).') : ''}
      </p>
      <p className="src-note">
        <a href="/research/zipf">{t('→ Исследование INF-01: иерархия городов и закон Ципфа, 1897–2026')}</a> {t('— почему Минск в 4 раза больше Гомеля при «ципфовском» ожидании 2×.')}
      </p>
    </div>
  );
}
