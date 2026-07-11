'use client';

import { useEffect, useRef, useState } from 'react';
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
import { valueAt, nearestPoint, formatNumber, formatPct, DTYPE_LABEL } from '@/lib/series';
import { colorFor, legendStops, CITY_OVERLAY } from '@/lib/scales';

interface Props {
  data: DataFile;
  geo: { adm1: GeoJSON.FeatureCollection; adm2: GeoJSON.FeatureCollection; border1921: GeoJSON.FeatureCollection };
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
  const { data, geo, year, metric, level, raionMode, baseYear, showBorder1921, showCities, selected, onSelect } = props;
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
      if (s.level === 'city') return ['cities-circle'];
      const base = s.level === 'raion' ? ['adm2-fill'] : ['adm1-fill'];
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

    const adm2visible = level === 'raion';
    const adm1visible = level === 'oblast';
    const citiesVisible = level === 'city' || showCities;
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
        if (t.level === 'oblast' && level !== 'oblast') continue;
        const v = territoryMetric(t.id, stateRef.current);
        map.setFeatureState({ source: src, id: t.id }, {
          color: v == null ? noData : colorFor(metric, level, v, raionMode === 'noCenter'),
        });
      } else if (t.level === 'city' && t.lon != null && citiesVisible) {
        const pop = valueAt(t.pop, year)?.value ?? null;
        const v = territoryMetric(t.id, stateRef.current);
        const overlay = level !== 'city';
        const r = pop == null ? 0 : Math.max(overlay ? 1.8 : 2.2, Math.sqrt(pop) / (overlay ? 110 : 90));
        map.setFeatureState({ source: 'cities', id: t.id }, {
          r,
          color: overlay
            ? (dark ? CITY_OVERLAY.dark : CITY_OVERLAY.light)
            : metric === 'change'
              ? (v == null ? '#9a9891' : colorFor('change', 'city', v))
              : '#2a78d6',
        });
      }
    }
    // Минск-город виден и на уровне районов (полигон в adm2)
    if (level === 'raion') {
      const v = territoryMetric('BY-HM', stateRef.current);
      map.setFeatureState({ source: 'adm2', id: 'BY-HM' }, {
        color: v == null ? noData : colorFor(metric, level, v),
      });
    }

    map.setFilter('selected-line', ['==', ['get', 'id'], level === 'raion' && selected ? selected : '']);
    map.setFilter('selected-line-1', ['==', ['get', 'id'], level === 'oblast' && selected ? selected : '']);
    map.triggerRepaint();
  }, [ready, data, year, metric, level, raionMode, baseYear, showBorder1921, showCities, selected, dark]);

  function territoryMetric(id: string, s: Props): number | null {
    const t = s.data.territories[id];
    if (!t) return null;
    const series = t.level === 'raion' && s.raionMode === 'noCenter' ? t.popNoCenter : t.pop;
    const now = valueAt(series, s.year)?.value ?? null;
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
    const base = valueAt(series, s.baseYear)?.value ?? null;
    if (base == null || base === 0) return null;
    return now / base - 1;
  }

  function renderTooltip(id: string, s: Props): React.ReactNode {
    const t = s.data.territories[id];
    if (!t) return null;
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

  const noCenterScale = level === 'raion' && raionMode === 'noCenter';
  const stops = legendStops(metric, level, noCenterScale);

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
          <div>Размер круга — численность населения города</div>
        ) : (
          stops.map((s) => (
            <div className="lg-row" key={s.label}>
              <span className="lg-swatch" style={{ background: s.color }} />
              {s.label}
            </div>
          ))
        )}
        {showCities && level !== 'city' && (
          <div className="lg-row">
            <span className="lg-circle" />
            город (размер — население)
          </div>
        )}
        {showBorder1921 && (
          <div className="lg-row">
            <span className="lg-line" />
            граница Польша/СССР, 1921–1939
          </div>
        )}
      </div>
    </div>
  );
}

