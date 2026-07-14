'use client';

/**
 * INF-08 v3 «Беларусь из космоса, 1992–2075»: режимы «История» и «Анализ».
 *
 * История — автоплей с адаптивной скоростью (длительности из
 * аналитического событийного слоя), автоматический delta-слой и акценты
 * на событиях, остановки с пояснением на методологических границах.
 * Анализ — слои абсолют/изменение, выбор базы сравнения, A/B со
 * «Показать различия», сценарные отклонения от базового, числа и
 * карточка района. Числа — только из аналитического слоя.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import MethodDrawer from '../MethodDrawer';
import Stage, { type Layer } from './Stage';
import Timeline from './Timeline';
import EventCard from './EventCard';
import LongSpark from './LongSpark';
import { useT, useLang } from '@/lib/i18n';
import { useNlData, stopsOf, frameAsset, deltaAsset, sourceTypeOf,
  fmtPct, type DeltaMode, type NlEvent } from '@/lib/nightlightsV3';

const SCN_LABEL: Record<string, string> = {
  base: 'базовый', negative: 'негативный', optimistic: 'оптимистичный',
};
const JMP_LABEL: Record<string, string> = {
  official: 'официальный', adjusted: 'скорректированный',
};

function useReducedMotion(): boolean {
  const [rm, setRm] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setRm(mq.matches);
    const fn = (e: MediaQueryListEvent) => setRm(e.matches);
    mq.addEventListener('change', fn);
    return () => mq.removeEventListener('change', fn);
  }, []);
  return rm;
}

export default function NightlightsV3View() {
  const t = useT();
  const lang = useLang();
  const data = useNlData(lang);
  const reducedMotion = useReducedMotion();

  const [mode, setMode] = useState<'story' | 'analysis'>('story');
  const [idx, setIdx] = useState(0);
  const [scn, setScn] = useState('base');
  const [jmp, setJmp] = useState('official');
  const [layer, setLayer] = useState<Layer>('abs');
  const [deltaBase, setDeltaBase] = useState<DeltaMode>('prev');
  const [sel, setSel] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [showBorders, setShowBorders] = useState(false);
  const [accents, setAccents] = useState(true);
  const [ab, setAb] = useState(false);
  const [abFrom, setAbFrom] = useState(2012);
  const [abDiff, setAbDiff] = useState(false);
  const [evOverride, setEvOverride] = useState<NlEvent | null>(null);
  const [cardDismissed, setCardDismissed] = useState<number | null>(null);
  const initDone = useRef(false);

  const stops = useMemo(() => (data ? stopsOf(data.night) : []), [data]);
  const year = stops[idx] ?? 2024;
  const isModel = year > 2024;

  // deep-link: чтение при загрузке
  useEffect(() => {
    if (!data || initDone.current) return;
    initDone.current = true;
    const q = new URLSearchParams(window.location.search);
    const wantY = Number(q.get('year'));
    const st = stopsOf(data.night);
    if (wantY) {
      let best = 0, dist = 1e9;
      st.forEach((y, i) => { const d = Math.abs(y - wantY); if (d < dist) { dist = d; best = i; } });
      setIdx(best);
    } else {
      setIdx(data.night.yearsObs.length - 1);
    }
    if (data.night.scenarios.includes(q.get('scenario') ?? '')) setScn(q.get('scenario')!);
    if (data.night.jumpoffs.includes(q.get('jumpoff') ?? '')) setJmp(q.get('jumpoff')!);
    if (q.get('sel')) setSel(q.get('sel'));
    if (q.get('mode') === 'analysis') setMode('analysis');
    const l = q.get('layer');
    if (l === 'delta' || l === 'both' || l === 'abs') setLayer(l);
  }, [data]);

  // deep-link: запись
  useEffect(() => {
    if (!data) return;
    const url = new URL(window.location.href);
    url.searchParams.set('year', String(year));
    url.searchParams.set('scenario', scn);
    url.searchParams.set('jumpoff', jmp);
    url.searchParams.set('mode', mode);
    url.searchParams.set('layer', layer);
    if (sel) url.searchParams.set('sel', sel); else url.searchParams.delete('sel');
    window.history.replaceState(null, '', url);
  }, [data, year, scn, jmp, mode, layer, sel]);

  const evByYear = useMemo(() => {
    const m: Record<number, NlEvent[]> = {};
    if (data) for (const e of data.events.events) (m[e.year] ??= []).push(e);
    return m;
  }, [data]);

  // активное событие года (в Истории и при включённых акцентах)
  const autoEvent = useMemo(() => {
    if (!accents) return null;
    const evs = evByYear[year] ?? [];
    return evs.find((e) => e.kind === 'regional_change')
      ?? evs.find((e) => e.kind !== 'regional_change') ?? null;
  }, [evByYear, year, accents]);
  const activeEvent = evOverride ?? autoEvent;
  const regionalEvent = activeEvent?.kind === 'regional_change' ? activeEvent : null;

  // История: авто-delta на событиях
  const effLayer: Layer = mode === 'story'
    ? (regionalEvent ? 'both' : 'abs')
    : layer;
  const effDeltaBase: DeltaMode = mode === 'story' ? 'prev'
    : (isModel && typeof deltaBase === 'number') ? 'prev' : deltaBase;

  // адаптивное воспроизведение (только История)
  useEffect(() => {
    if (!playing || !data) return;
    const dur = data.events.durationsMs[String(year)] ?? 450;
    const pause = (evByYear[year] ?? []).reduce(
      (a, e) => Math.max(a, e.pauseAfterMs ?? 0), 0);
    const id = window.setTimeout(() => {
      if (idx + 1 >= stops.length) { setPlaying(false); return; }
      setIdx(idx + 1);
    }, dur + pause);
    return () => window.clearTimeout(id);
  }, [playing, idx, data, year, stops.length, evByYear]);

  // префетч соседних кадров (и delta при необходимости)
  useEffect(() => {
    if (!data) return;
    for (let d = -2; d <= 3; d++) {
      const i = idx + d;
      if (i < 0 || i >= stops.length || i === idx) continue;
      const y = stops[i];
      new Image().src = frameAsset(y, data.night, scn, jmp);
      const da = deltaAsset(y, 'prev', data.night, scn, jmp);
      if (da && effLayer !== 'abs') new Image().src = da;
    }
  }, [data, idx, stops, scn, jmp, effLayer]);

  // сброс перекрытий при смене года
  useEffect(() => { setEvOverride(null); setCardDismissed(null); }, [idx]);

  const changeIdx = useCallback((i: number) => setIdx(i), []);
  const onEvent = useCallback((e: NlEvent) => {
    const i = stops.indexOf(e.year);
    if (i >= 0) setIdx(i);
    setEvOverride(e);
    setPlaying(false);
    if (e.regions[0]) setSel(e.regions[0].id);
  }, [stops]);

  if (!data) return <p className="hint">{t('Загрузка данных…')}</p>;

  const { night, manifest, events, annotations, geo, names } = data;
  const rowById: Record<string, (typeof night.rows)[number]> = {};
  for (const r of night.rows) rowById[r.id] = r;
  const rec = sel ? rowById[sel] : null;

  const absSrc = frameAsset(year, night, scn, jmp);
  const deltaSrc = deltaAsset(year, effDeltaBase, night, scn, jmp);
  const srcLabel = manifest.sourceTypeLabels[sourceTypeOf(year)]?.[lang]
    ?? sourceTypeOf(year);
  const modelBadge = isModel
    ? `${t('МОДЕЛЬ')} · ${t(SCN_LABEL[scn])} · ${t('старт')}: ${t(JMP_LABEL[jmp])}`
    : null;

  const abSrcA = mode === 'analysis' && ab
    ? frameAsset(abFrom, night, 'base', jmp) : null;
  const abDiffSrc = mode === 'analysis' && ab && abDiff && !isModel && year !== abFrom
    ? deltaAsset(year, abFrom, night, scn, jmp) : null;

  const showCard = activeEvent && cardDismissed !== year
    && (activeEvent.kind !== 'quality_note' || mode === 'analysis' || evOverride);

  const natNow = isModel
    ? night.natModel[jmp][scn][String(year)]
    : night.natLight[String(year)];
  const scenarioDiff = isModel && scn !== 'base'
    ? natNow / night.natModel[jmp]['base'][String(year)] - 1 : null;

  return (
    <div className="nlv2 nlv3">
      <div className="controls" style={{ marginBottom: 6 }}>
        <div className="seg nlv3-mode" role="tablist">
          <button className={mode === 'story' ? 'on' : ''} role="tab"
            aria-selected={mode === 'story'}
            onClick={() => { setMode('story'); setLayer('abs'); }}>{t('История')}</button>
          <button className={mode === 'analysis' ? 'on' : ''} role="tab"
            aria-selected={mode === 'analysis'}
            onClick={() => { setMode('analysis'); setPlaying(false); }}>{t('Анализ')}</button>
        </div>
        <MethodDrawer slug="nightlights" />
        <a className="btn" href="/artifacts/by-maps-nightlights-v2.1.1.zip" download>
          ⬇ {t('Пакет (ZIP)')}
        </a>
      </div>

      {mode === 'analysis' && (
        <div className="controls nlv3-analysis-controls">
          <span className="hint">{t('Слой:')}</span>
          <div className="seg">
            {(['abs', 'delta', 'both'] as Layer[]).map((l) => (
              <button key={l} className={layer === l ? 'on' : ''} onClick={() => setLayer(l)}>
                {l === 'abs' ? t('Абсолютная яркость') : l === 'delta' ? t('Изменение') : t('Абсолют + изменение')}
              </button>
            ))}
          </div>
          {layer !== 'abs' && !isModel && (
            <>
              <span className="hint">{t('База изменения:')}</span>
              <div className="seg">
                <button className={deltaBase === 'prev' ? 'on' : ''}
                  onClick={() => setDeltaBase('prev')}>{t('пред. год')}</button>
                {manifest.deltas.analysisBases.map((b) => (
                  <button key={b} className={deltaBase === b ? 'on' : ''}
                    onClick={() => setDeltaBase(b)}>{b}</button>
                ))}
              </div>
            </>
          )}
          {layer !== 'abs' && isModel && (
            <>
              <span className="hint">{t('База изменения:')}</span>
              <div className="seg">
                <button className={deltaBase === 'prev' ? 'on' : ''}
                  onClick={() => setDeltaBase('prev')}>{t('пред. узел')}</button>
                <button className={deltaBase === 'base2024' ? 'on' : ''}
                  onClick={() => setDeltaBase('base2024')}>2024</button>
                <button className={deltaBase === 'scenario' ? 'on' : ''}
                  disabled={scn === 'base'}
                  title={scn === 'base' ? t('выберите негативный или оптимистичный сценарий') : undefined}
                  onClick={() => setDeltaBase('scenario')}>{t('сценарий − базовый')}</button>
              </div>
            </>
          )}
          <label className="nlv2-check">
            <input type="checkbox" checked={showBorders} onChange={(e) => setShowBorders(e.target.checked)} />
            {t('границы районов')}
          </label>
          <label className="nlv2-check">
            <input type="checkbox" checked={accents} onChange={(e) => setAccents(e.target.checked)} />
            {t('акценты событий')}
          </label>
          <label className="nlv2-check">
            <input type="checkbox" checked={ab} onChange={(e) => { setAb(e.target.checked); setPlaying(false); }} />
            {t('сравнение A/B')}
          </label>
          {ab && (
            <>
              <span className="hint">A:</span>
              <div className="seg">
                {manifest.deltas.analysisBases.map((y) => (
                  <button key={y} className={abFrom === y ? 'on' : ''}
                    onClick={() => setAbFrom(y)}>{y}</button>
                ))}
              </div>
              <button className={`btn ${abDiff ? 'primary' : ''}`}
                onClick={() => setAbDiff(!abDiff)}>{t('Показать различия')}</button>
            </>
          )}
        </div>
      )}

      <div className="nlv3-stage-wrap">
        <Stage manifest={manifest}
          absSrc={absSrc}
          deltaSrc={abDiffSrc ?? deltaSrc}
          layer={abDiffSrc ? 'both' : effLayer}
          sourceBadge={`${year <= 2024 ? year : ''} ${srcLabel}`.trim()}
          modelBadge={modelBadge}
          geo={geo} names={names} sel={sel}
          onSelect={(id) => setSel(id === sel ? null : id)}
          showBorders={showBorders || mode === 'analysis'}
          event={mode === 'analysis' && !accents ? null : regionalEvent}
          reducedMotion={reducedMotion}
          abSrc={abSrcA} abLabel={String(abFrom)} curLabel={String(year)}
          dirGlyphs={!!regionalEvent} />
        {showCard && activeEvent && (
          <EventCard ev={activeEvent} names={names} annotations={annotations}
            onClose={() => { setEvOverride(null); setCardDismissed(year); }} />
        )}
      </div>

      <Timeline night={night} events={events} stops={stops} idx={idx}
        scn={scn} jmp={jmp} onChange={changeIdx} onEvent={onEvent}
        playing={playing} setPlaying={setPlaying} />

      <div className="controls nlv2-scn">
        <span className="hint">{t('Сценарий модели:')}</span>
        {night.scenarios.map((s) => (
          <button key={s} className={`btn scn-${s} ${scn === s ? 'active' : ''}`}
            onClick={() => setScn(s)}>{t(SCN_LABEL[s])}</button>
        ))}
        <span className="hint" style={{ marginLeft: 10 }}>{t('Стартовый ряд:')}</span>
        {night.jumpoffs.map((j) => (
          <button key={j} className={`btn ${jmp === j ? 'primary' : ''}`}
            onClick={() => setJmp(j)}>{t(JMP_LABEL[j])}</button>
        ))}
        {scenarioDiff != null && (
          <span className="nlv3-scn-diff">
            {t('к базовому сценарию:')} <strong className={scenarioDiff < 0 ? 'neg' : 'pos'}>
              {fmtPct(scenarioDiff, 1)}</strong> {t('нац. света')}
          </span>
        )}
      </div>
      {isModel && (
        <p className="hint nlv3-model-note">
          {t('Модельная визуализация на основе демографического сценария и пространственной структуры освещения базового года.')}
          {' '}{t('Появление новых световых объектов модель не прогнозирует.')}
        </p>
      )}

      {rec && sel && (
        <div className="chart-block">
          <div className="chart-title">
            {names[sel] ?? sel} · <a href={`/map?sel=${sel}`}>{t('на карту')}</a>
            {t(' — доля в свете против доли в населении, 1992–2075')}
          </div>
          <LongSpark row={rec} night={night} scn={scn} jmp={jmp} />
          {rec.div != null && (
            <p className="hint">
              {t('Индекс расхождения 2022–2023 к тренду 2015–2019:')} {rec.div > 0 ? '+' : ''}{(rec.div * 100).toFixed(0)}%.
              {' '}{t('Будущий сегмент кривой — модель (штрих), сценарий')} «{t(SCN_LABEL[scn])}».
            </p>
          )}
        </div>
      )}

      <div className="grid-2" style={{ marginTop: 12 }}>
        <div className="chart-block">
          <div className="chart-title">
            <span className="chip chip-data">{t('Данные')}</span> {t('Три природы данных на одном таймлайне')}
          </div>
          <div className="zone-table-wrap">
            <table className="zone-table">
              <tbody>
                <tr><td><span className="nlv2-dot nlv2-dot-dmsp" /> 1992–2011</td>
                  <td>{t('реконструкция VIIRS-like')}</td>
                  <td>{t('шаблон VIIRS-2012 × зональная динамика гармонизированного ряда DMSP; не наблюдение')}</td></tr>
                <tr><td><span className="nlv2-dot nlv2-dot-vnl" /> 2012–2024</td>
                  <td>{t('спутниковые наблюдения VIIRS')}</td>
                  <td>{t('EOG VNL v2.1, 500 м, радиансность')}</td></tr>
                <tr><td><span className="nlv2-dot nlv2-dot-model" /> 2030–2075</td>
                  <td>{t('модельный прогноз')}</td>
                  <td>{t('иллюстрация прогноза населения v2026.4, не предсказание света')}</td></tr>
              </tbody>
            </table>
          </div>
          <p className="hint">
            {t('Числа, рейтинги и события считаются только по аналитическому слою (гармонизированные зональные ряды); реконструкция отвечает за цельность картинки и не используется для точных локальных выводов.')}
          </p>
        </div>
        <div className="chart-block">
          <div className="chart-title">
            <span className="chip chip-model">{t('Модель')}</span> {t('Иллюстрация будущего, 2030–2075')}
          </div>
          <p className="hint" style={{ fontSize: 14 }}>
            {t('Будущие кадры — не прогноз света и не предсказание. Это ответ на вопрос «как выглядела бы карта света, если бы светимость следовала за населением при прочих равных»: яркая часть света района масштабируется прогнозом населения (v2026.4, три сценария, два стартовых ряда) с межрайонной эластичностью, оценённой по данным; инфраструктурная подсветка (дороги, рассеянный свет) остаётся на месте. Санкции, энергетика, технологии освещения не моделируются. Каждый модельный кадр несёт впечатанный маркер «МОДЕЛЬ», штриховую рамку и подпись сценария — его невозможно выдать за снимок.')}
          </p>
        </div>
      </div>

      <p className="src-note">
        {t('Наблюдения: DMSP-OLS stable lights (калибровка Li et al. 2020, версия 1992–2024) и годовые композиты EOG VIIRS VNL v2.1 (зеркало OpenGeoHub); единая шкала — калибровка-«мост» через перекрытие продуктов simVIIRS/VNL 2014–2024, стык проверен out-of-sample, главная метрика — доля района в национальном свете. Будущее (2030–2075) — модель: светимость следует за прогнозом населения проекта (v2026.4) при прочих равных; санкции, энергетика и технологии освещения не моделируются. Свет ≠ население: расхождения — маркер для разбора, а не оценка численности. Полные оговорки — в методблоке и LIMITATIONS.md пакета.')}
      </p>
    </div>
  );
}
