'use client';

/** SVG-хороплет 118 районов по коэффициенту поддержки (SR). Лёгкая
 *  проекция без MapLibre — тот же приём, что AgingView и MLChallengerView
 *  (простой единственный скалярный показатель на район, без слоёв карты). */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useT } from '@/lib/i18n';
import type { PensionFile, PolicyId, SeriesKey } from '@/lib/pension';
import { valueAt } from '@/lib/pension';
import { srColor } from './scale';
import { ruNum, fillTemplate, type ContentGetter } from '@/lib/pensionContent';
import Markdown from '@/components/Markdown';

interface GeoFeature {
  properties: { id: string };
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][] };
}

export default function PensionMap({
  geo,
  pf,
  names,
  policy,
  seriesKey,
  year,
  selected,
  onSelect,
  C,
}: {
  geo: GeoFeature[];
  pf: PensionFile;
  names: Record<string, string>;
  policy: PolicyId;
  seriesKey: SeriesKey;
  year: number;
  selected: string | null;
  onSelect: (id: string) => void;
  C: ContentGetter;
}) {
  const t = useT();
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    // читаем ширину сразу синхронно, не дожидаясь первого срабатывания
    // ResizeObserver: обнаружено при проверке рилса на проде (2026-07-27) -
    // в части окружений колбэк ResizeObserver ни разу не срабатывает даже
    // при реальном ресайзе окна (воспроизведено и локально, и на проде;
    // компонент этой правкой не затронут - баг был и до неё), из-за чего
    // ширина SVG оставалась на дефолте 640 на мобильном экране уже, чем
    // 640px, - пути карты (посчитаны под 640) вылезали за пределы CSS-
    // подогнанного контейнера и создавали горизонтальную прокрутку
    // страницы. ResizeObserver остаётся - он всё ещё нужен для реакции на
    // последующие изменения размера (поворот экрана и т.п.).
    if (el.clientWidth > 40) setWidth(el.clientWidth);
    const ro = new ResizeObserver(() => el.clientWidth > 40 && setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const { paths, height } = useMemo(() => {
    let minLon = 180, maxLon = -180, minLat = 90, maxLat = -90;
    const eachRing = (f: GeoFeature, cb: (ring: number[][]) => void) => {
      const polys = f.geometry.type === 'Polygon'
        ? [f.geometry.coordinates as number[][][]]
        : (f.geometry.coordinates as number[][][][]);
      for (const poly of polys) for (const ring of poly) cb(ring);
    };
    for (const f of geo) eachRing(f, (ring) => {
      for (const [lon, lat] of ring) {
        if (lon < minLon) minLon = lon; if (lon > maxLon) maxLon = lon;
        if (lat < minLat) minLat = lat; if (lat > maxLat) maxLat = lat;
      }
    });
    const kx = Math.cos(((minLat + maxLat) / 2) * Math.PI / 180);
    const pad = 6;
    const iw = width - pad * 2;
    const scale = iw / ((maxLon - minLon) * kx);
    const h = Math.round((maxLat - minLat) * scale) + pad * 2;
    const X = (lon: number) => pad + (lon - minLon) * kx * scale;
    const Y = (lat: number) => pad + (maxLat - lat) * scale;
    const ps = geo.map((f) => {
      let d = '';
      eachRing(f, (ring) => {
        d += ring.map(([lon, lat], i) =>
          `${i ? 'L' : 'M'}${X(lon).toFixed(1)},${Y(lat).toFixed(1)}`).join('') + 'Z';
      });
      return { id: f.properties.id, d };
    });
    return { paths: ps, height: h };
  }, [geo, width]);

  const valueOf = (id: string): number | null => {
    const entry = pf.territories[id];
    if (!entry) return null;
    return valueAt(entry.sr, pf.years.territory, policy, seriesKey, year);
  };

  const hoverVal = hover ? valueOf(hover.id) : null;

  return (
    <div className="chart-svg-wrap" ref={wrapRef}>
      <svg width={width} height={height} role="img" aria-label={t('карта районов по коэффициенту поддержки')}>
        {paths.map((p) => (
          <path
            key={p.id}
            d={p.d}
            fill={srColor(valueOf(p.id))}
            stroke={p.id === selected ? 'var(--ink)' : 'var(--surface-1)'}
            strokeWidth={p.id === selected ? 1.8 : 0.6}
            style={{ cursor: 'pointer' }}
            onPointerMove={(e) => {
              const box = wrapRef.current!.getBoundingClientRect();
              setHover({ id: p.id, x: e.clientX - box.left, y: e.clientY - box.top });
            }}
            onPointerLeave={() => setHover(null)}
            onClick={() => onSelect(p.id)}
          >
            <title>{`${names[p.id] ?? p.id}${valueOf(p.id) != null ? `: ${valueOf(p.id)!.toFixed(2)}` : ''}`}</title>
          </path>
        ))}
        {paths.filter((p) => p.id === selected).map((p) => (
          <path key={p.id + '-sel'} d={p.d} fill="none" stroke="var(--ink)" strokeWidth="1.8" pointerEvents="none" />
        ))}
      </svg>

      {hover && (
        <div className="chart-tooltip pen-map-tooltip" style={{ left: Math.min(hover.x + 14, width - 220), top: hover.y - 8 }}>
          {hoverVal != null ? (
            <Markdown text={fillTemplate(C.get('micro.tooltip'), {
              district: names[hover.id] ?? hover.id, year, value: ruNum(hoverVal, 2),
            })} />
          ) : (
            <div className="ct-year">{C.get('micro.no-data') || t('нет данных на этот год')}</div>
          )}
        </div>
      )}
    </div>
  );
}
