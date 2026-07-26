'use client';

import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { CentroidPoint } from '@/lib/grid';

const BOUNDS: [[number, number], [number, number]] = [[22.9, 51.1], [33.0, 56.3]];

export interface GridMapProps {
  frameUrl: string | null;
  boundsLonLat: [number, number, number, number] | null; // W,S,E,N
  showBorders: boolean;
  showCentroidTrack: boolean;
  centroidTrack: CentroidPoint[];
  centroidUpToYear: number;
  onMapClick: (lon: number, lat: number) => void;
  adm2: GeoJSON.FeatureCollection | null;
  adm1: GeoJSON.FeatureCollection | null;
}

/** Карта «Полотна»: растровый image-overlay кадра (webp) + опциональные
 *  границы районов (по умолчанию выключены, раздел 3 ТЗ) + опциональный
 *  трек центра масс. Один экземпляр maplibre на весь жизненный цикл
 *  компонента - смена кадра меняет только источник изображения. */
export default function GridMap({
  frameUrl, boundsLonLat, showBorders, showCentroidTrack,
  centroidTrack, centroidUpToYear, onMapClick, adm2, adm1,
}: GridMapProps) {
  const divRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const loadedRef = useRef(false);

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
    map.on('click', (e) => onMapClick(e.lngLat.lng, e.lngLat.lat));

    // Контейнер может изменить размер после инициализации (шрифты,
    // условный рендер тулбара, ресайз окна) - maplibre не отслеживает это
    // сам, нужен явный resize(), иначе канва остаётся маленькой и клики
    // мимо неё не долетают до карты (баг, найденный при ручной проверке).
    const ro = new ResizeObserver(() => map.resize());
    if (divRef.current) ro.observe(divRef.current);
    window.addEventListener('resize', () => map.resize());

    return () => {
      ro.disconnect();
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
          paint: { 'raster-fade-duration': 120 } });
      }
    }

    if (adm2 && !map.getSource('gv-adm2')) {
      map.addSource('gv-adm2', { type: 'geojson', data: adm2 });
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

    const track = centroidTrack.filter((p) => p.year <= centroidUpToYear);
    const trackGeo: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature', properties: {},
          geometry: { type: 'LineString', coordinates: track.map((p) => [p.lon, p.lat]) },
        },
        ...track.map((p) => ({
          type: 'Feature' as const,
          properties: { year: p.year, dtype: p.dtype },
          geometry: { type: 'Point' as const, coordinates: [p.lon, p.lat] },
        })),
      ],
    };
    const trackSrc = map.getSource('gv-centroid') as maplibregl.GeoJSONSource | undefined;
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
    }
    for (const id of ['gv-centroid-line', 'gv-centroid-pts']) {
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', showCentroidTrack ? 'visible' : 'none');
    }
  }

  useEffect(syncLayers);

  return <div ref={divRef} className="gv-map" role="img" aria-label="Карта расселения Беларуси по сетке 1 км" />;
}
