'use client';

/** Карточка района (ТЗ §3): SR сейчас/2036/2046/2056, год перехода по трём
 *  порогам (интервал вместо даты, если у района активен crossing_interval —
 *  гейт G-3 не пройден на районном уровне), условная денежная арифметика
 *  (или явная причина, почему скрыта — запрещённое слово из ТЗ §Абсолютное
 *  правило сюда никогда не попадает, кроме единственного разрешённого места -
 *  card.cg-note.p2 в слое «Просто», где отрицание «не бюджет района» прямо
 *  требует раздел 9 п.1 нового ТЗ handoff/10_pension_ux_copy), веер
 *  трёх сценариев SR и «пенсионный крест».
 *
 *  INF-13 UX: подписи плиток/блоков и пояснения - из контент-файлов (§7.8),
 *  сама механика (сеть точек, crossingDisplay, CG-состояния) не менялась.
 *  Режим "шторки" на мобильном - в обёртке PensionView, этот компонент
 *  не знает о sheet-механике, просто рендерит содержимое целиком. */

import { useT } from '@/lib/i18n';
import type { PensionFile, PolicyId, ScenarioId, JumpoffId, TerritoryEntry, ThresholdKey } from '@/lib/pension';
import { THRESHOLDS, valueAt, crossingDisplay, seriesKey as mkSeriesKey } from '@/lib/pension';
import { SCENARIO_STYLE, SCENARIO_LABEL } from '@/lib/forecast';
import { ruNum, fillTemplate, type ContentGetter } from '@/lib/pensionContent';
import LineChart from '@/components/LineChart';
import Markdown from '@/components/Markdown';

const CARD_YEARS = [2036, 2046, 2056];
const THRESHOLD_CONTENT_KEY: Record<ThresholdKey, string> = {
  '2.0': 'card.threshold.2_0',
  '1.5': 'card.threshold.1_5',
  '1.0': 'card.threshold.1_0',
};

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
  layer,
  C,
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
  layer: 'simple' | 'pro';
  C: ContentGetter;
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
          <div className="st-label">{C.get('card.sr-now-label')} ({year})</div>
          <div className="st-value">{srNow != null ? ruNum(srNow, 2) : '—'}</div>
        </div>
        {cardSr.map(({ y, v }) => (
          <div className="stat-tile" key={y}>
            <div className="st-label">{fillTemplate(C.get('card.sr-year-label'), { y })}</div>
            <div className="st-value">{v != null ? ruNum(v, 2) : '—'}</div>
          </div>
        ))}
      </div>

      <div className="chart-block">
        <div className="chart-title">{C.get('card.crossing-title')}</div>
        <div className="stat-row">
          {THRESHOLDS.map((th) => (
            <CrossingTile key={th} th={th} entry={entry} policy={policy} skey={key} C={C} />
          ))}
        </div>
        {C.has('card.crossing-note') && <Markdown text={C.get('card.crossing-note')} />}
      </div>

      <div className="prob-panel">
        <div className="prob-head">{C.get('card.cg-title')}</div>
        {entry.cg_suppressed ? (
          <div className="prob-note">{C.get('card.cg-suppressed')}</div>
        ) : cgVal != null ? (
          <>
            <div className="prob-rows">
              <span><b>{ruNum(cgVal, 2)}</b> {layer === 'pro' && C.has('card.cg-value-note') ? C.get('card.cg-value-note') : ''}</span>
            </div>
            <div className="prob-note">
              {C.has('card.cg-note.p1') && <Markdown text={C.get('card.cg-note.p1')} />}
              {C.has('card.cg-note.p2') && <Markdown text={C.get('card.cg-note.p2')} />}
            </div>
          </>
        ) : (
          <div className="prob-note">{C.get('card.cg-not-yet')}</div>
        )}
      </div>

      <div className="chart-block">
        <div className="chart-title">{C.get('card.fan-title')}</div>
        <LineChart
          series={fanSeries}
          domain={[years[0], years[years.length - 1]]}
          markYear={year}
          yFormat={(v) => v.toFixed(1)}
          refY={{ value: 1.5, label: t('порог 1,5') }}
        />
      </div>

      <div className="chart-block">
        <div className="chart-title">{C.get('card.cross-title')}</div>
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
          {C.get('card.cross-note')}
          {/* слой «Профессионально»: card.cross-note нарочно обрывается на тире,
              ждёт продолжения значением (как в исходном коде); слой «Просто» -
              самостоятельное законченное предложение (ТЗ §7.8), ничего не
              дописываем, иначе получится "...уже произошло. после 2045." */}
          {layer === 'pro' && (
            <>{' '}{cross1.kind === 'year' ? cross1.value : cross1.kind === 'interval' ? t(cross1.value) : C.get('card.cross-not-yet')}.</>
          )}
        </p>
      </div>
    </div>
  );
}

function CrossingTile({ th, entry, policy, skey, C }: {
  th: ThresholdKey;
  entry: TerritoryEntry;
  policy: PolicyId;
  skey: `${ScenarioId}:${JumpoffId}`;
  C: ContentGetter;
}) {
  const t = useT();
  const c = crossingDisplay(entry, policy, skey, th);
  return (
    <div className="stat-tile" data-threshold={th}>
      <div className="st-label">{C.get(THRESHOLD_CONTENT_KEY[th])}</div>
      <div className="st-value pen-crossing-value" data-kind={c.kind} style={{ fontSize: c.kind === 'interval' ? 13.5 : 17 }}>
        {c.kind === 'year' ? c.value : c.kind === 'interval' ? t(c.value) : t('не наступает до 2056')}
      </div>
    </div>
  );
}
