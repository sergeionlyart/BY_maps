'use client';

/** Карточка района (ТЗ §3): SR сейчас/2036/2046/2056, год перехода по трём
 *  порогам (интервал вместо даты, если у района активен crossing_interval —
 *  гейт G-3 не пройден на районном уровне), условная денежная арифметика
 *  (или явная причина, почему скрыта — запрещённое слово из ТЗ §Абсолютное
 *  правило сюда никогда не попадает), веер
 *  трёх сценариев SR и «пенсионный крест». */

import { useT } from '@/lib/i18n';
import type { PensionFile, PolicyId, ScenarioId, JumpoffId, TerritoryEntry, ThresholdKey } from '@/lib/pension';
import { THRESHOLDS, THRESHOLD_LABEL, valueAt, crossingDisplay, seriesKey as mkSeriesKey } from '@/lib/pension';
import { SCENARIO_STYLE, SCENARIO_LABEL } from '@/lib/forecast';
import LineChart from '@/components/LineChart';

const CARD_YEARS = [2036, 2046, 2056];

export default function TerritoryPanel({
  pf,
  id,
  entry,
  name,
  oblastName,
  scenario,
  jumpoff,
  policy,
  year,
}: {
  pf: PensionFile;
  id: string;
  entry: TerritoryEntry;
  name: string;
  oblastName: string;
  scenario: ScenarioId;
  jumpoff: JumpoffId;
  policy: PolicyId;
  year: number;
}) {
  const t = useT();
  const key = mkSeriesKey(scenario, jumpoff);
  const years = pf.years.territory;

  const srNow = valueAt(entry.sr, years, policy, key, year);
  const cardSr = CARD_YEARS.map((y) => ({ y, v: valueAt(entry.sr, years, policy, key, y) }));

  const cgYear = String(year);
  const cgVal = entry.cg?.[key]?.[cgYear] ?? null;

  const fanSeries = (['optimistic', 'base', 'negative'] as ScenarioId[]).map((s) => ({
    name: t(SCENARIO_LABEL[s]),
    color: SCENARIO_STYLE[s].color,
    dash: SCENARIO_STYLE[s].dash,
    points: years.map((y) => {
      const v = valueAt(entry.sr, years, policy, mkSeriesKey(s, jumpoff), y);
      return v == null ? null : { year: y, value: v, major: pf.dtype.territory[String(y)] !== 'f' };
    }).filter((p): p is { year: number; value: number; major: boolean } => p != null),
  }));

  // «пенсионный крест»: сырых численностей по возрастным группам района на
  // клиенте нет (только областной/национальный разрез выгружен наружу —
  // docs/decisions/INF-13.md, запись «пенсионный крест: индекс вместо
  // абсолютных численностей»), поэтому строим индекс на 100 человек старше
  // трудоспособного возраста: «пожилые» = опорная линия 100, «работающие» =
  // 100×SR(t). Пересечение линий математически тождественно пересечению
  // порога SR=1 (работающих столько же, сколько пожилых).
  const crossPts = years.map((y) => {
    const v = valueAt(entry.sr, years, policy, key, y);
    return v == null ? null : { year: y, value: Math.round(v * 100), major: pf.dtype.territory[String(y)] !== 'f' };
  }).filter((p): p is { year: number; value: number; major: boolean } => p != null);
  const crossRef = years.map((y) => ({ year: y, value: 100 }));
  const cross1 = crossingDisplay(entry, policy, key, '1.0');

  return (
    <div>
      <div className="terr-title">{name}</div>
      <div className="terr-sub">{oblastName}</div>

      <div className="stat-row">
        <div className="stat-tile">
          <div className="st-label">{t('SR сейчас')} ({year})</div>
          <div className="st-value">{srNow != null ? srNow.toFixed(2) : '—'}</div>
        </div>
        {cardSr.map(({ y, v }) => (
          <div className="stat-tile" key={y}>
            <div className="st-label">SR {y}</div>
            <div className="st-value">{v != null ? v.toFixed(2) : '—'}</div>
          </div>
        ))}
      </div>

      <div className="chart-block">
        <div className="chart-title">{t('Год перехода порогов')}</div>
        <div className="stat-row">
          {THRESHOLDS.map((th) => (
            <CrossingTile key={th} th={th} entry={entry} policy={policy} skey={key} />
          ))}
        </div>
      </div>

      <div className="prob-panel">
        <div className="prob-head">{t('Условная денежная арифметика (CG)')}</div>
        {entry.cg_suppressed ? (
          <div className="prob-note">
            {t('Не показывается: район в пределах 45 минут эффективной доступности до Минска — маятниковая миграция искажает базу взносов, количественная поправка недоступна (проверка G-7). Это не реальные доходы или расходы района.')}
          </div>
        ) : cgVal != null ? (
          <>
            <div className="prob-rows"><span><b>{cgVal.toFixed(2)}</b> {t('(1,00 — взносы работающих района равны условной потребности его пожилых)')}</span></div>
            <div className="prob-note">
              {t('Условный сравнительный индекс, не реальные доходы или расходы района: общереспубликанский пенсионный фонд по районам не делится. При текущем экономическом масштабе района CG пропорционален SR — это тот же демографический ряд, пересчитанный в условные деньги, а не независимое подтверждение тренда.')}
            </div>
          </>
        ) : (
          <div className="prob-note">{t('Не рассчитывается для факта до 2026 года — денежный слой использует текущие занятость и зарплату района.')}</div>
        )}
      </div>

      <div className="chart-block">
        <div className="chart-title">{t('Веер трёх сценариев, SR')}</div>
        <LineChart
          series={fanSeries}
          domain={[years[0], years[years.length - 1]]}
          markYear={year}
          yFormat={(v) => v.toFixed(1)}
          refY={{ value: 1.5, label: t('порог 1,5') }}
        />
      </div>

      <div className="chart-block">
        <div className="chart-title">{t('«Пенсионный крест»: работающие и пожилые')}</div>
        <LineChart
          series={[
            { name: t('работающие (индекс на 100 пожилых)'), color: 'var(--accent)', points: crossPts },
            { name: t('пожилые (опорная линия = 100)'), color: 'var(--muted)', dash: '4 3', points: crossRef },
          ]}
          domain={[years[0], years[years.length - 1]]}
          markYear={year}
          yFormat={(v) => v.toFixed(0)}
        />
        <p className="hint" style={{ marginTop: 6 }}>
          {t('Индекс на 100 человек старше трудоспособного возраста района (не абсолютная численность: районный разрез по отдельным возрастным группам на клиенте недоступен). Пересечение линий тождественно году, когда работающих становится столько же, сколько пожилых —')}{' '}
          {cross1.kind === 'year' ? cross1.value : cross1.kind === 'interval' ? t(cross1.value) : t('не наступает до 2056 года')}.
        </p>
      </div>
    </div>
  );
}

function CrossingTile({ th, entry, policy, skey }: {
  th: ThresholdKey;
  entry: TerritoryEntry;
  policy: PolicyId;
  skey: `${ScenarioId}:${JumpoffId}`;
}) {
  const t = useT();
  const c = crossingDisplay(entry, policy, skey, th);
  return (
    <div className="stat-tile" data-threshold={th}>
      <div className="st-label">{t(THRESHOLD_LABEL[th])}</div>
      <div className="st-value pen-crossing-value" data-kind={c.kind} style={{ fontSize: c.kind === 'interval' ? 13.5 : 17 }}>
        {c.kind === 'year' ? c.value : c.kind === 'interval' ? t(c.value) : t('не наступает до 2056')}
      </div>
    </div>
  );
}
