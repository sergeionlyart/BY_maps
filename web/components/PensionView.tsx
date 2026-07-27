'use client';

/** INF-13 «Кто кого содержит»: карта коэффициента поддержки (SR) по 118
 *  районам, 2009-2056, с переключателями сценария/стартового ряда/
 *  пенсионного возраста, карточкой района, «найди себя» и тремя выводами.
 *
 *  INF-13 UX (handoff/10_pension_ux_copy/INF-13_PENSION_UX_AND_COPY_v1.md):
 *  1) два слоя текста «Просто»/«Профессионально», состояние в ?copy=pro,
 *     тексты - из web/public/content/research/pension.<layer>.<lang>.md;
 *  2) новый порядок блоков (разд. 5): карта на всю ширину -> строка времени
 *     с кнопкой ▶ сразу под картой -> легенда -> счётчик -> настройки ->
 *     карточка района -> график по стране -> найди себя -> три вывода ->
 *     ограничения -> методика;
 *  3) мобильная версия (разд. 6): настройки-аккордеон, карточка района -
 *     шторкой, кнопка ▶ в липкой панели времени, длинные блоки свёрнуты.
 *  Расчёт/данные не менялись - те же useMemo, что были в исходном коде. */

import { useEffect, useMemo, useState } from 'react';
import { useT, useLang } from '@/lib/i18n';
import type { DataFile } from '@/lib/types';
import type { PensionFile, PolicyId, ScenarioId, JumpoffId } from '@/lib/pension';
import { POLICIES, SCENARIOS, JUMPOFFS, POLICY_LABEL, valueAt, countBelowThreshold, seriesKey as mkSeriesKey } from '@/lib/pension';
import { SCENARIO_LABEL, JUMPOFF_LABEL } from '@/lib/forecast';
import { usePensionContent, makeGetter, readLayerParam, fillTemplate, ruNum, type CopyLayer } from '@/lib/pensionContent';
import MethodDrawer from '@/components/MethodDrawer';
import Markdown from '@/components/Markdown';
import LineChart from '@/components/LineChart';
import PensionSlider from '@/components/pension/PensionSlider';
import PensionMap from '@/components/pension/PensionMap';
import PensionLegend from '@/components/pension/PensionLegend';
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
  const [layer, setLayer] = useState<CopyLayer>(() => readLayerParam());

  const [howtoOpen, setHowtoOpen] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [cardOpen, setCardOpen] = useState(false);
  const [findingsOpen, setFindingsOpen] = useState(false);
  const [limitsOpen, setLimitsOpen] = useState(false);
  const [everPlayed, setEverPlayed] = useState(false);

  const content = usePensionContent(layer, lang);
  const C = makeGetter(content);

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
      if (layer !== 'simple') url.searchParams.set('copy', layer); else url.searchParams.delete('copy');
      try {
        window.history.replaceState(null, '', url.toString());
      } catch {
        // лимит браузера на replaceState - пропускаем тик, догонит следующий
      }
    }, 350);
    return () => window.clearTimeout(id);
  }, [pf, year, scenario, jumpoff, policy, selected, layer]);

  const key = mkSeriesKey(scenario, jumpoff);

  const nameFor = (id: string) => (lang === 'be' ? (names[id]?.be || names[id]?.ru) : names[id]?.ru) ?? id;

  const raionIds = useMemo(
    () => Object.keys(pf?.territories ?? {}).sort((a, b) => nameFor(a).localeCompare(nameFor(b), 'ru')),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [pf, lang, names],
  );

  const counter = useMemo(() => {
    if (!pf) return null;
    return countBelowThreshold(pf, 1.0, year, key, policy);
  }, [pf, policy, key, year]);

  // фиксированный факт для лида (§7.2): доля районов с SR<1,5 к 2046 году по
  // сценарию base:official, НЕ зависит от текущих настроек читателя.
  const leadBelow2046 = useMemo(() => {
    if (!pf) return null;
    return countBelowThreshold(pf, 1.5, 2046, 'base:official' as const);
  }, [pf]);

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

  const select = (id: string) => { setSelected(id); setHowtoOpen(false); setCardOpen(true); };

  if (!pf || !geo || !content) return <p className="hint">{t('Загрузка данных…')}</p>;

  const entry = pf.territories[selected] ?? pf.territories[DEFAULT_TERRITORY];
  const selId = pf.territories[selected] ? selected : DEFAULT_TERRITORY;

  const counterVars = {
    year,
    policy: t(POLICY_LABEL[policy]),
    scenario: t(SCENARIO_LABEL[scenario]),
    jumpoff: t(JUMPOFF_LABEL[jumpoff]),
  };

  return (
    <div className="pen-view">
      {/* 1. Заголовок + лид + переключатель слоя (разд. 5 п.1) */}
      <header className="pen-header">
        <h1>{C.get('title')}</h1>
        <p className="pen-subtitle">{C.get('subtitle')}</p>
        <div className="pen-lead">
          {C.has('lead.p1') && <Markdown text={C.get('lead.p1')} />}
          {C.has('lead.p2') && <Markdown text={fillTemplate(C.get('lead.p2'), { below2046: leadBelow2046?.below ?? '—' })} />}
          {C.has('lead.p3') && <Markdown text={C.get('lead.p3')} />}
        </div>
        <div className="pen-layer-toggle" role="group" aria-label={C.get('micro.layer-toggle')}>
          <span className="pen-layer-toggle-label">{C.get('micro.layer-toggle')}:</span>
          <div className="seg">
            <button className={layer === 'simple' ? 'on' : ''} aria-pressed={layer === 'simple'} onClick={() => setLayer('simple')}>
              {C.get('micro.layer-simple')}
            </button>
            <button className={layer === 'pro' ? 'on' : ''} aria-pressed={layer === 'pro'} onClick={() => setLayer('pro')}>
              {C.get('micro.layer-pro')}
            </button>
          </div>
        </div>
      </header>

      {/* 2. «Как читать эту карту» (разд. 5 п.2) */}
      <div className="pen-howto">
        <button type="button" className="pen-howto-toggle" onClick={() => setHowtoOpen((v) => !v)} aria-expanded={howtoOpen}>
          {C.get('howto.label')} {howtoOpen ? '▴' : '▾'}
        </button>
        {howtoOpen && (
          <div className="pen-howto-steps">
            <div className="pen-howto-step"><Markdown text={C.get('howto.1')} /></div>
            <div className="pen-howto-step"><Markdown text={C.get('howto.2')} /></div>
            <div className="pen-howto-step"><Markdown text={C.get('howto.3')} /></div>
          </div>
        )}
      </div>

      {/* 3. Карта - во всю ширину (разд. 5 п.3) */}
      <div className="chart-block pen-map-block">
        <div className="chart-title">{C.get('map.caption-title')}</div>
        {C.has('map.caption-sub') && <p className="hint pen-map-caption-sub">{C.get('map.caption-sub')}</p>}
        <PensionMap
          geo={geo}
          pf={pf}
          names={Object.fromEntries(raionIds.map((id) => [id, nameFor(id)]))}
          policy={policy}
          seriesKey={key}
          year={year}
          selected={selId}
          onSelect={select}
          C={C}
        />
      </div>

      {/* 4. Строка времени, сразу под картой (разд. 5 п.4) */}
      <PensionSlider
        years={pf.years.territory}
        dtype={pf.dtype.territory}
        idx={Math.max(0, pf.years.territory.indexOf(year))}
        onChange={(i) => { setYear(pf.years.territory[i]); setEverPlayed(true); }}
        C={C}
        firstPlay={!everPlayed}
      />

      {/* 5. Легенда с человеческими подписями (разд. 5 п.5) */}
      <PensionLegend C={C} />

      {/* 6. Счётчик (разд. 5 п.6) */}
      <div className="stat-row">
        <div className="stat-tile forecast-tile" style={{ flex: '1 1 100%' }}>
          <div className="st-label">{C.get('counter.label')} — {fillTemplate(C.get('counter.settings-sentence'), counterVars)}</div>
          <div className="st-value pen-counter-value" style={{ fontSize: 26 }}>{counter?.below} {t('из')} {counter?.total}</div>
        </div>
      </div>

      {/* 7. Настройки: сценарий/стартовый ряд в аккордеоне на мобильном,
             пенсионный возраст - отдельно и заметнее (разд. 5 п.7, разд. 6 п.2) */}
      <div className={`pen-settings-acc${settingsOpen ? ' open' : ''}`}>
        <button type="button" className="pen-settings-toggle" onClick={() => setSettingsOpen((v) => !v)} aria-expanded={settingsOpen}>
          {t('Настройки прогноза')} {settingsOpen ? '▴' : '▾'}
        </button>
        <div className="pen-settings-body controls" style={{ marginBottom: 6 }}>
          <div className="control-group">
            <span className="control-label">{C.get('settings.scenario.label')}</span>
            <div className="seg" role="group" aria-label={C.get('settings.scenario.label')}>
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
            {C.has('settings.scenario.hint') && <p className="hint pen-setting-hint">{C.get('settings.scenario.hint')}</p>}
          </div>
          <div className="control-group">
            <span className="control-label">{C.get('settings.jumpoff.label')}</span>
            <div className="seg" role="group" aria-label={C.get('settings.jumpoff.label')}>
              {JUMPOFFS.map((j) => (
                <button key={j} className={jumpoff === j ? 'on' : ''} aria-pressed={jumpoff === j} onClick={() => setJumpoff(j)}>
                  {t(JUMPOFF_LABEL[j])}
                </button>
              ))}
            </div>
            {C.has('settings.jumpoff.hint') && <p className="hint pen-setting-hint">{C.get('settings.jumpoff.hint')}</p>}
          </div>
        </div>
      </div>
      <div className="controls pen-policy-primary" style={{ marginBottom: 6 }}>
        <div className="control-group">
          <span className="control-label">{C.get('settings.policy.label')}</span>
          <div className="seg" role="group" aria-label={C.get('settings.policy.label')}>
            {POLICIES.map((p) => (
              <button key={p} className={policy === p ? 'on' : ''} aria-pressed={policy === p} onClick={() => setPolicy(p)}>
                {t(POLICY_LABEL[p])}
              </button>
            ))}
          </div>
          {C.has('settings.policy.hint') && <p className="hint pen-setting-hint">{C.get('settings.policy.hint')}</p>}
        </div>
      </div>

      {/* 8. Карточка района - шторкой на мобильном (разд. 5 п.8, разд. 6 п.6) */}
      <div className={`chart-block pen-card-sheet${cardOpen ? ' open' : ''}`}>
        <button type="button" className="pen-sheet-handle" onClick={() => setCardOpen((v) => !v)} aria-expanded={cardOpen}>
          <span className="pen-sheet-grip" aria-hidden="true" />
          <span className="pen-sheet-peek">{nameFor(selId)} · {(() => {
            const v = valueAt(entry.sr, pf.years.territory, policy, key, year);
            return v != null ? ruNum(v, 2) : '—';
          })()}</span>
        </button>
        <div className="pen-sheet-body">
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
            layer={layer}
            C={C}
          />
        </div>
        <div className="controls" style={{ margin: '6px 0 0' }}>
          <select value={selId} onChange={(e) => select(e.target.value)} aria-label={t('район')}>
            {raionIds.map((id) => <option key={id} value={id}>{nameFor(id)}</option>)}
          </select>
        </div>
      </div>

      {/* 9. График по стране - после карты и карточки, с пояснением (разд. 5 п.9) */}
      <div className="chart-block">
        <div className="chart-title">{C.get('chart-country.title')}</div>
        <LineChart series={nationalSeries} domain={[1989, 2056]} markYear={year} yFormat={(v) => v.toFixed(1)} refY={{ value: 1.5, label: t('порог 1,5') }} />
        {C.has('chart-country.caption.p1') && <Markdown text={C.get('chart-country.caption.p1')} />}
        {C.has('chart-country.caption.p2') && <Markdown text={C.get('chart-country.caption.p2')} />}
      </div>

      {/* 10. Найди себя */}
      <FindYourself pf={pf} territoryId={selId} territoryName={nameFor(selId)} policy={policy} scenario={scenario} jumpoff={jumpoff} layer={layer} C={C} />

      {/* 11. Три вывода - свёрнуто на мобильном до вводной (разд. 6 п.7) */}
      <div className={`pen-collapsible${findingsOpen ? ' open' : ''}`}>
        <div className="pen-collapsible-body">
          <Findings pf={pf} C={C} />
        </div>
      </div>
      <button type="button" className="pen-more-btn" onClick={() => setFindingsOpen((v) => !v)}>
        {findingsOpen ? C.get('micro.less') : C.get('micro.more')}
      </button>

      {/* 12. Чего это исследование не говорит - свёрнуто на мобильном (разд. 6 п.7) */}
      <section>
        <h2>{C.get('limits.title')}</h2>
        <div className={`pen-collapsible${limitsOpen ? ' open' : ''}`}>
          <div className="pen-collapsible-body limit-list">
            {['limits.1', 'limits.2', 'limits.3', 'limits.4', 'limits.5'].map((k) => (
              C.has(k) && <Markdown key={k} text={C.get(k)} />
            ))}
          </div>
        </div>
        <button type="button" className="pen-more-btn" onClick={() => setLimitsOpen((v) => !v)}>
          {limitsOpen ? C.get('micro.less') : C.get('micro.more')}
        </button>
      </section>

      {/* 13. Методика и данные - короткий пересказ + кнопки (разд. 5 п.13) */}
      <section className="pen-method-pitch">
        <h2>{C.get('method.title')}</h2>
        {['method.people', 'method.age', 'method.money', 'method.checks', 'method.diy'].map((k) => (
          C.has(k) && <Markdown key={k} text={C.get(k)} />
        ))}
        <div className="controls" style={{ marginTop: 8 }}>
          <MethodDrawer slug="pension" label={C.get('micro.method-button') || 'О данных и методике'} />
          <a className="btn" href="/artifacts/by-maps-pension-v1.0.0.zip" download>
            {C.get('micro.archive-button')}
          </a>
        </div>
      </section>

      <p className="hint attribution">
        {t('Источники: переписи 2009/2019 (Белстат), прогноз проекта v2026.4, дата-портал занятости и зарплат Белстата, отчёты ФСЗН (уровень области), Указ Президента №137 от 11.04.2016. Полная методика — в методблоке выше и в проверяемом пакете.')}
      </p>
    </div>
  );
}
