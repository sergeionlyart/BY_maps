'use client';

/**
 * «Пирамида, которая переворачивается» (INF-11, P-5…P-9): морфинг
 * возрастно-половой структуры 1959–2075.
 *
 * - бары анимируются CSS-транзишеном width (без перерисовки дерева);
 * - слайдер: 1959–2026 погодно, дальше модельная сетка 2030–2075
 *   (штриховка); переписные годы — метки;
 * - после 2026: переключатели сценария и стартового ряда + до трёх
 *   полупрозрачных «призраков» других сценариев;
 * - «найди себя»: год рождения (+пол) → когорта подсвечена и едет
 *   вверх; deep-link ?born=&year=&scenario=;
 * - аннотации A1–A7 всплывают на якорных годах; «▶ рассказ»
 *   проигрывает таймлайн;
 * - тултип бара: численности м/ж, f/m, доля группы, тип кадра.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useT, useLang } from '@/lib/i18n';
import {
  usePyramidData, stopsOf, frameOf, cohortGroup, fmt, fmtK,
  CENSUS_YEARS, TYPE_RU,
  type Scenario, type Jumpoff, type PyramidFrame,
} from '@/lib/pyramid';

const SCN_RU: Record<Scenario, string> = {
  base: 'базовый', optimistic: 'оптимистичный', negative: 'негативный',
};
const SCN_CLASS: Record<Scenario, string> = {
  base: 'scn-base', optimistic: 'scn-opt', negative: 'scn-neg',
};

export interface AnnotationText { title: string; text: string }

export default function PyramidView({ annotations }: {
  annotations: Record<string, AnnotationText>;
}) {
  const t = useT();
  const lang = useLang();
  const data = usePyramidData();

  const [year, setYear] = useState(1959);
  const [scn, setScn] = useState<Scenario>('base');
  const [jo, setJo] = useState<Jumpoff>('official');
  const [born, setBorn] = useState<number | null>(null);
  const [sex, setSex] = useState<'m' | 'f' | null>(null);
  const [playing, setPlaying] = useState(false);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [tip, setTip] = useState<number | null>(null);
  const playRef = useRef<number | null>(null);

  // deep-link: чтение при монтировании
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const y = parseInt(p.get('year') ?? '', 10);
    const b = parseInt(p.get('born') ?? '', 10);
    const s = p.get('scenario') as Scenario | null;
    const j = p.get('jumpoff') as Jumpoff | null;
    if (Number.isFinite(y)) setYear(y);
    if (Number.isFinite(b)) setBorn(b);
    if (s && ['base', 'optimistic', 'negative'].includes(s)) setScn(s);
    if (j && ['official', 'adjusted'].includes(j)) setJo(j);
  }, []);

  // deep-link: запись
  useEffect(() => {
    if (!data) return;
    const url = new URL(window.location.href);
    url.searchParams.set('year', String(year));
    if (born) url.searchParams.set('born', String(born));
    else url.searchParams.delete('born');
    if (year > 2026) {
      url.searchParams.set('scenario', scn);
      if (jo === 'adjusted') url.searchParams.set('jumpoff', jo);
      else url.searchParams.delete('jumpoff');
    } else {
      url.searchParams.delete('scenario');
      url.searchParams.delete('jumpoff');
    }
    window.history.replaceState(null, '', url.toString());
  }, [data, year, scn, jo, born]);

  const stops = useMemo(() => (data ? stopsOf(data) : []), [data]);
  const idx = useMemo(() => {
    if (!stops.length) return 0;
    let best = 0;
    stops.forEach((y, i) => {
      if (Math.abs(y - year) < Math.abs(stops[best] - year)) best = i;
    });
    return best;
  }, [stops, year]);

  // максимум по всему ряду - фиксированная шкала для морфинга
  const maxVal = useMemo(() => {
    if (!data) return 1;
    let m = 0;
    for (const rec of Object.values(data.series)) {
      for (const v of rec.m) m = Math.max(m, v);
      for (const v of rec.f) m = Math.max(m, v);
    }
    return m;
  }, [data]);

  // активные аннотации текущего года
  const activeAnns = useMemo(() => {
    if (!data) return [];
    return data.annotations.filter((a) => a.year === year
      && annotations[a.id] && !dismissed.has(`${a.id}:${year}`));
  }, [data, year, annotations, dismissed]);

  // «рассказ»: шаг по остановкам с паузами на аннотациях
  useEffect(() => {
    if (!playing || !data) return;
    const cur = stops[idx];
    const hasAnn = data.annotations.some((a) => a.year === cur);
    const atEnd = idx >= stops.length - 1;
    if (atEnd) { setPlaying(false); return; }
    const delay = hasAnn ? 3200 : (cur >= 2026 ? 700 : 260);
    playRef.current = window.setTimeout(() => {
      setDismissed(new Set());
      setYear(stops[idx + 1]);
    }, delay);
    return () => {
      if (playRef.current) window.clearTimeout(playRef.current);
    };
  }, [playing, idx, stops, data]);

  if (!data) return <p className="hint">{t('Загрузка…')}</p>;

  const frame = frameOf(data, stops[idx], scn, jo);
  if (!frame) return null;
  const G = data.age_groups;
  const isModel = stops[idx] > 2026;
  const total = frame.m.reduce((a, b) => a + b, 0)
    + frame.f.reduce((a, b) => a + b, 0) + (frame.unknown ?? 0);

  // призраки других сценариев (P-5)
  const ghosts: { scn: Scenario; rec: PyramidFrame }[] = [];
  if (isModel) {
    for (const s of ['base', 'optimistic', 'negative'] as Scenario[]) {
      if (s === scn) continue;
      const rec = frameOf(data, stops[idx], s, jo);
      if (rec) ghosts.push({ scn: s, rec });
    }
  }

  // «найди себя»
  const cg = born != null ? cohortGroup(born, stops[idx]) : null;
  const age = born != null ? stops[idx] - born : null;

  const w = (v: number) => `${(v / maxVal) * 100}%`;

  return (
    <div className="pyr">
      <div className="controls pyr-controls">
        <button className="play-btn" onClick={() => {
          if (!playing && idx >= stops.length - 1) setYear(stops[0]);
          setPlaying(!playing);
        }}>
          {playing ? '❚❚' : '▶'} {t('рассказ')}
        </button>
        <span className="year-display pyr-year">{stops[idx]}</span>
        <span className={`nlv2-badge pyr-badge pyr-badge-${frame.type}`}>
          {t(TYPE_RU[frame.type])}
        </span>
        {isModel && (
          <>
            <div className="seg" role="group" aria-label={t('Сценарий')}>
              {(['optimistic', 'base', 'negative'] as Scenario[]).map((s) => (
                <button key={s} className={`${SCN_CLASS[s]} ${scn === s ? 'on' : ''}`}
                  onClick={() => setScn(s)}>{t(SCN_RU[s])}</button>
              ))}
            </div>
            <div className="seg" role="group" aria-label={t('Стартовый ряд')}>
              <button className={jo === 'official' ? 'on' : ''}
                onClick={() => setJo('official')}>{t('официальный')}</button>
              <button className={jo === 'adjusted' ? 'on' : ''}
                onClick={() => setJo('adjusted')}>{t('скорректированный')}</button>
            </div>
          </>
        )}
      </div>

      <div className="pyr-find controls">
        <label className="hint" htmlFor="pyr-born">{t('Найди себя — год рождения:')}</label>
        <input id="pyr-born" type="number" min={1875} max={2075}
          placeholder="1985" value={born ?? ''}
          onChange={(e) => {
            const v = parseInt(e.target.value, 10);
            setBorn(Number.isFinite(v) ? v : null);
          }} />
        <div className="seg">
          {([null, 'm', 'f'] as const).map((s) => (
            <button key={String(s)} className={sex === s ? 'on' : ''}
              onClick={() => setSex(s)}>
              {s === null ? t('оба') : s === 'm' ? t('муж.') : t('жен.')}
            </button>
          ))}
        </div>
        {born != null && age != null && age < 0 && (
          <span className="hint pyr-notyet">{t('вы ещё не родились')}</span>
        )}
        {born != null && cg != null && (
          <span className="pyr-find-label">
            {stops[idx]} · {t('вам')} {age} · {t('ваша когорта:')}{' '}
            {fmtK(sex ? frame[sex][cg]
              : frame.m[cg] + frame.f[cg])} {t('тыс.')}
            {isModel ? ` (${t('сценарий')} ${t(SCN_RU[scn])})` : ''}
          </span>
        )}
      </div>

      <div className="pyr-stage-wrap">
        <div className="pyr-stage" role="img"
          aria-label={t('Возрастно-половая пирамида,') + ` ${stops[idx]}`}>
          <div className="pyr-head">
            <span>{t('Мужчины')}</span>
            <span className="pyr-head-age">{t('возраст')}</span>
            <span>{t('Женщины')}</span>
          </div>
          {[...G.keys()].reverse().map((gi) => {
            const isCohort = cg === gi;
            const share = (frame.m[gi] + frame.f[gi]) / total;
            return (
              <div key={G[gi]}
                className={`pyr-row ${isCohort ? 'pyr-row-cohort' : ''}`}
                onMouseEnter={() => setTip(gi)}
                onMouseLeave={() => setTip((v) => (v === gi ? null : v))}
                onClick={() => setTip(gi)}>
                <div className="pyr-cell pyr-m">
                  {ghosts.map((g) => (
                    <div key={g.scn}
                      className={`pyr-ghost ${SCN_CLASS[g.scn]}`}
                      style={{ width: w(g.rec.m[gi]) }} />
                  ))}
                  <div className="pyr-bar pyr-bar-m"
                    style={{ width: w(frame.m[gi]) }} />
                </div>
                <div className="pyr-age">{G[gi]}</div>
                <div className="pyr-cell pyr-f">
                  {ghosts.map((g) => (
                    <div key={g.scn}
                      className={`pyr-ghost ${SCN_CLASS[g.scn]}`}
                      style={{ width: w(g.rec.f[gi]) }} />
                  ))}
                  <div className="pyr-bar pyr-bar-f"
                    style={{ width: w(frame.f[gi]) }} />
                </div>
                {tip === gi && (
                  <div className="pyr-tip" role="status">
                    <strong>{G[gi]}</strong> · {t('муж.')} {fmt(frame.m[gi])} ·{' '}
                    {t('жен.')} {fmt(frame.f[gi])}
                    {frame.m[gi] > 0 && (
                      <> · f/m {(frame.f[gi] / frame.m[gi]).toFixed(2)}</>
                    )}
                    {' '}· {(share * 100).toFixed(1)}%{' '}
                    <span className={`pyr-badge pyr-badge-${frame.type}`}>
                      {t(TYPE_RU[frame.type])}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
          {born != null && cg != null && (
            <div className="pyr-cohort-note hint">
              {t('когорта')} {born} {isModel
                ? `· ${t('сценарий')}: ${t(SCN_RU[scn])}` : ''}
            </div>
          )}
        </div>

        {activeAnns.length > 0 && (
          <div className="pyr-ann" role="status">
            {activeAnns.slice(0, 1).map((a) => (
              <div key={a.id} className="pyr-ann-card">
                <button className="nlv3-card-close" aria-label={t('закрыть')}
                  onClick={() => setDismissed(
                    (d) => new Set(d).add(`${a.id}:${year}`))}>×</button>
                <div className="pyr-ann-title">{annotations[a.id].title}</div>
                <div className="pyr-ann-text">{annotations[a.id].text}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="pyr-slider">
        <input className="nlv3-range" type="range" min={0}
          max={stops.length - 1} value={idx}
          aria-label={t('Год')}
          onChange={(e) => {
            setPlaying(false);
            setDismissed(new Set());
            setYear(stops[parseInt(e.target.value, 10)]);
          }} />
        <div className="pyr-ticks">
          {CENSUS_YEARS.map((y) => {
            const i = stops.indexOf(y);
            if (i < 0) return null;
            return (
              <button key={y} className="pyr-tick"
                style={{ left: `${(i / (stops.length - 1)) * 100}%` }}
                onClick={() => { setPlaying(false); setYear(y); }}>
                {y}
              </button>
            );
          })}
          <div className="pyr-zone-model" style={{
            left: `${(stops.indexOf(2030) / (stops.length - 1)) * 100}%`,
          }} title={t('модель')} />
        </div>
      </div>

      <p className="hint pyr-src">
        {t('Итог кадра:')} {fmt(total)} {t('чел.')}
        {frame.unknown ? ` (${t('в т.ч. возраст не указан:')} ${fmt(frame.unknown)})` : ''}
        {' '}· {lang === 'be' ? frame.source : frame.source}
      </p>
    </div>
  );
}
