'use client';

/** Слайдер лет по индексу узла (годы не равномерны: 2009, 2019, 2026, потом
 *  шаг 5 до 2056) — тот же приём, что и «остановки» PyramidView (INF-11).
 *  Прогнозная зона — штриховка + подпись «прогноз», как в TimeBar/PyramidView
 *  (ТЗ Приложение А: «прогнозная зона слайдера — штриховка + метка»). */

import { useEffect, useRef, useState } from 'react';
import { useT } from '@/lib/i18n';
import { useMedia } from '@/lib/useMedia';

export default function PensionSlider({
  years,
  dtype,
  idx,
  onChange,
}: {
  years: number[];
  dtype: Record<string, string>;
  idx: number;
  onChange: (idx: number) => void;
}) {
  const t = useT();
  const [playing, setPlaying] = useState(false);
  const idxRef = useRef(idx);
  idxRef.current = idx;
  const reduceMotion = useMedia('(prefers-reduced-motion: reduce)');

  const firstForecastIdx = years.findIndex((y) => dtype[String(y)] === 'f');
  const year = years[idx];
  const isForecast = dtype[String(year)] === 'f';

  useEffect(() => {
    if (!playing) return;
    let last = performance.now();
    const raf = { id: 0 };
    const tick = (now: number) => {
      if (now - last > 900) {
        last = now;
        const next = idxRef.current + 1;
        if (next > years.length - 1) { setPlaying(false); return; }
        onChange(next);
      }
      raf.id = requestAnimationFrame(tick);
    };
    raf.id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, years.length]);

  const pct = (i: number) => (i / (years.length - 1)) * 100;

  return (
    <div className="pen-slider-wrap">
      <div className="pyr-controls" style={{ marginBottom: 4 }}>
        <button
          className="play-btn pyr-play"
          aria-label={playing ? t('пауза') : t('воспроизвести')}
          disabled={reduceMotion}
          title={reduceMotion ? t('Анимация отключена: система запрашивает уменьшение движения') : undefined}
          onClick={() => {
            if (!playing && idx >= years.length - 1) onChange(0);
            setPlaying(!playing);
          }}
        >
          <span className="pyr-play-icon">{playing ? '❚❚' : '▶'}</span>
          {playing ? t('Пауза') : t('Проиграть')}
        </button>
        <span className="year-display pen-year">
          {year}
          {isForecast && <span className="forecast-flag">{t('прогноз')}</span>}
        </span>
      </div>
      <div className="pyr-slider pen-slider">
        <input
          className="nlv3-range"
          type="range"
          min={0}
          max={years.length - 1}
          step={1}
          value={idx}
          aria-label={t('год')}
          onChange={(e) => { setPlaying(false); onChange(parseInt(e.target.value, 10)); }}
        />
        <div className="pyr-ticks">
          {years.map((y, i) => (
            <button
              key={y}
              className="pyr-tick"
              style={{ left: `${pct(i)}%` }}
              onClick={() => { setPlaying(false); onChange(i); }}
            >
              {y}
            </button>
          ))}
          {firstForecastIdx >= 0 && (
            <div
              className="pyr-zone-model"
              style={{ left: `${pct(firstForecastIdx)}%` }}
              title={t('Зона прогноза')}
            />
          )}
        </div>
      </div>
    </div>
  );
}
