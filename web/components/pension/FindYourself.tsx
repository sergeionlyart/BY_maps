'use client';

/** «Найди себя» (ТЗ §3): год рождения + пол → год выхода на пенсию по
 *  действующему (или выбранному гипотетическому) графику → SR в выбранном
 *  районе на ближайший доступный год. Полностью на клиенте: состояние живёт
 *  только в React (useState), никуда не отправляется и нигде не
 *  сохраняется (localStorage/сеть здесь не используются намеренно).
 *
 *  INF-13 UX (handoff/10_pension_ux_copy §7.9): слой «Просто» - одна
 *  цельная фраза (грамматика русского требует разных падежей вокруг числа,
 *  поэтому не собирается из тех же фрагментов, что и профессиональный слой -
 *  один шаблон на весь результат). Слой «Профессионально» - тот же состав
 *  фрагментов, что был в коде до этой правки, перенесённый в контент-файл. */

import { useState } from 'react';
import { useT } from '@/lib/i18n';
import type { PensionFile, PolicyId, ScenarioId, JumpoffId } from '@/lib/pension';
import { findRetirementYear, nearestTerritoryYear, valueAt, seriesKey as mkSeriesKey } from '@/lib/pension';
import { ruNum, fillTemplate, type ContentGetter } from '@/lib/pensionContent';
import Markdown from '@/components/Markdown';

export default function FindYourself({
  pf,
  territoryId,
  territoryName,
  policy,
  scenario,
  jumpoff,
  layer,
  C,
}: {
  pf: PensionFile;
  territoryId: string;
  territoryName: string;
  policy: PolicyId;
  scenario: ScenarioId;
  jumpoff: JumpoffId;
  layer: 'simple' | 'pro';
  C: ContentGetter;
}) {
  const t = useT();
  const [birth, setBirth] = useState<number | null>(null);
  const [sex, setSex] = useState<'m' | 'f'>('f');

  const entry = pf.territories[territoryId];
  const retireYear = birth != null ? findRetirementYear(pf, birth, sex, policy) : null;
  const dataYear = retireYear != null ? nearestTerritoryYear(pf, retireYear) : null;
  const sr = entry && dataYear != null
    ? valueAt(entry.sr, pf.years.territory, policy, mkSeriesKey(scenario, jumpoff), dataYear)
    : null;
  const beyondHorizon = retireYear != null && retireYear > 2056;

  return (
    <div className="chart-block pen-find">
      <div className="chart-title">{C.get('find.title')}</div>
      {C.has('find.lead.p1') && <Markdown text={C.get('find.lead.p1')} />}
      <div className="controls" style={{ marginBottom: 6 }}>
        <label className="hint" htmlFor="pen-birth">{t('Год рождения:')}</label>
        <input
          id="pen-birth"
          className="pen-birth-input"
          type="number"
          min={1940}
          max={2056}
          placeholder="1990"
          aria-label={t('Год рождения')}
          value={birth ?? ''}
          onChange={(e) => {
            const v = parseInt(e.target.value, 10);
            setBirth(Number.isFinite(v) ? v : null);
          }}
        />
        <div className="seg" role="group" aria-label={t('Пол')}>
          <button className={sex === 'f' ? 'on' : ''} aria-pressed={sex === 'f'} onClick={() => setSex('f')}>{t('жен.')}</button>
          <button className={sex === 'm' ? 'on' : ''} aria-pressed={sex === 'm'} onClick={() => setSex('m')}>{t('муж.')}</button>
        </div>
      </div>
      {birth != null && retireYear != null && (
        <div className="pen-find-result">
          {sr == null ? (
            C.get('find.result-nodata')
          ) : layer === 'simple' ? (
            <>
              <Markdown text={fillTemplate(dataYear === retireYear ? C.get('find.result-main') : C.get('find.result-main-nearest'), {
                retireYear, district: territoryName, dataYear: dataYear ?? '', sr: ruNum(sr, 2),
              })} />
              {beyondHorizon && <span className="hint">{C.get('find.result-beyond-note')}</span>}
              {scenario !== 'base' && (
                <span className="hint">{' '}{fillTemplate(C.get('find.result-scenario-note'), { scenario: t(scenario === 'optimistic' ? 'оптимистический' : 'негативный') })}</span>
              )}
            </>
          ) : (
            <>
              {C.get('find.result-retire-label')} <strong>{retireYear}</strong> {C.get('find.result-year-word')}
              {beyondHorizon && ` (${C.get('find.result-beyond-suffix')})`}
              {'. '}
              {C.get('find.result-in-district')} «{territoryName}»{dataYear !== retireYear ? ` ${C.get('find.result-nearest-year')} ${dataYear}` : ` ${C.get('find.result-this-year')}`}{' '}
              {C.get('find.result-will-have')} <strong>{ruNum(sr, 2)}</strong> {C.get('find.result-workers-word')}
              {scenario !== 'base' ? ` (${C.get('find.result-scenario-word')}: ${t(scenario === 'optimistic' ? 'оптимистический' : 'негативный')})` : ''}.
            </>
          )}
        </div>
      )}
      <p className="hint" style={{ marginTop: 4 }}>
        {C.get('find.lead.p2') || t('Расчёт выполняется в браузере: год рождения никуда не отправляется и нигде не сохраняется.')}
      </p>
    </div>
  );
}
