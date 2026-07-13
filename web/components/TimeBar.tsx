'use client';

import { useEffect, useRef, useState } from 'react';
import { useT } from '@/lib/i18n';

interface Props {
  year: number;
  range: [number, number];
  censusYears: number[];
  /** Год начала прогнозной зоны (визуально отделяется штриховкой). */
  forecastStart?: number | null;
  onChange: (y: number) => void;
}

export default function TimeBar({ year, range, censusYears, forecastStart, onChange }: Props) {
  const t = useT();
  const [playing, setPlaying] = useState(false);
  const raf = useRef<number>(0);
  const yearRef = useRef(year);
  yearRef.current = year;

  useEffect(() => {
    if (!playing) return;
    let last = performance.now();
    const tick = (now: number) => {
      if (now - last > 450) {
        last = now;
        const next = yearRef.current + 1;
        if (next > range[1]) { setPlaying(false); return; }
        onChange(next);
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [playing, onChange, range]);

  const pct = (y: number) => ((y - range[0]) / (range[1] - range[0])) * 100;
  // на узких экранах показываем только эти опорные годы, остальные прячем CSS-ом (U-04)
  const MAJOR = new Set([1897, 1959, 1989, 2019]);

  return (
    <div className="timebar">
      <button
        className="play-btn"
        onClick={() => {
          if (!playing && year >= range[1]) onChange(range[0]);
          setPlaying(!playing);
        }}
        aria-label={playing ? t('пауза') : t('воспроизвести')}
      >
        {playing ? '❚❚' : '▶'}
      </button>
      <div className="year-display">
        {year}
        {forecastStart != null && year > forecastStart && (
          <span className="forecast-flag">{t('прогноз')}</span>
        )}
      </div>
      <div className="slider-zone">
        {forecastStart != null && (
          <div
            className="forecast-zone"
            style={{ left: `${pct(forecastStart)}%`, width: `${100 - pct(forecastStart)}%` }}
            title={t('Зона прогноза')}
          />
        )}
        <input
          type="range"
          min={range[0]}
          max={range[1]}
          step={1}
          value={year}
          onChange={(e) => onChange(+e.target.value)}
          aria-label={t('год')}
        />
        <div className="slider-ticks">
          {censusYears.map((y) => (
            <span
              key={y}
              className={MAJOR.has(y) ? 'tick-major' : 'tick-minor'}
              style={{ left: `${pct(y)}%` }}
              onClick={() => onChange(y)}
            >
              {y}
            </span>
          ))}
          {forecastStart != null && (
            <span key="f" className="tick-forecast" style={{ left: `${pct((forecastStart + range[1]) / 2)}%` }}>
              {t('прогноз →')}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
