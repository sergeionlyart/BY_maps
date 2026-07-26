'use client';

/** INF-13 «Кто кого содержит»: карта коэффициента поддержки (SR) по 118
 *  районам, 2009-2056, с переключателями сценария/стартового ряда/
 *  пенсионного возраста, карточкой района, «найди себя» и тремя проверенными
 *  гипотезами. Шаблоны: AgingView/MLChallengerView (SVG-хороплет), PyramidView
 *  (слайдер по остановкам + дебаунс deep-link), UrbanOverhangView (ResearchShell/
 *  MethodDrawer/i18n). */

import { useEffect, useMemo, useState } from 'react';
import { useT, useLang } from '@/lib/i18n';
import type { DataFile } from '@/lib/types';
import type { PensionFile, PolicyId, ScenarioId, JumpoffId } from '@/lib/pension';
import { POLICIES, SCENARIOS, JUMPOFFS, POLICY_LABEL, valueAt, seriesKey as mkSeriesKey } from '@/lib/pension';
import { SCENARIO_LABEL, JUMPOFF_LABEL, SCENARIO_STYLE } from '@/lib/forecast';
import MethodDrawer from '@/components/MethodDrawer';
import LineChart from '@/components/LineChart';
import PensionSlider from '@/components/pension/PensionSlider';
import PensionMap from '@/components/pension/PensionMap';
import TerritoryPanel from '@/components/pension/TerritoryPanel';
import FindYourself from '@/components/pension/FindYourself';
import Findings from '@/components/pension/Findings';

interface GeoFeature {
  properties: { id: string };
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][] };
}

const DEFAULT_TERRITORY = 'r-karelicki';

function readParam(name: string): string | null {
  if (typeof window === 'undefined') return null;
  return new URLSearchParams(window.location.search).get(name);
}

export default function PensionView() {
  const t = useT();
  const lang = useLang();

  const [pf, setPf] = useState<PensionFile | null>(null);
  const [geo, setGeo] = useState<GeoFeature[] | null>(null);
  const [names, setNames] = useState<Record<string, { ru: string; be: string }>>({});

  const [year, setYear] = useState<number>(() => {
    const y = parseInt(readParam('year') ?? '', 10);
    return Number.isFinite(y) ? y : 2026;
  });
  const [scenario, setScenario] = useState<ScenarioId>(() => {
    const s = readParam('scenario');
    return (SCENARIOS as string[]).includes(s ?? '') ? (s as ScenarioId) : 'base';
  });
  const [jumpoff, setJumpoff] = useState<JumpoffId>(() => {
    const j = readParam('jumpoff');
    return (JUMPOFFS as string[]).includes(j ?? '') ? (j as JumpoffId) : 'official';
  });
  const [policy, setPolicy] = useState<PolicyId>(() => {
    const p = readParam('policy');
    return (POLICIES as string[]).includes(p ?? '') ? (p as PolicyId) : 'as_is';
  });
  const [selected, setSelected] = useState<string>(() => readParam('sel') ?? DEFAULT_TERRITORY);

  useEffect(() => {
    let alive = true;
    fetch('/data/pension.json').then((r) => r.json()).then((d: PensionFile) => { if (alive) setPf(d); });
    fetch('/data/geo/adm2.geojson').then((r) => r.json()).then((g) => {
      if (alive) setGeo(g.features.filter((f: GeoFeature) => f.properties.id.startsWith('r-')));
    });
    fetch('/data/data.json').then((r) => r.json()).then((d: DataFile) => {
      if (!alive) return;
      const m: Record<string, { ru: string; be: string }> = {};
      for (const terr of Object.values(d.territories)) m[terr.id] = { ru: terr.ru, be: terr.be };
      setNames(m);
    });
    return () => { alive = false; };
  }, []);

  // deep-link: запись состояния с дебаунсом (регресс INF-08/INF-11 - без
  // дебаунса быстрое перетаскивание слайдера роняет replaceState с
  // SecurityError на лимите браузера ~100 вызовов/10 с).
  useEffect(() => {
    if (!pf) return;
    const id = window.setTimeout(() => {
      const url = new URL(window.location.href);
      url.searchParams.set('year', String(year));
      if (scenario !== 'base') url.searchParams.set('scenario', scenario); else url.searchParams.delete('scenario');
      if (jumpoff !== 'official') url.searchParams.set('jumpoff', jumpoff); else url.searchParams.delete('jumpoff');
      if (policy !== 'as_is') url.searchParams.set('policy', policy); else url.searchParams.delete('policy');
      if (selected !== DEFAULT_TERRITORY) url.searchParams.set('sel', selected); else url.searchParams.delete('sel');
      try {
        window.history.replaceState(null, '', url.toString());
      } catch {
        // лимит браузера на replaceState - пропускаем тик, догонит следующий
      }
    }, 350);
    return () => window.clearTimeout(id);
  }, [pf, year, scenario, jumpoff, policy, selected]);

  const key = mkSeriesKey(scenario, jumpoff);

  const nameFor = (id: string) => (lang === 'be' ? (names[id]?.be || names[id]?.ru) : names[id]?.ru) ?? id;

  const raionIds = useMemo(
    () => Object.keys(pf?.territories ?? {}).sort((a, b) => nameFor(a).localeCompare(nameFor(b), 'ru')),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [pf, lang, names],
  );

  const counter = useMemo(() => {
    if (!pf) return null;
    let below = 0, n = 0;
    for (const entry of Object.values(pf.territories)) {
      const v = valueAt(entry.sr, pf.years.territory, policy, key, year);
      if (v == null) continue;
      n++;
      if (v < 1.0) below++;
    }
    return { below, n };
  }, [pf, policy, key, year]);

  const nationalSeries = useMemo(() => {
    if (!pf) return [];
    return [{
      name: t('коэффициент поддержки, страна'),
      color: 'var(--accent-2)',
      points: pf.years.national.map((y) => {
        const v = valueAt(pf.national.sr, pf.years.national, policy, key, y);
        return v == null ? null : { year: y, value: v, major: pf.dtype.national[String(y)] === 'c' };
      }).filter((p): p is { year: number; value: number; major: boolean } => p != null),
    }];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pf, policy, key]);

  const select = (id: string) => setSelected(id);

  if (!pf || !geo) return <p className="hint">{t('Загрузка данных…')}</p>;

  const entry = pf.territories[selected] ?? pf.territories[DEFAULT_TERRITORY];
  const selId = pf.territories[selected] ? selected : DEFAULT_TERRITORY;

  return (
    <div className="pen-view">
      <div className="stat-row">
        <div className="stat-tile forecast-tile" style={{ flex: '1 1 100%' }}>
          <div className="st-label">{t('районов, где на одного пожилого меньше одного работающего')} ({year}, {t(POLICY_LABEL[policy])}, {t(SCENARIO_LABEL[scenario])}, {t(JUMPOFF_LABEL[jumpoff])})</div>
          <div className="st-value pen-counter-value" style={{ fontSize: 26 }}>{counter?.below} {t('из')} {counter?.n}</div>
        </div>
      </div>

      <div className="controls" style={{ marginBottom: 6 }}>
        <div className="control-group">
          <span className="control-label">{t('Сценарий прогноза')}</span>
          <div className="seg" role="group" aria-label={t('Сценарий прогноза')}>
            {(['optimistic', 'base', 'negative'] as ScenarioId[]).map((s) => (
              <button
                key={s}
                className={`scn scn-${s}${scenario === s ? ' on' : ''}`}
                aria-pressed={scenario === s}
                onClick={() => setScenario(s)}
              >
                {t(SCENARIO_LABEL[s])}
              </button>
            ))}
          </div>
        </div>
        <div className="control-group">
          <span className="control-label">{t('Стартовый ряд')}</span>
          <div className="seg" role="group" aria-label={t('Стартовый ряд')}>
            {JUMPOFFS.map((j) => (
              <button key={j} className={jumpoff === j ? 'on' : ''} aria-pressed={jumpoff === j} onClick={() => setJumpoff(j)}>
                {t(JUMPOFF_LABEL[j])}
              </button>
            ))}
          </div>
        </div>
        <div className="control-group">
          <span className="control-label">{t('Пенсионный возраст (муж./жен.)')}</span>
          <div className="seg" role="group" aria-label={t('Пенсионный возраст')}>
            {POLICIES.map((p) => (
              <button key={p} className={policy === p ? 'on' : ''} aria-pressed={policy === p} onClick={() => setPolicy(p)}>
                {t(POLICY_LABEL[p])}
              </button>
            ))}
          </div>
        </div>
        <MethodDrawer slug="pension" />
        <a className="btn" href="/artifacts/by-maps-pension-v1.0.0.zip" download>
          {t('⬇ Проверяемый пакет (ZIP)')}
        </a>
      </div>

      <div className="chart-block">
        <div className="chart-title">{t('Национальный тренд, 1989–2056 (справочно; районный ряд начинается с 2009 года)')}</div>
        <LineChart series={nationalSeries} domain={[1989, 2056]} markYear={year} yFormat={(v) => v.toFixed(1)} refY={{ value: 1.5, label: t('порог 1,5') }} />
      </div>

      <PensionSlider years={pf.years.territory} dtype={pf.dtype.territory} idx={Math.max(0, pf.years.territory.indexOf(year))} onChange={(i) => setYear(pf.years.territory[i])} />

      <div className="grid-2">
        <div className="chart-block">
          <div className="chart-title">{t('Коэффициент поддержки по районам (клик — выбрать район)')}</div>
          <PensionMap geo={geo} pf={pf} names={Object.fromEntries(raionIds.map((id) => [id, nameFor(id)]))} policy={policy} seriesKey={key} year={year} selected={selId} onSelect={select} />
          <div className="controls" style={{ margin: '6px 0 0' }}>
            <select value={selId} onChange={(e) => select(e.target.value)} aria-label={t('район')}>
              {raionIds.map((id) => <option key={id} value={id}>{nameFor(id)}</option>)}
            </select>
          </div>
        </div>
        <div className="chart-block">
          <TerritoryPanel
            pf={pf}
            id={selId}
            entry={entry}
            name={nameFor(selId)}
            oblastName={nameFor(entry.oblast)}
            scenario={scenario}
            jumpoff={jumpoff}
            policy={policy}
            year={year}
          />
        </div>
      </div>

      <FindYourself pf={pf} territoryId={selId} territoryName={nameFor(selId)} policy={policy} scenario={scenario} jumpoff={jumpoff} />

      <Findings pf={pf} />

      <section>
        <h2>{t('Что это исследование не утверждает')}</h2>
        <ul className="limit-list">
          <li>{t('Условная денежная арифметика (CG) — не реальные доходы или расходы района: общереспубликанский пенсионный фонд по районам не делится.')}</li>
          <li>{t('CG не является независимым от демографии подтверждением тренда: при текущем экономическом масштабе района CG пропорционален SR.')}</li>
          <li>{t('Год перехода районов — честный интервал, а не точная дата: проверка на прошлом (бэктест 2009→2019) не пройдена на районном уровне.')}</li>
          <li>{t('Прогноз — не предсказание: три сценария — три набора предположений, а не три версии будущего.')}</li>
          <li>{t('Повышение пенсионного возраста не устраняет проблему всюду: для 27 из 93 затронутых районов переход лишь отодвигается за горизонт расчёта (2056 год), а не отменяется навсегда.')}</li>
        </ul>
      </section>

      <p className="hint attribution">
        {t('Источники: переписи 2009/2019 (Белстат), прогноз проекта v2026.4, дата-портал занятости и зарплат Белстата, отчёты ФСЗН (уровень области), Указ Президента №137 от 11.04.2016. Полная методика — в методблоке ниже и в проверяемом пакете.')}
      </p>

      <MethodDrawer slug="pension" />
    </div>
  );
}
