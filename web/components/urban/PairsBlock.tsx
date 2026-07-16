'use client';

import { useMemo, useState } from 'react';
import { useLang, useT } from '@/lib/i18n';
import { fmtNum, ratePct, Story } from '@/components/urban/types';

/** Сопоставленные пары «сокращающийся город - похожий стабильный/растущий»:
 *  таблица с MOR обоих и разрывом. Описательное сравнение (не причинность). */
export default function PairsBlock({ story }: { story: Story }) {
  const t = useT();
  const lang = useLang();
  const [showAll, setShowAll] = useState(false);

  const name = (id: string) =>
    lang === 'be' ? story.cities[id]?.be || story.cities[id]?.ru : story.cities[id]?.ru;

  const rows = useMemo(
    () =>
      [...story.pairs].sort(
        (a, b) => (b.mor_treated - b.mor_control) - (a.mor_treated - a.mor_control),
      ),
    [story.pairs],
  );
  const visible = showAll ? rows : rows.slice(0, 10);
  const gap = story.national.matching.median_mor_gap;

  return (
    <div className="chart-block">
      <div className="stat-row">
        <div className="stat-tile">
          <div className="st-label">{t('сопоставленных пар')}</div>
          <div className="st-value">{story.national.matching.n_pairs}</div>
        </div>
        <div className="stat-tile">
          <div className="st-label">{t('медианный разрыв навеса (MOR), п.п. в год')}</div>
          <div className="st-value">{gap == null ? '—' : fmtNum(gap * 100, 2)}</div>
        </div>
        <div className="stat-tile">
          <div className="st-label">{t('то же за 30 лет интервала')}</div>
          <div className="st-value">{gap == null ? '—' : ratePct(gap, 30)}</div>
        </div>
      </div>
      <div className="zone-table-wrap">
        <table className="zone-table">
          <thead>
            <tr>
              <th>{t('Сокращающийся город')}</th>
              <th>{t('MOR, %/год')}</th>
              <th>{t('Двойник (1990)')}</th>
              <th>{t('MOR двойника')}</th>
              <th>{t('Разрыв')}</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((p) => {
              const d = p.mor_treated - p.mor_control;
              return (
                <tr key={p.treated}>
                  <td>{name(p.treated)}</td>
                  <td>{fmtNum(p.mor_treated * 100, 2)}</td>
                  <td>{name(p.control)}</td>
                  <td>{fmtNum(p.mor_control * 100, 2)}</td>
                  <td className={d > 0 ? 'pos' : 'neg'}>
                    {d > 0 ? '+' : ''}{fmtNum(d * 100, 2)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {rows.length > 10 && (
        <button type="button" className="btn" onClick={() => setShowAll(!showAll)}>
          {showAll ? t('Свернуть') : t('Показать все пары')}
        </button>
      )}
      <p className="hint">
        {t('Подбор: ближайший сосед по стандартизованным признакам 1990 года (лог-население, фонд на жителя, плотность, удалённость от Минска) с калипером по размеру. Разрыв описывает расхождение траекторий при похожем старте — это не причинный эффект депопуляции.')}
        {story.national.matching.sign_test_p != null && (
          <>
            {' '}
            {t('Знаковый тест разрыва по парам: p =')}{' '}
            {fmtNum(story.national.matching.sign_test_p, 3)}
            {t(' — различие статистически неотличимо от нуля на общепринятых уровнях; сравнение остаётся описательным.')}
          </>
        )}
      </p>
    </div>
  );
}
