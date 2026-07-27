'use client';

/** Слайдер лет по индексу узла (годы не равномерны: 2009, 2019, 2026, потом
 *  шаг 5 до 2056) — тот же приём, что и «остановки» PyramidView (INF-11).
 *  Прогнозная зона — штриховка + подпись «прогноз», как в TimeBar/PyramidView
 *  (ТЗ Приложение А: «прогнозная зона слайдера — штриховка + метка»).
 *
 *  INF-13 UX (handoff/10_pension_ux_copy §5 п.4, §6 п.3, §6 п.9): кнопка ▶,
 *  год и сам ползунок теперь один DOM-узел `.pen-timebar` (раньше кнопка
 *  была соседним блоком выше .pyr-slider - на мобильном в липкую панель
 *  внизу попадал только ползунок, не кнопка). При `prefers-reduced-motion`
 *  кнопка больше не блокируется - шаг по годам не «плавная анимация» (нет
 *  CSS-переходов ни на карте, ни на слайдере), просто мгновенная смена
 *  значения по таймеру, поэтому оставляем её рабочей и показываем подпись. */

import { useEffect, useRef, useState } from 'react';
import { useT } from '@/lib/i18n';
import { useMedia } from '@/lib/useMedia';
import type { ContentGetter } from '@/lib/pensionContent';

export default function PensionSlider({
  years,
  dtype,
  idx,
  onChange,
  C,
  firstPlay,
}: {
  years: number[];
  dtype: Record<string, string>;
  idx: number;
  onChange: (idx: number) => void;
  C: ContentGetter;
  /** Слайдер ещё не запускали в этой сессии - показать одноразовую подсказку (§7.5, §8). */
  firstPlay: boolean;
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
    <div className="pen-timebar">
      <button
        className="play-btn pyr-play pen-play"
        aria-label={playing ? (C.get('play.label-playing') || t('пауза')) : (C.get('play.label') || t('воспроизвести'))}
        onClick={() => {
          if (!playing && idx >= years.length - 1) onChange(0);
          setPlaying(!playing);
        }}
      >
        <span className="pyr-play-icon">{playing ? '❚❚' : '▶'}</span>
        {playing ? C.get('play.label-playing') : C.get('play.label')}
      </button>
      <span className="year-display pen-year">
        {year}
        {isForecast && <span className="forecast-flag" title={C.get('micro.forecast-hover')}>{t('прогноз')}</span>}
      </span>
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
      {reduceMotion && (
        <p className="hint pen-reduced-motion-note">{t('Анимация отключена в настройках системы; кадры переключаются без плавности.')}</p>
      )}
      {!reduceMotion && firstPlay && !playing && (
        <p className="hint pen-play-hint">{C.get('play.hint-first')}</p>
      )}
    </div>
  );
}
