'use client';

import { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import type { DataFile, Metric, MapLevel, RaionMode } from '@/lib/types';
import type { ForecastFile, ScenarioId, JumpoffId } from '@/lib/forecast';
import { FORECAST_START, JUMPOFF_LABEL } from '@/lib/forecast';
import { useMedia } from '@/lib/useMedia';
import { useT } from '@/lib/i18n';
import TimeBar from '@/components/TimeBar';
import TerritoryCard from '@/components/TerritoryCard';
import ComparePanel from '@/components/ComparePanel';
import UrbanPanel from '@/components/UrbanPanel';
import MethodDrawer from '@/components/MethodDrawer';

const MapView = dynamic(() => import('@/components/MapView'), { ssr: false });

type Tab = 'territory' | 'compare' | 'urban';

interface GeoBundle {
  adm1: GeoJSON.FeatureCollection;
  adm2: GeoJSON.FeatureCollection;
  border1921: GeoJSON.FeatureCollection;
}

const BASE_YEARS = [1897, 1959, 1970, 1979, 1989, 1999, 2009, 2019];
const METRIC_LABEL: Record<Metric, string> = {
  pop: 'Численность',
  density: 'Плотность',
  change: 'Изменение',
};

export default function MapApp() {
  const [data, setData] = useState<DataFile | null>(null);
  const [geo, setGeo] = useState<GeoBundle | null>(null);
  const [forecast, setForecast] = useState<ForecastFile | null>(null);
  const [scenario, setScenario] = useState<ScenarioId>('base');
  const [jumpoff, setJumpoff] = useState<JumpoffId>('official');
  const [year, setYear] = useState(2019);
  // стартовый вид - главный сюжет проекта: плотность сельской части районов
  // (без городских центров) + города точками поверх
  const [metric, setMetric] = useState<Metric>('density');
  const [level, setLevel] = useState<MapLevel>('raion');
  const [raionMode, setRaionMode] = useState<RaionMode>('noCenter');
  const [baseYear, setBaseYear] = useState(1989);
  const [showBorder, setShowBorder] = useState(false);
  const [showCities, setShowCities] = useState(true);
  // диплинк ?sel=<id> читается синхронно при монтировании - до эффекта,
  // который синхронизирует выбор обратно в URL
  const [selected, setSelected] = useState<string | null>(() =>
    typeof window === 'undefined'
      ? null
      : new URLSearchParams(window.location.search).get('sel'));
  const [compare, setCompare] = useState<string[]>([]);
  const [tab, setTab] = useState<Tab>('territory');

  // мобильные шторки (U-05 контролы, U-06 карточка территории)
  const narrow = useMedia('(max-width: 980px)');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [cardOpen, setCardOpen] = useState(false);
  const touchY = useRef<number | null>(null);

  const t = useT();

  // режим приложения: страница /map не прокручивается
  useEffect(() => {
    document.body.classList.add('map-mode');
    return () => document.body.classList.remove('map-mode');
  }, []);

  useEffect(() => {
    Promise.all([
      fetch('/data/data.json').then((r) => r.json()),
      fetch('/data/geo/adm1.geojson').then((r) => r.json()),
      fetch('/data/geo/adm2.geojson').then((r) => r.json()),
      fetch('/data/geo/border1921.geojson').then((r) => r.json()),
    ]).then(([d, adm1, adm2, border1921]) => {
      setData(d);
      setGeo({ adm1, adm2, border1921 });
    });
    fetch('/data/forecast.json').then((r) => (r.ok ? r.json() : null)).then(setForecast);
  }, []);

  // выбранная территория - в URL (для диплинков и «назад»)
  useEffect(() => {
    if (!data) return;
    const url = new URL(window.location.href);
    if (selected && data.territories[selected]) url.searchParams.set('sel', selected);
    else url.searchParams.delete('sel');
    window.history.replaceState(null, '', url);
  }, [selected, data]);

  const select = (id: string | null) => {
    setSelected(id);
    if (id) {
      setTab('territory');
      // на мобильном карточка и шторка настроек — взаимоисключающие (обе fixed)
      if (narrow) { setCardOpen(true); setSettingsOpen(false); }
    } else if (narrow) {
      setCardOpen(false);
    }
  };

  const openSettings = () => { setSettingsOpen(true); setCardOpen(false); };

  const metricSafe: Metric = level === 'city' && metric === 'density' ? 'pop' : metric;
  const inForecast = !!forecast && year > FORECAST_START;

  const compareAdd = (id: string) =>
    setCompare((c) => (c.includes(id) || c.length >= 4 ? c : [...c, id]));

  const loaded = data && geo;

  // чипы активных нестандартных настроек над картой (мобильный) — U-05
  const chips: string[] = [];
  if (metricSafe !== 'density') chips.push(t(METRIC_LABEL[metricSafe]));
  if (level === 'raion' && raionMode === 'total') chips.push(t('весь район'));
  if (metricSafe === 'change') chips.push(`${t('база')} ${baseYear}`);
  if (inForecast && forecast && scenario !== 'base') chips.push(t(forecast.scenarioMeta[scenario].name));
  if (inForecast && jumpoff === 'adjusted') chips.push(t('ряд скорр.'));
  if (level !== 'city' && !showCities) chips.push(t('без городов'));
  if (showBorder) chips.push(t('граница 1921'));

  // свайп вниз по «ручке» шторки закрывает карточку
  const onHandleTouchStart = (e: React.TouchEvent) => { touchY.current = e.touches[0].clientY; };
  const onHandleTouchMove = (e: React.TouchEvent) => {
    if (touchY.current != null && e.touches[0].clientY - touchY.current > 60) {
      setCardOpen(false);
      touchY.current = null;
    }
  };

  const secondaryControls = (
    <>
      <div className="control-group">
        <span className="control-label">{t('Показатель')}</span>
        <div className="seg">
          <button className={metricSafe === 'pop' ? 'on' : ''} onClick={() => setMetric('pop')}>{t('Численность')}</button>
          <button
            className={metricSafe === 'density' ? 'on' : ''}
            onClick={() => setMetric('density')}
            disabled={level === 'city'}
          >
            {t('Плотность')}
          </button>
          <button className={metricSafe === 'change' ? 'on' : ''} onClick={() => setMetric('change')}>{t('Изменение')}</button>
        </div>
      </div>

      {level === 'raion' && (
        <div className="control-group">
          <span className="control-label">{t('Район')}</span>
          <div className="seg">
            <button className={raionMode === 'total' ? 'on' : ''} onClick={() => setRaionMode('total')}>{t('Весь район')}</button>
            <button className={raionMode === 'noCenter' ? 'on' : ''} onClick={() => setRaionMode('noCenter')}>{t('Без центра')}</button>
          </div>
        </div>
      )}

      {metricSafe === 'change' && (
        <div className="control-group">
          <span className="control-label">{t('База')}</span>
          <select className="base-year" value={baseYear} onChange={(e) => setBaseYear(+e.target.value)}>
            {BASE_YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
      )}

      {forecast && year > FORECAST_START && (
        <div className="control-group forecast-scenarios">
          <span className="control-label">{t('Сценарий прогноза')}</span>
          <div className="seg">
            {forecast.scenarios.map((s) => (
              <button
                key={s}
                className={`scn scn-${s}${scenario === s ? ' on' : ''}`}
                onClick={() => setScenario(s)}
              >
                {t(forecast.scenarioMeta[s].name)}
              </button>
            ))}
          </div>
          {forecast.adjusted && (
            <>
              <span className="control-label" title={forecast.adjustedMeta?.note}>{t('Стартовый ряд')}</span>
              <div className="seg">
                {(['official', 'adjusted'] as JumpoffId[]).map((j) => (
                  <button key={j} className={jumpoff === j ? 'on' : ''}
                    title={j === 'adjusted' ? forecast.adjustedMeta?.note : t('официальные оценки Белстата на 01.01.2026')}
                    onClick={() => setJumpoff(j)}>
                    {t(JUMPOFF_LABEL[j])}
                  </button>
                ))}
              </div>
            </>
          )}
          <MethodDrawer slug="forecast" label={t('Методика прогноза')} />
        </div>
      )}

      {level !== 'city' && (
        <label className="toggle">
          <input type="checkbox" checked={showCities} onChange={(e) => setShowCities(e.target.checked)} />
          {t('города точками')}
        </label>
      )}

      <label className="toggle">
        <input type="checkbox" checked={showBorder} onChange={(e) => setShowBorder(e.target.checked)} />
        {t('граница 1921–1939')}
      </label>

      <MethodDrawer slug="map" />
    </>
  );

  return (
    <div className="mapapp">
      <div className="mapapp-bar">
        <div className="control-group mapapp-primary">
          <span className="control-label">{t('Уровень')}</span>
          <div className="seg">
            <button className={level === 'oblast' ? 'on' : ''} onClick={() => setLevel('oblast')}>{t('Области')}</button>
            <button className={level === 'raion' ? 'on' : ''} onClick={() => setLevel('raion')}>{t('Районы')}</button>
            <button className={level === 'city' ? 'on' : ''} onClick={() => setLevel('city')}>{t('Города')}</button>
          </div>
        </div>

        <button className="btn sheet-open-btn" onClick={openSettings} aria-expanded={settingsOpen}>
          {t('Слои и показатель')}{chips.length ? ` · ${chips.length}` : ''}
        </button>

        {chips.length > 0 && (
          <div className="mapapp-chips" onClick={openSettings}>
            {chips.map((c) => <span key={c} className="mapapp-chip">{c}</span>)}
          </div>
        )}

        <div className={`mapapp-secondary ${settingsOpen ? 'open' : ''}`}>
          <div className="sheet-head">
            <span className="sheet-title">{t('Слои и показатель')}</span>
            <button className="sheet-close" onClick={() => setSettingsOpen(false)} aria-label={t('закрыть')}>×</button>
          </div>
          {secondaryControls}
        </div>
      </div>

      <div className="mapapp-main">
        {loaded ? (
          <MapView
            data={data}
            geo={geo}
            forecast={forecast}
            scenario={scenario}
            jumpoff={jumpoff}
            year={year}
            metric={metricSafe}
            level={level}
            raionMode={raionMode}
            baseYear={baseYear}
            showBorder1921={showBorder}
            showCities={showCities}
            selected={selected}
            onSelect={select}
          />
        ) : (
          <div className="map-wrap" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span className="hint">{t('Загрузка данных…')}</span>
          </div>
        )}

        <aside className={`side ${cardOpen ? 'sheet-open' : ''}`}>
          <div
            className="sheet-handle"
            onClick={() => setCardOpen(false)}
            onTouchStart={onHandleTouchStart}
            onTouchMove={onHandleTouchMove}
            role="button"
            aria-label={t('свернуть карточку')}
          />
          <div className="side-tabs" role="tablist">
            <button className={tab === 'territory' ? 'on' : ''} onClick={() => setTab('territory')}>{t('Территория')}</button>
            <button className={tab === 'compare' ? 'on' : ''} onClick={() => setTab('compare')}>
              {t('Сравнение')}{compare.length ? ` (${compare.length})` : ''}
            </button>
            <button className={tab === 'urban' ? 'on' : ''} onClick={() => setTab('urban')}>{t('Урбанизация')}</button>
          </div>
          <div className="side-body">
            {!loaded ? (
              <p className="hint">{t('Загрузка…')}</p>
            ) : tab === 'territory' ? (
              <TerritoryCard
                data={data}
                forecast={forecast}
                scenario={scenario}
                jumpoff={jumpoff}
                id={selected}
                year={year}
                baseYear={baseYear}
                raionMode={raionMode}
                compare={compare}
                onCompareAdd={compareAdd}
                onSelect={select}
              />
            ) : tab === 'compare' ? (
              <ComparePanel
                data={data}
                compare={compare}
                onRemove={(id) => setCompare((c) => c.filter((x) => x !== id))}
              />
            ) : (
              <UrbanPanel data={data} year={year} forecast={forecast} scenario={scenario} />
            )}
          </div>
        </aside>
      </div>

      {data && (
        <TimeBar
          year={year}
          range={[data.yearRange[0], forecast ? forecast.horizon[1] : data.yearRange[1]]}
          censusYears={data.censusYears}
          forecastStart={forecast ? FORECAST_START : null}
          onChange={setYear}
        />
      )}

      {(settingsOpen || cardOpen) && (
        <div
          className="sheet-backdrop"
          onClick={() => { setSettingsOpen(false); setCardOpen(false); }}
        />
      )}
    </div>
  );
}
