'use client';

import { useMemo } from 'react';
import { useLang, useT } from '@/lib/i18n';
import LineChart, { ChartSeries } from '@/components/LineChart';
import {
  fmtNum,
  Story,
  StoryCity,
  TYPE_LABELS,
} from '@/components/urban/types';

/** Ключ ряда исходных величин города (числитель/знаменатель навеса). */
type SeriesKey = 'pop' | 'built' | 'bpc';

/** Русские подписи ролей ключевых кейсов (общие для интерактивов INF-12). */
const ROLE_LABELS: Record<string, string> = {
  satellite: 'Спутник Минска',
  monotown: 'Моногород',
  small_center: 'Малый райцентр',
  northeast: 'Северо-восток',
  cluster: 'Агломерация',
  counterexample: 'Контрпример',
};

const BASE_YEAR = 1990;

function median(values: number[]): number {
  const s = [...values].sort((a, b) => a - b);
  const n = s.length;
  const m = n >> 1;
  return n % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

/** «Часы материального навеса»: индексы к 1990=100 отдельно для населения,
 *  накопленного фонда и фонда на жителя — чтобы рост «на жителя» не скрывал
 *  свой механизм (растущий фонд при убывающем населении, а не «сжатие»). */
export default function OverhangClock(props: {
  story: Story;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const { story, selected, onSelect } = props;
  const t = useT();
  const lang = useLang();

  const cityName = (c: StoryCity | undefined) =>
    c ? (lang === 'be' ? c.be || c.ru : c.ru) : '';

  // выбранный город: props.selected → первый кейс как фолбэк
  const selectedId =
    selected && story.cities[selected] ? selected : story.cases[0]?.city_id;
  const city = story.cities[selectedId];

  // сокращающиеся города (лог-годовой темп населения < -0.001)
  const declining = useMemo(
    () => Object.values(story.cities).filter((c) => c.main && c.main.pgr < -0.001),
    [story],
  );

  // ряды выбранного города, индексированные к 1990=100
  const citySeries = useMemo<ChartSeries[]>(() => {
    if (!city) return [];
    const build = (
      key: SeriesKey,
      name: string,
      color: string,
      dash?: string,
    ): ChartSeries | null => {
      const base = city.series.find((p) => p.year === BASE_YEAR)?.[key];
      if (base == null || base === 0) return null;
      const points = city.series
        .filter((p) => p[key] != null)
        .map((p) => ({
          year: p.year,
          value: ((p[key] as number) / base) * 100,
          major: p.popStatus === 'census',
        }));
      return points.length ? { name, color, dash, points } : null;
    };
    return [
      build('pop', t('Население'), 'var(--accent)'),
      build('built', t('Накопленный фонд'), 'var(--accent-2)'),
      build('bpc', t('Фонд на жителя'), 'var(--viz-urban)', '6 4'),
    ].filter((s): s is ChartSeries => s != null);
  }, [city, t]);

  // помедианные индексы по сокращающимся городам, по каждой эпохе
  const medianSeries = useMemo<ChartSeries[]>(() => {
    const build = (
      key: SeriesKey,
      name: string,
      color: string,
      dash?: string,
    ): ChartSeries => {
      const points = story.epochs
        .map((epoch) => {
          const vals: number[] = [];
          for (const c of declining) {
            const base = c.series.find((p) => p.year === BASE_YEAR)?.[key];
            if (base == null || base === 0) continue;
            const v = c.series.find((p) => p.year === epoch)?.[key];
            if (v == null) continue;
            vals.push((v / base) * 100);
          }
          return vals.length ? { year: epoch, value: median(vals) } : null;
        })
        .filter((p): p is { year: number; value: number } => p != null);
      return { name, color, dash, points };
    };
    return [
      build('pop', t('Население'), 'var(--accent)'),
      build('built', t('Накопленный фонд'), 'var(--accent-2)'),
      build('bpc', t('Фонд на жителя'), 'var(--viz-urban)', '6 4'),
    ].filter((s) => s.points.length > 0);
  }, [declining, story.epochs, t]);

  // строки таблицы-фолбэка: индексы выбранного города по эпохам
  const tableRows = useMemo(() => {
    if (!city) return [];
    const at = (epoch: number, key: SeriesKey): number | null => {
      const base = city.series.find((p) => p.year === BASE_YEAR)?.[key];
      const v = city.series.find((p) => p.year === epoch)?.[key];
      if (base == null || base === 0 || v == null) return null;
      return (v / base) * 100;
    };
    return story.epochs.map((epoch) => ({
      epoch,
      pop: at(epoch, 'pop'),
      built: at(epoch, 'built'),
      bpc: at(epoch, 'bpc'),
    }));
  }, [city, story.epochs]);

  const cities = useMemo(
    () =>
      Object.values(story.cities)
        .slice()
        .sort((a, b) => cityName(a).localeCompare(cityName(b), 'ru')),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [story, lang],
  );

  const yFormat = (v: number) => fmtNum(v, 0);
  const refY = { value: 100, label: t('1990 = 100') };
  const main = city?.main ?? null;

  return (
    <div className="chart-block">
      {/* ------- выбор кейса и города ------- */}
      <div className="urban-controls">
        <div className="seg urban-seg" role="group" aria-label={t('Ключевые кейсы')}>
          {story.cases.map((cs) => {
            const on = cs.city_id === selectedId;
            const label = t(ROLE_LABELS[cs.role] ?? cs.role);
            const nm = cityName(story.cities[cs.city_id]);
            return (
              <button
                key={cs.role + cs.city_id}
                type="button"
                className={on ? 'on' : ''}
                aria-pressed={on}
                aria-label={`${label}: ${nm}`}
                title={nm}
                onClick={() => onSelect(cs.city_id)}
              >
                {label}
              </button>
            );
          })}
        </div>
        <label>
          {t('Город')}:{' '}
          <select
            aria-label={t('Выбрать город из списка')}
            value={selectedId}
            onChange={(e) => onSelect(e.target.value)}
          >
            {cities.map((c) => (
              <option key={c.id} value={c.id}>
                {cityName(c)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* ------- два графика: выбранный город и медиана ------- */}
      <div className="grid-2">
        <div className="chart-block">
          <h3>{cityName(city)}</h3>
          {citySeries.length > 0 ? (
            <div
              role="img"
              aria-label={`${t(
                'Индексы к 1990 (=100): население, накопленный фонд и фонд на жителя для города',
              )} ${cityName(city)}`}
            >
              <LineChart series={citySeries} yFormat={yFormat} refY={refY} />
            </div>
          ) : (
            <p className="hint">{t('Нет данных для индексов по этому городу')}</p>
          )}
        </div>

        <div className="chart-block">
          <h3>
            {t('Медиана сокращающихся городов')}{' '}
            <span className="hint">({declining.length})</span>
          </h3>
          <div
            role="img"
            aria-label={t(
              'Медианные индексы населения, накопленного фонда и фонда на жителя по сокращающимся городам, 1990 = 100',
            )}
          >
            <LineChart series={medianSeries} yFormat={yFormat} refY={refY} />
          </div>
        </div>
      </div>

      {/* ------- сводные счётчики выбранного города ------- */}
      {main && (
        <div className="urban-counters">
          <span>
            {t('Фонд на жителя')}: <b>{fmtNum(main.bpc1990, 0)}</b> →{' '}
            <b>{fmtNum(main.bpc2020, 0)}</b> {t('м²/чел')}
          </span>
          <span>
            {t('MOR')}: <b>{fmtNum(main.mor * 100, 2)}</b> {t('%/год')},{' '}
            {t('размах сценариев')} [<b>{fmtNum(main.morLo * 100, 2)}</b>;{' '}
            <b>{fmtNum(main.morHi * 100, 2)}</b>], {t('MDC')} ±
            <b>{fmtNum(main.mdc * 100, 2)}</b> {t('%/год')}
          </span>
          <span
            className="urban-badge"
            title={city ? TYPE_LABELS[city.type] : undefined}
          >
            {main.robust
              ? t('знак устойчив: 9 сценариев границ')
              : `${t('знак неустойчив — тип')} ${city?.type ?? ''}`}
          </span>
          {main.morAdmin != null && (
            <span>
              {t('в админ-границах OSM')}: <b>{fmtNum(main.morAdmin * 100, 2)}</b>{' '}
              {t('%/год')}
            </span>
          )}
        </div>
      )}

      <p className="hint">
        {t(
          'Индексы показывают числитель и знаменатель отдельно: рост «на жителя» почти всюду создан ростом фонда при падении населения, а не «сжатием» города.',
        )}
      </p>

      {/* ------- текстовый фолбэк: индексы выбранного города ------- */}
      <details className="urban-fallback">
        <summary>{t('Таблица индексов выбранного города (1990 = 100)')}</summary>
        <div className="zone-table-wrap">
          <table className="zone-table">
            <caption className="sr-only">
              {`${t('Индексы к 1990 (=100): население, накопленный фонд и фонд на жителя для города')} ${cityName(city)}`}
            </caption>
            <thead>
              <tr>
                <th>{t('Год')}</th>
                <th>{t('Население')}</th>
                <th>{t('Накопленный фонд')}</th>
                <th>{t('Фонд на жителя')}</th>
              </tr>
            </thead>
            <tbody>
              {tableRows.map((r) => (
                <tr key={r.epoch}>
                  <td>{r.epoch}</td>
                  <td>{r.pop == null ? '—' : fmtNum(r.pop, 0)}</td>
                  <td>{r.built == null ? '—' : fmtNum(r.built, 0)}</td>
                  <td>{r.bpc == null ? '—' : fmtNum(r.bpc, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
