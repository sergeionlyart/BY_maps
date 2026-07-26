'use client';

/** «Найди себя» (ТЗ §3): год рождения + пол → год выхода на пенсию по
 *  действующему (или выбранному гипотетическому) графику → SR в выбранном
 *  районе на ближайший доступный год. Полностью на клиенте: состояние живёт
 *  только в React (useState), никуда не отправляется и нигде не
 *  сохраняется (localStorage/сеть здесь не используются намеренно). */

import { useState } from 'react';
import { useT } from '@/lib/i18n';
import type { PensionFile, PolicyId, ScenarioId, JumpoffId } from '@/lib/pension';
import { findRetirementYear, nearestTerritoryYear, valueAt, seriesKey as mkSeriesKey } from '@/lib/pension';

export default function FindYourself({
  pf,
  territoryId,
  territoryName,
  policy,
  scenario,
  jumpoff,
}: {
  pf: PensionFile;
  territoryId: string;
  territoryName: string;
  policy: PolicyId;
  scenario: ScenarioId;
  jumpoff: JumpoffId;
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
      <div className="chart-title">{t('Найди себя')}</div>
      <div className="controls" style={{ marginBottom: 6 }}>
        <label className="hint" htmlFor="pen-birth">{t('Год рождения:')}</label>
        <input
          id="pen-birth"
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
        <p className="pen-find-result">
          {t('Выход на пенсию:')} <strong>{retireYear}</strong> {t('год')}
          {beyondHorizon && ` (${t('за пределами горизонта прогноза, 2056 год')})`}
          {'. '}
          {sr != null ? (
            <>
              {t('В районе')} «{territoryName}»{dataYear !== retireYear ? ` ${t('на ближайший доступный год')} ${dataYear}` : ` ${t('в этот год')}`}{' '}
              {t('на одного пожилого будет приходиться')} <strong>{sr.toFixed(2)}</strong> {t('работающих')}
              {scenario !== 'base' ? ` (${t('сценарий')}: ${t(scenario === 'optimistic' ? 'оптимистический' : 'негативный')})` : ''}.
            </>
          ) : (
            t('Данных SR для этого года и района нет.')
          )}
        </p>
      )}
      <p className="hint" style={{ marginTop: 4 }}>
        {t('Расчёт выполняется в браузере: год рождения никуда не отправляется и нигде не сохраняется.')}
      </p>
    </div>
  );
}
