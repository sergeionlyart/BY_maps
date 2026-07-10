'use client';

import { useEffect, useRef, useState } from 'react';

interface Props {
  year: number;
  range: [number, number];
  censusYears: number[];
  onChange: (y: number) => void;
}

export default function TimeBar({ year, range, censusYears, onChange }: Props) {
  const [playing, setPlaying] = useState(false);
  const raf = useRef<number>(0);
  const yearRef = useRef(year);
  yearRef.current = year;

  useEffect(() => {
    if (!playing) return;
    let last = performance.now();
    const tick = (now: number) => {
      if (now - last > 180) {
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

  return (
    <div className="timebar">
      <button
        className="play-btn"
        onClick={() => {
          if (!playing && year >= range[1]) onChange(range[0]);
          setPlaying(!playing);
        }}
        aria-label={playing ? 'пауза' : 'воспроизвести'}
      >
        {playing ? '❚❚' : '▶'}
      </button>
      <div className="year-display">{year}</div>
      <div className="slider-zone">
        <input
          type="range"
          min={range[0]}
          max={range[1]}
          step={1}
          value={year}
          onChange={(e) => onChange(+e.target.value)}
          aria-label="год"
        />
        <div className="slider-ticks">
          {censusYears.map((y) => (
            <span key={y} style={{ left: `${pct(y)}%` }} onClick={() => onChange(y)}>
              {y}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
