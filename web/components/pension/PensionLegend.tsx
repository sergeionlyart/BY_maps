'use client';

/** Легенда карты SR - вынесена из PensionMap отдельным компонентом, чтобы
 *  порядок блоков на странице был: карта -> строка времени -> легенда
 *  (разд. 5 п.4-5 ТЗ handoff/10_pension_ux_copy). На десктопе - полная шкала
 *  всегда; на мобильном - компактные 3 словесные подписи, полная по тапу
 *  (разд. 6 п.5). Слой «Просто» добавляет словесные подписи на краях и у
 *  критической отметки (разд. 7.6); слой «Профессионально» - только числа. */

import { useState } from 'react';
import { useT } from '@/lib/i18n';
import { SR_LEGEND } from './scale';
import type { ContentGetter } from '@/lib/pensionContent';

const WORD_INDEX: Record<number, string> = { 0: 'legend.low', 4: 'legend.mid', 8: 'legend.high' };

export default function PensionLegend({ C }: { C: ContentGetter }) {
  const t = useT();
  const [legendOpen, setLegendOpen] = useState(false);

  return (
    <div className="pen-legend">
      <div className="pen-legend-compact">
        {[0, 4, 8].map((i) => (
          <span className="cl-item" key={i}>
            <span className="cl-swatch" style={{ background: SR_LEGEND[i].color }} />
            {C.get(WORD_INDEX[i]) || t(SR_LEGEND[i].label)}
          </span>
        ))}
        <button type="button" className="pen-legend-toggle" onClick={() => setLegendOpen((v) => !v)} aria-expanded={legendOpen}>
          {legendOpen ? C.get('legend.collapse') : C.get('legend.expand')}
        </button>
      </div>
      <div className={`choro-legend pen-legend-full${legendOpen ? ' pen-legend-open' : ''}`}>
        {SR_LEGEND.map((s, i) => (
          <span className="cl-item" key={s.label}>
            <span className="cl-swatch" style={{ background: s.color }} />
            {WORD_INDEX[i] && C.get(WORD_INDEX[i]) ? `${C.get(WORD_INDEX[i])} · ` : ''}{t(s.label)}
          </span>
        ))}
      </div>
    </div>
  );
}
