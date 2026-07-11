'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

// MapLibre загружает стиль и рендерит через requestAnimationFrame, который в
// скрытых вкладках не срабатывает - карта «зависает» до первого показа.
// Фолбэк: пока документ скрыт, планируем кадры таймером (id < 0, чтобы не
// пересекаться с id rAF).
if (typeof window !== 'undefined') {
  const raf = window.requestAnimationFrame.bind(window);
  const caf = window.cancelAnimationFrame.bind(window);
  window.requestAnimationFrame = (cb: FrameRequestCallback) =>
    document.hidden ? -window.setTimeout(() => cb(performance.now()), 33) : raf(cb);
  window.cancelAnimationFrame = (id: number) => {
    if (id < 0) window.clearTimeout(-id);
    else caf(id);
  };
}
import type { DataFile, Metric, MapLevel, RaionMode } from '@/lib/types';
import type { ForecastFile, ScenarioId, JumpoffId } from '@/lib/forecast';
import { forecastAt, hasAdjusted, FORECAST_START, SCENARIO_LABEL, JUMPOFF_LABEL } from '@/lib/forecast';
import { valueAt, nearestPoint, formatNumber, formatPct, formatCompact, DTYPE_LABEL } from '@/lib/series';
import { colorFor, legendStops, cityColor, cityRadius } from '@/lib/scales';

interface Props {
  data: DataFile;
  geo: { adm1: GeoJSON.FeatureCollection; adm2: GeoJSON.FeatureCollection; border1921: GeoJSON.FeatureCollection };
  forecast: ForecastFile | null;
  scenario: ScenarioId;
  jumpoff?: JumpoffId;
  year: number;
  metric: Metric;
  level: MapLevel;
  raionMode: RaionMode;
  baseYear: number;
  showBorder1921: boolean;
  /** Круги городов поверх хороплета (размер - население города). */
  showCities: boolean;
  selected: string | null;
  onSelect: (id: string | null) => void;
}

const BOUNDS: [[number, number], [number, number]] = [[23.0, 51.15], [32.9, 56.25]];

const METRIC_TITLE: Record<Metric, string> = {
  pop: 'Численность населения',
  density: 'Плотность, чел./км²',
  change: 'Изменение численности',
};

export default function MapView(props: Props) {
  const { data, geo, forecast, scenario, jumpoff = 'official', year, metric, level, raionMode, baseYear, showBorder1921, showCities, selected, onSelect } = props;
  // с этапа 5 прогноз есть на всех уровнях (районы - CCR, города - доли);
  // фолбэк уровня больше не нужен
  const inForecast = forecast != null && year > FORECAST_START;
  const effLevel: MapLevel = level;
  const divRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [ready, setReady] = useState(false);
  const [dark, setDark] = useState(false);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; html: React.ReactNode } | null>(null);
  const stateRef = useRef(props);
  stateRef.current = props;

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    setDark(mq.matches);
    const fn = (e: MediaQueryListEvent) => setDark(e.matches);
    mq.addEventListener('change', fn);
    return () => mq.removeEventListener('change', fn);
  }, []);

  // исторический максимум населения города за весь период (пик Минска) -
  // якорь относительной красной шкалы маркеров
  const maxCityPop = useMemo(
    () => Math.max(...Object.values(data.territories)
      .filter((t) => t.level === 'city')
      .flatMap((t) => Object.values(t.pop).map(([v]) => v))),
    [data],
  );

  // --- инициализация карты (один раз) ------------------------------------
  useEffect(() => {
    if (!divRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: divRef.current,
      style: { version: 8, sources: {}, layers: [] },
      bounds: BOUNDS,
      fitBoundsOptions: { padding: 18 },
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
      minZoom: 4.5,
      maxZoom: 10,
    });
    map.touchZoomRotate.disableRotation();
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');

    map.on('load', () => {
      map.addSource('adm2', { type: 'geojson', data: geo.adm2, promoteId: 'id' });
      map.addSource('adm1', { type: 'geojson', data: geo.adm1, promoteId: 'id' });
      map.addSource('border1921', { type: 'geojson', data: geo.border1921 });

      const cities: GeoJSON.FeatureCollection = {
        type: 'FeatureCollection',
        features: Object.values(data.territories)
          .filter((t) => t.level === 'city' && t.lon != null)
          .map((t) => ({
            type: 'Feature' as const,
            id: t.id,
            properties: { id: t.id },
            geometry: { type: 'Point' as const, coordinates: [t.lon!, t.lat!] },
          })),
      };
      map.addSource('cities', { type: 'geojson', data: cities, promoteId: 'id' });

      for (const src of ['adm2', 'adm1'] as const) {
        map.addLayer({
          id: `${src}-fill`,
          type: 'fill',
          source: src,
          paint: {
            'fill-color': ['coalesce', ['feature-state', 'color'], 'rgba(0,0,0,0)'],
            'fill-opacity': 0.92,
          },
        });
        map.addLayer({
          id: `${src}-line`,
          type: 'line',
          source: src,
          paint: {
            'line-color': '#a3a29a',
            'line-width': src === 'adm1' ? 1.4 : 0.7,
          },
        });
      }
      // контур страны поверх
      map.addLayer({
        id: 'adm1-outer',
        type: 'line',
        source: 'adm1',
        paint: { 'line-color': '#8a887f', 'line-width': 1.2 },
      });
      map.addLayer({
        id: 'selected-line',
        type: 'line',
        source: 'adm2',
        paint: { 'line-color': '#0b0b0b', 'line-width': 2.2 },
        filter: ['==', ['get', 'id'], ''],
      });
      map.addLayer({
        id: 'selected-line-1',
        type: 'line',
        source: 'adm1',
        paint: { 'line-color': '#0b0b0b', 'line-width': 2.4 },
        filter: ['==', ['get', 'id'], ''],
      });
      map.addLayer({
        id: 'border1921-line',
        type: 'line',
        source: 'border1921',
        paint: {
          'line-color': '#7a4a20',
          'line-width': 2,
          'line-dasharray': [3, 2],
        },
        layout: { visibility: 'none' },
      });
      map.addLayer({
        id: 'cities-circle',
        type: 'circle',
        source: 'cities',
        paint: {
          'circle-radius': ['coalesce', ['feature-state', 'r'], 0],
          'circle-color': ['coalesce', ['feature-state', 'color'], '#2a78d6'],
          'circle-opacity': 0.85,
          'circle-stroke-color': '#fcfcfb',
          'circle-stroke-width': 1,
        },
        layout: { visibility: 'none' },
      });

      setReady(true);
    });

    // контейнер получает финальный размер позже создания карты (поздняя
    // раскладка/загрузка CSS): подгоняем канвас и один раз вписываем границы
    let fitted = false;
    const ro = new ResizeObserver(() => {
      map.resize();
      if (!fitted && (divRef.current?.clientWidth ?? 0) > 450) {
        fitted = true;
        map.fitBounds(BOUNDS, { padding: 18, duration: 0 });
      }
    });
    ro.observe(divRef.current);

    // в скрытой вкладке WebGL-кадр может не дорисоваться - поддерживаем
    // перерисовку, пока документ скрыт
    const keepalive = window.setInterval(() => {
      if (document.hidden) map.triggerRepaint();
    }, 300);

    const hitLayers = () => {
      const s = stateRef.current;
      const lv = s.level;
      if (lv === 'city') return ['cities-circle'];
      const base = lv === 'raion' ? ['adm2-fill'] : ['adm1-fill'];
      // при наложении городов круги в приоритете (queryRenderedFeatures
      // возвращает фичи сверху вниз)
      return s.showCities ? ['cities-circle', ...base] : base;
    };

    map.on('mousemove', (e) => {
      const feats = map.queryRenderedFeatures(e.point, { layers: hitLayers().filter((l) => map.getLayer(l)) });
      map.getCanvas().style.cursor = feats.length ? 'pointer' : '';
      if (!feats.length) { setTooltip(null); return; }
      const id = feats[0].properties?.id as string;
      setTooltip({ x: e.point.x, y: e.point.y, html: renderTooltip(id, stateRef.current) });
    });
    map.on('mouseout', () => setTooltip(null));
    map.on('click', (e) => {
      const feats = map.queryRenderedFeatures(e.point, { layers: hitLayers().filter((l) => map.getLayer(l)) });
      stateRef.current.onSelect(feats.length ? (feats[0].properties?.id as string) : null);
    });

    mapRef.current = map;
    if (process.env.NODE_ENV === 'development') {
      (window as unknown as Record<string, unknown>).__map = map;
    }
    return () => { window.clearInterval(keepalive); ro.disconnect(); map.remove(); mapRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- раскраска и видимость слоёв ----------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    const adm2visible = effLevel === 'raion';
    const adm1visible = effLevel === 'oblast';
    const citiesVisible = effLevel === 'city' || showCities;
    for (const [layer, vis] of [
      ['adm2-fill', adm2visible], ['adm2-line', adm2visible],
      ['adm1-fill', adm1visible], ['adm1-line', adm1visible],
      ['cities-circle', citiesVisible],
    ] as const) {
      map.setLayoutProperty(layer, 'visibility', vis ? 'visible' : 'none');
    }
    map.setPaintProperty('cities-circle', 'circle-stroke-color', dark ? '#1a1a19' : '#fcfcfb');
    map.setLayoutProperty('border1921-line', 'visibility', showBorder1921 ? 'visible' : 'none');

    // заливка полигонов
    const noData = dark ? '#242423' : '#e7e6e0';
    for (const t of Object.values(data.territories)) {
      if (t.level === 'raion' || t.level === 'oblast') {
        const src = t.level === 'raion' ? 'adm2' : 'adm1';
        if (t.level === 'oblast' && effLevel !== 'oblast') continue;
        const v = territoryMetric(t.id, stateRef.current);
        map.setFeatureState({ source: src, id: t.id }, {
          color: v == null ? noData : colorFor(metric, effLevel, v, raionMode === 'noCenter'),
        });
      } else if (t.level === 'city' && t.lon != null && citiesVisible) {
        // в прогнозной зоне размер/цвет города ведёт прогноз выбранного
        // сценария; города без прогноза (оборванные ряды) исчезают честно
        const pop = comboPop(t.id, stateRef.current, year);
        const v = territoryMetric(t.id, stateRef.current);
        const overlay = effLevel !== 'city';
        // размер и интенсивность цвета растут и убывают вместе с населением
        map.setFeatureState({ source: 'cities', id: t.id }, {
          r: cityRadius(pop, overlay),
          color: !overlay && metric === 'change'
            ? (v == null ? '#9a9891' : colorFor('change', 'city', v))
            : cityColor(pop, maxCityPop, dark),
        });
      }
    }
    // Минск-город виден и на уровне районов (полигон в adm2)
    if (effLevel === 'raion') {
      const v = territoryMetric('BY-HM', stateRef.current);
      map.setFeatureState({ source: 'adm2', id: 'BY-HM' }, {
        color: v == null ? noData : colorFor(metric, effLevel, v),
      });
    }

    map.setFilter('selected-line', ['==', ['get', 'id'], effLevel === 'raion' && selected ? selected : '']);
    map.setFilter('selected-line-1', ['==', ['get', 'id'], effLevel === 'oblast' && selected ? selected : '']);
    map.triggerRepaint();
  }, [ready, data, year, metric, level, effLevel, inForecast, scenario, forecast, raionMode, baseYear, showBorder1921, showCities, selected, dark, maxCityPop]);

  /** Численность с учётом прогноза: до 2026 - факт/оценка, после - прогноз
   *  выбранного сценария (тип f). */
  function comboPop(id: string, s: Props, yr: number): number | null {
    const t = s.data.territories[id];
    if (s.forecast && yr > FORECAST_START) {
      const v = forecastAt(s.forecast, id, s.scenario, yr, 'pop', s.jumpoff);
      if (v == null) return null;
      // «без центра» в прогнозе: район минус прогнозы его городских центров
      if (t?.level === 'raion' && s.raionMode === 'noCenter') {
        let centers = 0;
        for (const cid of t.center ?? []) {
          const cv = forecastAt(s.forecast, cid, s.scenario, yr, 'pop', s.jumpoff);
          if (cv == null) return null;
          centers += cv;
        }
        return Math.max(v - centers, 0);
      }
      return v;
    }
    if (!t) return null;
    const series = t.level === 'raion' && s.raionMode === 'noCenter' ? t.popNoCenter : t.pop;
    return valueAt(series, yr)?.value ?? null;
  }

  function territoryMetric(id: string, s: Props): number | null {
    const t = s.data.territories[id];
    if (!t) return null;
    const now = comboPop(id, s, s.year);
    if (now == null) return null;
    if (s.metric === 'pop') return now;
    if (s.metric === 'density') {
      if (!t.area) return null;
      let area = t.area;
      // «без центра»: вычитаем известные площади городских центров, чтобы
      // плотность отражала сельскую часть, а не среднее с городом
      if (t.level === 'raion' && s.raionMode === 'noCenter') {
        for (const cid of t.center ?? []) {
          const a = s.data.territories[cid]?.area;
          if (a) area -= a;
        }
        area = Math.max(area, 1);
      }
      return now / area;
    }
    const base = comboPop(id, s, s.baseYear);
    if (base == null || base === 0) return null;
    return now / base - 1;
  }

  function renderTooltip(id: string, s: Props): React.ReactNode {
    const t = s.data.territories[id];
    if (!t) return null;
    // прогнозная зона: значение, интервал и обязательная атрибуция
    if (s.forecast && s.year > FORECAST_START) {
      const v = forecastAt(s.forecast, id, s.scenario, s.year, 'pop', s.jumpoff);
      if (v == null) return <div className="tt-name">{t.ru}: прогноза нет</div>;
      const q10 = forecastAt(s.forecast, id, s.scenario, s.year, 'q10', s.jumpoff);
      const q90 = forecastAt(s.forecast, id, s.scenario, s.year, 'q90', s.jumpoff);
      const m = territoryMetric(id, s);
      return (
        <>
          <div className="tt-name">{t.ru}</div>
          <div className="tt-val">
            <strong>{formatNumber(v)}</strong> чел.
            {s.metric === 'density' && t.area ? <> · {(v / t.area).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} чел./км²</> : null}
            {s.metric === 'change' && m != null ? <> · {m > 0 ? '+' : ''}{formatPct(m)} к {s.baseYear}</> : null}
          </div>
          {q10 != null && q90 != null && (
            <div className="tt-src">80% интервал: {formatCompact(q10)} – {formatCompact(q90)}</div>
          )}
          <div className="tt-src">
            прогноз {s.forecast.version}, сценарий «{SCENARIO_LABEL[s.scenario]}»
            {s.jumpoff === 'adjusted' ? (hasAdjusted(s.forecast, id) ? ', ряд скорректированный' : ', ряд официальный (поправка — до уровня областей)') : ''}
          </div>
        </>
      );
    }
    const series = t.level === 'raion' && s.raionMode === 'noCenter' ? t.popNoCenter : t.pop;
    const res = valueAt(series, s.year);
    const near = nearestPoint(series, s.year);
    const m = territoryMetric(id, s);
    return (
      <>
        <div className="tt-name">{t.ru}</div>
        {res ? (
          <div className="tt-val">
            <strong>{formatNumber(res.value)}</strong> чел.
            {s.metric === 'density' && t.area ? <> · {(res.value / t.area).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} чел./км²</> : null}
            {s.metric === 'change' && m != null ? <> · {m > 0 ? '+' : ''}{formatPct(m)} к {s.baseYear}</> : null}
          </div>
        ) : (
          <div className="tt-val">нет данных на {s.year} год</div>
        )}
        {res && near && (
          <div className="tt-src">
            {res.interpolated ? `интерполяция (ближайшая точка: ${near.year}, ${DTYPE_LABEL[near.dtype]})` : DTYPE_LABEL[near.dtype]}
          </div>
        )}
      </>
    );
  }

  const noCenterScale = effLevel === 'raion' && raionMode === 'noCenter';
  const stops = legendStops(metric, effLevel, noCenterScale);

  return (
    <div className="map-wrap">
      <div ref={divRef} className="map-canvas" />
      {tooltip && (
        <div className="map-tooltip" style={{ left: tooltip.x + 12, top: tooltip.y + 12 }}>
          {tooltip.html}
        </div>
      )}
      <div className="map-legend">
        <div className="lg-title">
          {METRIC_TITLE[metric]}
          {metric === 'change' ? `, % к ${baseYear} г.` : ''}
          {noCenterScale ? ' — без городских центров' : ''}
        </div>
        {level === 'city' && metric !== 'change' ? (
          <CityLegend dark={dark} maxPop={maxCityPop} />
        ) : (
          stops.map((s) => (
            <div className="lg-row" key={s.label}>
              <span className="lg-swatch" style={{ background: s.color }} />
              {s.label}
            </div>
          ))
        )}
        {showCities && effLevel !== 'city' && <CityLegend dark={dark} maxPop={maxCityPop} />}
        {inForecast && (
          <div className="lg-row" style={{ marginTop: 5 }}>
            <span className="lg-line" style={{ borderTopColor: 'var(--accent)' }} />
            прогноз {forecast!.version} · «{SCENARIO_LABEL[scenario]}»{jumpoff === 'adjusted' ? ' · ряд скорр.' : ''}
          </div>
        )}
        {showBorder1921 && (
          <div className="lg-row">
            <span className="lg-line" />
            граница Польша/СССР, 1921–1939
          </div>
        )}
      </div>
      {effLevel === 'raion' && year < 1970 && (
        <div className="map-notice">
          Районный разрез — с 1970 года. Ранняя динамика видна по городам
          {year >= 1959 ? ' и областям' : ''} (уровень «Области» — с 1959 г.).
        </div>
      )}
      {inForecast && jumpoff === 'adjusted' && level !== 'oblast' && (
        <div className="map-notice">
          Скорректированный ряд построен для страны, областей и Минска:
          районы и города показаны по официальному ряду (поправка
          территориально обоснована только до уровня областей).
        </div>
      )}
      {inForecast && level === 'raion' && (
        <div className="map-notice">
          Прогноз районов — Гамильтон–Перри (CCR 2009–2019), согласован с
          областным CCMPP; без доверительных интервалов — смотрите сценарии.
        </div>
      )}
      {inForecast && level === 'city' && (
        <div className="map-notice">
          Прогноз городов — доля в районе (логистический тренд); Минск,
          облцентры и города областного подчинения — когортные модели. Города с рядами,
          оборванными до 2019 г., в прогнозе не показываются.
        </div>
      )}
    </div>
  );
}

/** Мини-легенда городов: размер и интенсивность красного растут с населением;
 *  ярко-красный - исторический максимум (пик Минска). */
function CityLegend({ dark, maxPop }: { dark: boolean; maxPop: number }) {
  const samples = [
    { pop: 10_000, label: '10 тыс.' },
    { pop: 100_000, label: '100 тыс.' },
    { pop: 500_000, label: '500 тыс.' },
    { pop: maxPop, label: 'пик (Минск)' },
  ];
  return (
    <div className="lg-row lg-cities">
      <span style={{ marginRight: 2 }}>город:</span>
      {samples.map((s) => (
        <span className="lg-city-sample" key={s.label}>
          <span
            className="lg-circle"
            style={{
              width: cityRadius(s.pop, true) * 2,
              height: cityRadius(s.pop, true) * 2,
              background: cityColor(s.pop, maxPop, dark),
            }}
          />
          {s.label}
        </span>
      ))}
    </div>
  );
}

