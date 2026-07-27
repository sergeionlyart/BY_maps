'use client';

import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { CentroidPoint, Metric } from '@/lib/grid';
import { networkColor } from '@/lib/grid';

const BOUNDS: [[number, number], [number, number]] = [[22.9, 51.1], [33.0, 56.3]];

export interface GridMapProps {
  frameUrl: string | null;
  boundsLonLat: [number, number, number, number] | null; // W,S,E,N
  metric: Metric;
  networkValues: Record<string, number | null> | null;
  reducedMotion: boolean;
  showBorders: boolean;
  showCentroidTrack: boolean;
  centroidTrack: CentroidPoint[];
  centroidUpToYear: number;
  onMapClick: (lon: number, lat: number) => void;
  onTerritoryClick: (id: string) => void;
  adm2: GeoJSON.FeatureCollection | null;
  adm1: GeoJSON.FeatureCollection | null;
}

/** Карта «Полотна»: растровый image-overlay кадра (webp) + опциональные
 *  границы районов (по умолчанию выключены, раздел 3 ТЗ) + опциональный
 *  трек центра масс + хороплет «метры сети на жителя» (B-2, часть 1) поверх
 *  приглушённого растра. Один экземпляр maplibre на весь жизненный цикл
 *  компонента - смена кадра меняет только источник изображения. */
export default function GridMap({
  frameUrl, boundsLonLat, metric, networkValues, reducedMotion, showBorders, showCentroidTrack,
  centroidTrack, centroidUpToYear, onMapClick, onTerritoryClick, adm2, adm1,
}: GridMapProps) {
  const divRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const loadedRef = useRef(false);
  // B-3: обработчик клика регистрируется один раз при монтировании карты -
  // без ref он навсегда захватывает пропсы первого рендера (замыкание),
  // и клик по клетке всегда возвращал бы число года первого рендера
  // независимо от положения ползунка.
  const onMapClickRef = useRef(onMapClick);
  onMapClickRef.current = onMapClick;
  const onTerritoryClickRef = useRef(onTerritoryClick);
  onTerritoryClickRef.current = onTerritoryClick;
  const metricRef = useRef(metric);
  metricRef.current = metric;

  useEffect(() => {
    if (!divRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: divRef.current,
      style: { version: 8, sources: {}, layers: [] },
      bounds: BOUNDS,
      fitBoundsOptions: { padding: 16 },
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
      minZoom: 4.5,
      maxZoom: 10,
    });
    map.touchZoomRotate.disableRotation();
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    map.on('load', () => {
      loadedRef.current = true;
      mapRef.current = map;
      map.resize();
      syncLayers();
    });
    map.on('click', (e) => {
      if (metricRef.current === 'network') {
        const feats = map.queryRenderedFeatures(e.point, {
          layers: [map.getLayer('gv-adm2-fill') ? 'gv-adm2-fill' : ''].filter(Boolean),
        });
        const id = feats[0]?.properties?.id as string | undefined;
        if (id) { onTerritoryClickRef.current(id); return; }
      }
      onMapClickRef.current(e.lngLat.lng, e.lngLat.lat);
    });

    // Контейнер может изменить размер после инициализации (шрифты,
    // условный рендер тулбара, ресайз окна) - maplibre не отслеживает это
    // сам, нужен явный resize(), иначе канва остаётся маленькой и клики
    // мимо неё не долетают до карты (баг, найденный при ручной проверке).
    const ro = new ResizeObserver(() => map.resize());
    if (divRef.current) ro.observe(divRef.current);
    const onWinResize = () => map.resize();
    window.addEventListener('resize', onWinResize);

    return () => {
      ro.disconnect();
      window.removeEventListener('resize', onWinResize);
      map.remove();
      mapRef.current = null;
      loadedRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function syncLayers() {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;

    if (frameUrl && boundsLonLat) {
      const [w, s, e, n] = boundsLonLat;
      const coords: [[number, number], [number, number], [number, number], [number, number]] = [
        [w, n], [e, n], [e, s], [w, s],
      ];
      const src = map.getSource('grid-frame') as maplibregl.ImageSource | undefined;
      if (src) {
        src.updateImage({ url: frameUrl, coordinates: coords });
      } else {
        map.addSource('grid-frame', { type: 'image', url: frameUrl, coordinates: coords });
        map.addLayer({ id: 'grid-frame-layer', type: 'raster', source: 'grid-frame',
          paint: { 'raster-fade-duration': reducedMotion ? 0 : 120 } });
      }
    }
    // «Метры сети на жителя» - снимок одного года, кадров растра нет:
    // хороплет районов рисуется поверх приглушённого (не скрытого)
    // растра последнего просмотренного кадра, для географического контекста.
    if (map.getLayer('grid-frame-layer')) {
      map.setPaintProperty('grid-frame-layer', 'raster-opacity', metric === 'network' ? 0.25 : 1);
      map.setPaintProperty('grid-frame-layer', 'raster-fade-duration', reducedMotion ? 0 : 120);
    }

    if (adm2 && !map.getSource('gv-adm2')) {
      map.addSource('gv-adm2', { type: 'geojson', data: adm2, promoteId: 'id' });
      map.addLayer({ id: 'gv-adm2-fill', type: 'fill', source: 'gv-adm2',
        paint: { 'fill-color': ['coalesce', ['feature-state', 'color'], 'rgba(0,0,0,0)'],
          'fill-opacity': metric === 'network' ? 0.88 : 0 } });
      map.addLayer({ id: 'gv-adm2-line', type: 'line', source: 'gv-adm2',
        paint: { 'line-color': '#d8d6cc', 'line-width': 0.8, 'line-opacity': showBorders ? 0.85 : 0 } });
    }
    if (adm1 && !map.getSource('gv-adm1')) {
      map.addSource('gv-adm1', { type: 'geojson', data: adm1 });
      map.addLayer({ id: 'gv-adm1-line', type: 'line', source: 'gv-adm1',
        paint: { 'line-color': '#a3a29a', 'line-width': 1.3, 'line-opacity': showBorders ? 0.9 : 0 } });
    }
    if (map.getLayer('gv-adm2-line')) {
      map.setPaintProperty('gv-adm2-line', 'line-opacity', showBorders ? 0.85 : 0);
    }
    if (map.getLayer('gv-adm1-line')) {
      map.setPaintProperty('gv-adm1-line', 'line-opacity', showBorders ? 0.9 : 0);
    }
    if (map.getLayer('gv-adm2-fill')) {
      map.setPaintProperty('gv-adm2-fill', 'fill-opacity', metric === 'network' ? 0.88 : 0);
      if (metric === 'network' && networkValues) {
        for (const [id, v] of Object.entries(networkValues)) {
          map.setFeatureState({ source: 'gv-adm2', id }, { color: networkColor(v) });
        }
      }
    }

    const track = centroidTrack.filter((p) => p.year <= centroidUpToYear);
    const KEY_YEARS = new Set([1897, 1970, 1975, 2020, 2050]);
    const trackGeo: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature', properties: {},
          geometry: { type: 'LineString', coordinates: track.map((p) => [p.lon, p.lat]) },
        },
        ...track.map((p, i) => ({
          type: 'Feature' as const,
          properties: {
            year: p.year, dtype: p.dtype,
            labeled: KEY_YEARS.has(p.year) || i === track.length - 1,
          },
          geometry: { type: 'Point' as const, coordinates: [p.lon, p.lat] },
        })),
      ],
    };
    const corridorGeo: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: corridorSegments(track) };

    const trackSrc = map.getSource('gv-centroid') as maplibregl.GeoJSONSource | undefined;
    const corridorSrc = map.getSource('gv-corridor') as maplibregl.GeoJSONSource | undefined;
    if (corridorSrc) {
      corridorSrc.setData(corridorGeo);
    } else {
      map.addSource('gv-corridor', { type: 'geojson', data: corridorGeo });
      map.addLayer({ id: 'gv-corridor-fill', type: 'fill', source: 'gv-corridor',
        paint: { 'fill-color': '#e0663f', 'fill-opacity': 0.14 } },
        map.getLayer('gv-adm2-line') ? 'gv-adm2-line' : undefined);
    }
    if (trackSrc) {
      trackSrc.setData(trackGeo);
    } else if (track.length) {
      map.addSource('gv-centroid', { type: 'geojson', data: trackGeo });
      map.addLayer({ id: 'gv-centroid-line', type: 'line', source: 'gv-centroid',
        filter: ['==', ['geometry-type'], 'LineString'],
        paint: { 'line-color': '#e0663f', 'line-width': 2, 'line-dasharray': [1, 1] } });
      map.addLayer({ id: 'gv-centroid-pts', type: 'circle', source: 'gv-centroid',
        filter: ['==', ['geometry-type'], 'Point'],
        paint: { 'circle-radius': 4, 'circle-color': '#e0663f', 'circle-stroke-width': 1.5,
          'circle-stroke-color': '#fff' } });
      map.addLayer({ id: 'gv-centroid-labels', type: 'symbol', source: 'gv-centroid',
        filter: ['all', ['==', ['geometry-type'], 'Point'], ['==', ['get', 'labeled'], true]],
        layout: { 'text-field': ['get', 'year'], 'text-size': 11, 'text-offset': [0, 1.1], 'text-anchor': 'top' },
        paint: { 'text-color': '#7a3a1f', 'text-halo-color': '#fff', 'text-halo-width': 1.4 } });
    }
    for (const id of ['gv-corridor-fill', 'gv-centroid-line', 'gv-centroid-pts', 'gv-centroid-labels']) {
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', showCentroidTrack ? 'visible' : 'none');
    }
  }

  // B-5: автозум/врезка на область трека при включении кнопки «Центр масс
  // населения» - на масштабе всей страны сдвиг в единицы км физически не
  // виден. Зум считается по ПОЛНОМУ треку (1897-2050), не только по видимой
  // за текущий год части - иначе картинка дёргалась бы при каждом шаге
  // ползунка. Срабатывает только на фронте включения/выключения кнопки.
  const prevShowTrack = useRef(false);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    if (showCentroidTrack === prevShowTrack.current) return;
    prevShowTrack.current = showCentroidTrack;
    if (showCentroidTrack && centroidTrack.length) {
      const lons = centroidTrack.map((p) => p.lon);
      const lats = centroidTrack.map((p) => p.lat);
      map.fitBounds(
        [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
        { padding: 120, duration: 500, maxZoom: 9 },
      );
    } else {
      map.fitBounds(BOUNDS, { padding: 16, duration: 500 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showCentroidTrack]);

  useEffect(syncLayers);

  return <div ref={divRef} className="gv-map" role="img" aria-label="Карта расселения Беларуси по сетке 1 км" />;
}

/** Полупрозрачная лента коридора погрешности вокруг трека: по сегменту
 *  между соседними точками, ширина с каждой стороны - собственный err_km
 *  этой точки (честно - не усредняем точную ±10 км эпоху с грубой ±40 км
 *  оценкой 1897 года). Меньше двух точек - коридора нет (замкнутая точка). */
function corridorSegments(track: { lon: number; lat: number; err_km: number }[]): GeoJSON.Feature[] {
  if (track.length < 2) return [];
  const feats: GeoJSON.Feature[] = [];
  for (let i = 0; i < track.length - 1; i++) {
    const a = track[i], b = track[i + 1];
    const latMid = (a.lat + b.lat) / 2;
    const mPerDegLat = 111320;
    const mPerDegLon = 111320 * Math.cos((latMid * Math.PI) / 180);
    const dx = (b.lon - a.lon) * mPerDegLon;
    const dy = (b.lat - a.lat) * mPerDegLat;
    const len = Math.hypot(dx, dy) || 1;
    const px = -dy / len, py = dx / len; // единичный перпендикуляр
    const offset = (p: { lon: number; lat: number; err_km: number }, sign: 1 | -1) => {
      const m = p.err_km * 1000 * sign;
      return [p.lon + (px * m) / mPerDegLon, p.lat + (py * m) / mPerDegLat];
    };
    feats.push({
      type: 'Feature', properties: {},
      geometry: { type: 'Polygon', coordinates: [[
        offset(a, 1), offset(b, 1), offset(b, -1), offset(a, -1), offset(a, 1),
      ]] },
    });
  }
  return feats;
}
