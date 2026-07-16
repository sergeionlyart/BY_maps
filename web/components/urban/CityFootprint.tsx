'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLang, useT } from '@/lib/i18n';
import {
  CityGrid, CityYearPoint, Story, StoryCase,
  TYPE_COLORS, TYPE_LABELS, decodePng, fmtNum,
} from '@/components/urban/types';

/** Hero INF-12 «Физический след города»: канва-морфинг по 10 эпохам GHSL
 *  (1975–2020, ячейка 100×100 м). Три слоя: доля застройки, возраст входа
 *  в фонд, ночной свет VNL. Промежуточные кадры анимации — визуальная
 *  интерполяция; все расчёты — только по опорным годам. */

type Layer = 'built' | 'age' | 'light';

interface Decoded {
  id: string;
  w: number;
  h: number;
  epochs: number[];
  grids: Uint8Array[];                                 // по эпохам, 0..255 — доля застройки
  entry: Uint8Array;                                   // 255 вне рамки, 0 буфер, 1..10 — эпоха входа
  light: Partial<Record<'vnl2013' | 'vnl2024', Uint8Array>>;
  lightNote: string;
}

interface Rgb { r: number; g: number; b: number }
interface Palette { ink: Rgb; accent: Rgb; accent2: Rgb; muted: Rgb }

const ROLE_LABELS: Record<StoryCase['role'], string> = {
  satellite: 'Спутник Минска',
  monotown: 'Моногород',
  small_center: 'Малый райцентр',
  northeast: 'Северо-восток',
  counterexample: 'Контрпример',
  cluster: 'Кластер',
};

const POP_STATUS: Record<CityYearPoint['popStatus'], string> = {
  census: 'перепись',
  estimate: 'оценка',
  interpolated: 'интерполяция',
  missing: 'нет данных',
};

const STEP_MS = 900;                                   // одна эпоха при воспроизведении
const WARM: Rgb = { r: 247, g: 166, b: 13 };           // тёплый «ночной свет»

/** Вычисленный CSS-цвет (hex/rgb) -> RGB через канву 1×1 (без парсера). */
function cssToRgb(css: string): Rgb {
  const c = document.createElement('canvas');
  c.width = 1; c.height = 1;
  const ctx = c.getContext('2d');
  if (!ctx) return { r: 0, g: 0, b: 0 };
  ctx.fillStyle = '#000';
  const v = css.trim();
  if (v) ctx.fillStyle = v;
  ctx.fillRect(0, 0, 1, 1);
  const d = ctx.getImageData(0, 0, 1, 1).data;
  return { r: d[0], g: d[1], b: d[2] };
}

async function decodeCity(g: CityGrid): Promise<Decoded> {
  const grids = await Promise.all(g.epochs.map((ep) => decodePng(g.grids[String(ep)])));
  const entry = await decodePng(g.entry);
  const lightKeys = (Object.keys(g.light) as ('vnl2013' | 'vnl2024')[])
    .filter((k) => g.light[k]);
  const lightArrs = await Promise.all(lightKeys.map((k) => decodePng(g.light[k])));
  const light: Decoded['light'] = {};
  lightKeys.forEach((k, i) => { light[k] = lightArrs[i].data; });
  return {
    id: g.id, w: g.w, h: g.h, epochs: g.epochs,
    grids: grids.map((x) => x.data), entry: entry.data, light, lightNote: g.lightNote,
  };
}

interface Props {
  story: Story;
  selected: string | null;
  onSelect: (id: string) => void;
}

export default function CityFootprint({ story, selected, onSelect }: Props) {
  const t = useT();
  const lang = useLang();

  const sel = selected && story.cities[selected] ? selected : null;
  const nEp = story.epochs.length;

  const [layer, setLayer] = useState<Layer>('built');
  const [epochIdx, setEpochIdx] = useState(nEp - 1);
  const [playing, setPlaying] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [decoded, setDecoded] = useState<Decoded | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [wrapW, setWrapW] = useState(0);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const cacheRef = useRef<Map<string, Decoded>>(new Map());
  const imgRef = useRef<ImageData | null>(null);
  const palRef = useRef<Palette | null>(null);
  const posRef = useRef(nEp - 1);                      // дробная позиция эпохи (кроссфейд)
  const drawRef = useRef<(pos: number) => void>(() => {});

  // ---- prefers-reduced-motion --------------------------------------------
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const on = () => setReducedMotion(mq.matches);
    on();
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);

  // ---- палитра из токенов страницы (один раз при монтировании) -----------
  useEffect(() => {
    const cs = getComputedStyle(document.body);
    palRef.current = {
      ink: cssToRgb(cs.color),
      accent: cssToRgb(cs.getPropertyValue('--accent')),
      accent2: cssToRgb(cs.getPropertyValue('--accent-2')),
      muted: cssToRgb(cs.getPropertyValue('--muted')),
    };
  }, []);

  // ---- ширина канвы для масштабной линейки --------------------------------
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const w = el.clientWidth;
      if (w > 40) setWrapW(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // ---- ленивая загрузка сетки города + кэш декодированного ---------------
  useEffect(() => {
    if (!sel) return;
    setPlaying(false);
    const cached = cacheRef.current.get(sel);
    if (cached) { setDecoded(cached); setLoadError(false); return; }
    let alive = true;
    setDecoded(null);
    setLoadError(false);
    fetch(`/data/urban/city_${sel}.json`)
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then((g: CityGrid) => decodeCity(g))
      .then((dec) => {
        if (!alive) return;
        cacheRef.current.set(sel, dec);
        setDecoded(dec);
      })
      .catch(() => { if (alive) setLoadError(true); });
    return () => { alive = false; };
  }, [sel]);

  // ---- отрисовка кадра (pos — дробный индекс эпохи) -----------------------
  const draw = useCallback((pos: number) => {
    const dec = decoded;
    const cv = canvasRef.current;
    const pal = palRef.current;
    if (!dec || !cv || !pal) return;
    const ctx = cv.getContext('2d');
    if (!ctx) return;
    const { w, h } = dec;
    const nE = dec.epochs.length;
    const a = Math.max(0, Math.min(Math.floor(pos), nE - 1));
    const b = Math.min(a + 1, nE - 1);
    const f = Math.max(0, Math.min(pos - a, 1));
    let img = imgRef.current;
    if (!img || img.width !== w || img.height !== h) {
      img = ctx.createImageData(w, h);
      imgRef.current = img;
    }
    const px = img.data;
    const ga = dec.grids[a];
    const gb = dec.grids[b];
    const entry = dec.entry;
    const n = w * h;

    if (layer === 'built') {
      // нейтральная шкала: прозрачный -> цвет текста страницы
      const { r, g, b: bl } = pal.ink;
      for (let i = 0; i < n; i++) {
        const v = ga[i] + (gb[i] - ga[i]) * f;
        const o = i * 4;
        px[o] = r; px[o + 1] = g; px[o + 2] = bl;
        px[o + 3] = v <= 0 ? 0 : Math.round(255 * Math.pow(v / 255, 0.65));
      }
    } else if (layer === 'age') {
      // эпоха входа: медь (ядро 1975) -> синий (новое); буфер и вне рамки прозрачны
      const c0 = pal.accent2;
      const c1 = pal.accent;
      for (let i = 0; i < n; i++) {
        const e = entry[i];
        const o = i * 4;
        if (e === 0 || e === 255 || e > b + 1) { px[o + 3] = 0; continue; }
        const tt = (e - 1) / (nE - 1);
        px[o] = Math.round(c0.r + (c1.r - c0.r) * tt);
        px[o + 1] = Math.round(c0.g + (c1.g - c0.g) * tt);
        px[o + 2] = Math.round(c0.b + (c1.b - c0.b) * tt);
        px[o + 3] = e <= a + 1 ? 235 : Math.round(235 * f);
      }
    } else {
      // подложка застройки серым + тёплый ночной свет VNL поверх
      const year = dec.epochs[a] + (dec.epochs[b] - dec.epochs[a]) * f;
      const L = (year <= 2015 ? dec.light.vnl2013 : dec.light.vnl2024)
        ?? dec.light.vnl2024 ?? dec.light.vnl2013 ?? null;
      const grey = pal.muted;
      for (let i = 0; i < n; i++) {
        const v = ga[i] + (gb[i] - ga[i]) * f;
        const ab = v <= 0 ? 0 : 0.45 * Math.pow(v / 255, 0.65);
        const lv = L ? L[i] : 0;
        const ao = lv <= 0 ? 0 : Math.pow(lv / 255, 0.85);
        const outA = ao + ab * (1 - ao);
        const o = i * 4;
        if (outA <= 0.003) { px[o + 3] = 0; continue; }
        px[o] = Math.round((WARM.r * ao + grey.r * ab * (1 - ao)) / outA);
        px[o + 1] = Math.round((WARM.g * ao + grey.g * ab * (1 - ao)) / outA);
        px[o + 2] = Math.round((WARM.b * ao + grey.b * ab * (1 - ao)) / outA);
        px[o + 3] = Math.round(255 * outA);
      }
    }
    ctx.putImageData(img, 0, 0);
  }, [decoded, layer]);
  drawRef.current = draw;

  // перерисовка при смене города/слоя/эпохи (вне анимации)
  useEffect(() => { draw(posRef.current); }, [draw, epochIdx]);

  // ---- воспроизведение: rAF, кроссфейд соседних эпох ----------------------
  useEffect(() => {
    if (!playing) return;
    if (reducedMotion) { setPlaying(false); return; }
    let raf = 0;
    let prev: number | null = null;
    const tick = (ts: number) => {
      if (prev == null) prev = ts;
      const d = (ts - prev) / STEP_MS;
      prev = ts;
      const p = posRef.current + d;
      if (p >= nEp - 1) {
        posRef.current = nEp - 1;
        setEpochIdx(nEp - 1);
        setPlaying(false);
        drawRef.current(nEp - 1);
        return;
      }
      posRef.current = p;
      setEpochIdx(Math.floor(p));
      drawRef.current(p);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, reducedMotion, nEp]);

  const togglePlay = () => {
    if (reducedMotion) return;
    if (playing) {
      const snapped = Math.max(0, Math.min(Math.round(posRef.current), nEp - 1));
      posRef.current = snapped;
      setEpochIdx(snapped);
      setPlaying(false);
    } else {
      if (epochIdx >= nEp - 1) { posRef.current = 0; setEpochIdx(0); }
      setPlaying(true);
    }
  };

  const onSlide = (v: number) => {
    setPlaying(false);
    posRef.current = v;
    setEpochIdx(v);
  };

  // ---- производные ---------------------------------------------------------
  const cityName = (id: string) =>
    lang === 'be' ? story.cities[id]?.be || story.cities[id]?.ru : story.cities[id]?.ru;

  const cityList = useMemo(
    () =>
      Object.values(story.cities)
        .map((c) => ({ id: c.id, name: lang === 'be' ? c.be || c.ru : c.ru }))
        .sort((x, y) => x.name.localeCompare(y.name, lang === 'be' ? 'be' : 'ru')),
    [story, lang],
  );

  const city = sel ? story.cities[sel] : null;
  const year = story.epochs[Math.max(0, Math.min(epochIdx, nEp - 1))];
  const pt = city?.series.find((p) => p.year === year) ?? null;

  const layerLabel =
    layer === 'built' ? t('Застройка') : layer === 'age' ? t('Эпоха появления застройки') : t('Ночной свет');
  // 50 ячеек = 5 км; ширина линейки - от ФАКТИЧЕСКОЙ ширины изображения:
  // canvas растянут CSS width:100% + max-height + object-fit:contain, поэтому
  // контент может быть pillar-boxed (уже обёртки) у высоких сеток
  const scalePx = (() => {
    if (!decoded || wrapW <= 0) return 0;
    const maxH = Math.min(typeof window !== 'undefined' ? window.innerHeight * 0.58 : 560, 560);
    const contentW = Math.min(wrapW, maxH * (decoded.w / decoded.h));
    return (50 / decoded.w) * contentW;
  })();

  return (
    <div className="chart-block">
      {/* -------- выбор города + чипы кейсов -------- */}
      <div className="urban-controls">
        <label className="control-label" htmlFor="uf-city">{t('Город')}</label>
        <select id="uf-city" value={sel ?? ''} onChange={(e) => onSelect(e.target.value)}>
          {!sel && <option value="" disabled hidden>{t('— выберите город —')}</option>}
          {cityList.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        {story.cases.map((c) => (
          <button
            key={`${c.role}-${c.city_id}`}
            type="button"
            className={`btn${c.city_id === sel ? ' primary' : ''}`}
            aria-pressed={c.city_id === sel}
            title={cityName(c.city_id)}
            onClick={() => onSelect(c.city_id)}
          >
            {t(ROLE_LABELS[c.role])}
          </button>
        ))}
        {city && (
          <span
            className="urban-badge"
            style={{ borderColor: TYPE_COLORS[city.type], color: TYPE_COLORS[city.type] }}
            title={t('Тип траектории')}
          >
            {city.type} · {t(TYPE_LABELS[city.type])}
          </span>
        )}
      </div>

      {/* -------- слои + бейджи статуса -------- */}
      <div className="urban-controls">
        <div className="seg urban-seg" role="group" aria-label={t('Слой')}>
          {(['built', 'age', 'light'] as Layer[]).map((l) => (
            <button
              key={l}
              type="button"
              className={layer === l ? 'on' : ''}
              aria-pressed={layer === l}
              onClick={() => setLayer(l)}
            >
              {l === 'built' ? t('Застройка') : l === 'age' ? t('Эпоха появления застройки') : t('Ночной свет')}
            </button>
          ))}
        </div>
        {layer === 'light' && (
          <span className="urban-badge model">{t('VNL ~500 м · грубое разрешение')}</span>
        )}
        {playing && <span className="urban-badge">{t('визуальная интерполяция')}</span>}
      </div>

      {/* -------- канва -------- */}
      <div className="urban-canvas-wrap" ref={wrapRef}>
        {decoded ? (
          <canvas
            ref={canvasRef}
            width={decoded.w}
            height={decoded.h}
            role="img"
            aria-label={`${t('Физический след города')} — ${sel ? cityName(sel) : ''}, ${year}. ${t('Слой')}: ${layerLabel}`}
          />
        ) : (
          <p className="hint" style={{ margin: 0, padding: '28px 16px' }}>
            {loadError ? t('Не удалось загрузить сетку города') : t('Загрузка…')}
          </p>
        )}
      </div>

      {/* -------- легенда активного слоя + масштаб -------- */}
      <div className="urban-legend">
        {layer === 'built' && (
          <>
            <span className="lg">
              <span className="sw" style={{ background: 'var(--ink)', opacity: 0.22 }} />
              {t('редкая застройка')}
            </span>
            <span className="lg">
              <span className="sw" style={{ background: 'var(--ink)' }} />
              {t('сплошная застройка')}
            </span>
          </>
        )}
        {layer === 'age' && (
          <>
            <span className="lg">
              <span className="sw" style={{ background: 'var(--accent-2)' }} />
              {t('ядро — в фонде к 1975')}
            </span>
            <span className="lg">
              <span className="sw" style={{ background: 'var(--accent)' }} />
              {t('новая застройка — вошла к 2020')}
            </span>
          </>
        )}
        {layer === 'light' && (
          <>
            <span className="lg">
              <span className="sw" style={{ background: 'var(--muted)', opacity: 0.5 }} />
              {t('застройка (подложка)')}
            </span>
            <span className="lg">
              <span className="sw" style={{ background: '#f7a60d' }} />
              {t('ночной свет (радианс, лог-шкала)')}
            </span>
          </>
        )}
        {scalePx > 0 && (
          <span className="lg">
            <span
              style={{
                display: 'inline-block',
                width: Math.round(scalePx),
                borderTop: '2px solid var(--muted)',
              }}
            />
            {t('5 км')}
          </span>
        )}
      </div>

      {/* -------- таймлайн -------- */}
      <div className="controls" style={{ marginTop: 10 }}>
        <button
          type="button"
          className="pyr-play"
          onClick={togglePlay}
          disabled={reducedMotion}
          aria-label={playing ? t('Пауза') : t('Проиграть таймлайн')}
          title={reducedMotion ? t('Анимация отключена: система запрашивает уменьшение движения') : undefined}
        >
          <span className="pyr-play-icon">{playing ? '❚❚' : '▶'}</span>
          {playing ? t('Пауза') : `${t('Проиграть')} 1975→2020`}
        </button>
        <span
          className="year-display"
          style={{ fontSize: 26, fontWeight: 700, fontVariantNumeric: 'tabular-nums', minWidth: 62, textAlign: 'center' }}
        >
          {year}
        </span>
        <div className="slider-zone">
          <input
            id="uf-epoch"
            type="range"
            min={0}
            max={nEp - 1}
            step={1}
            value={Math.max(0, Math.min(epochIdx, nEp - 1))}
            aria-label={t('Эпоха GHSL (5-летние шаги, 1975–2020)')}
            aria-valuetext={String(year)}
            onChange={(e) => onSlide(parseInt(e.target.value, 10))}
          />
        </div>
      </div>
      {reducedMotion && (
        <p className="hint">{t('Анимация отключена: система запрашивает уменьшение движения')}</p>
      )}

      {/* -------- счётчики опорного года -------- */}
      <div className="urban-counters">
        <span>{t('Год')}: <b>{year}</b></span>
        <span>
          {t('Население')}: <b>{fmtNum(pt?.pop ?? null, 0)}</b>
          {pt && <> · {t(POP_STATUS[pt.popStatus])}</>}
        </span>
        <span>{t('Застройка, км² (фикс-рамка)')}: <b>{fmtNum(pt?.built ?? null, 2)}</b></span>
        <span>{t('Контур, км²')}: <b>{fmtNum(pt?.footprint ?? null, 1)}</b></span>
        <span>{t('На жителя, м²')}: <b>{fmtNum(pt?.bpc ?? null, 0)}</b></span>
      </div>

      <p className="hint">
        {t('Ячейка 100×100 м, проекция Молльвейде. Промежуточные кадры интерполированы для анимации; расчёты — только по опорным годам.')}
      </p>

      {/* -------- текстовый фолбэк -------- */}
      {city && (
        <details className="urban-fallback">
          <summary>{t('Таблица по опорным годам (текстовая альтернатива анимации)')}</summary>
          <div className="zone-table-wrap">
            <table className="zone-table">
              <thead>
                <tr>
                  <th>{t('Год')}</th>
                  <th>{t('Население')}</th>
                  <th>{t('Статус')}</th>
                  <th>{t('Фонд, км²')}</th>
                  <th>{t('Контур, км²')}</th>
                  <th>{t('м² на жителя')}</th>
                </tr>
              </thead>
              <tbody>
                {city.series.map((p) => (
                  <tr key={p.year}>
                    <td>{p.year}</td>
                    <td>{fmtNum(p.pop, 0)}</td>
                    <td>{t(POP_STATUS[p.popStatus])}</td>
                    <td>{fmtNum(p.built, 2)}</td>
                    <td>{fmtNum(p.footprint, 1)}</td>
                    <td>{fmtNum(p.bpc, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </div>
  );
}
