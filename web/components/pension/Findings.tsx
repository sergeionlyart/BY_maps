'use client';

/** Три пререгистрированные гипотезы (docs/preregistration/pension-v0.1.md,
 *  docs/decisions/INF-13.md). Числа считаются здесь же из pension.json (не
 *  вписаны вручную), чтобы не разойтись с данными — база: сценарий
 *  base:official, как заморожено в пререгистрации. Формулировки — по
 *  редакторскому решению в журнале решений (H1: назван Кореличский район,
 *  НЕ «ни одного»; H2: показаны и CV, и SD/размах; H3: названа доля 27/93,
 *  НЕ «ни в одном районе»).
 *
 *  INF-13 UX: проза («Вывод 1/2/3», их заголовки и текст) вынесена в
 *  контент-файлы (pension.<layer>.<lang>.md, разд. 7.10 ТЗ) - расчёт stats
 *  здесь не меняется, меняется только то, как числа подставляются в текст. */

import { useMemo } from 'react';
import { useT } from '@/lib/i18n';
import type { PensionFile } from '@/lib/pension';
import { countBelowThreshold } from '@/lib/pension';
import { ruNum, fillTemplate, type ContentGetter } from '@/lib/pensionContent';
import Markdown from '@/components/Markdown';

const KEY = 'base:official' as const;

export default function Findings({ pf, C }: { pf: PensionFile; C: ContentGetter }) {
  const t = useT();

  const stats = useMemo(() => {
    const years = pf.years.territory;
    const i2009 = years.indexOf(2009);
    let below2009 = 0;
    let karelickiSr2009: number | null = null;
    let eligible = 0, beyond = 0;
    const shifts: number[] = [];
    for (const [tid, terr] of Object.entries(pf.territories)) {
      const arr = terr.sr.as_is?.[KEY];
      const v2009 = arr?.[i2009] ?? null;
      if (v2009 != null && v2009 < 1.5) below2009++;
      if (tid === 'r-karelicki') karelickiSr2009 = v2009;

      const cAsIs = terr.crossing.as_is?.[KEY]?.['1.5'] ?? null;
      if (cAsIs != null && cAsIs <= 2056) {
        eligible++;
        const cAlt = terr.crossing['65_60']?.[KEY]?.['1.5'] ?? null;
        if (cAlt == null) beyond++;
        else shifts.push(cAlt - cAsIs);
      }
    }
    const { below: below2046, total } = countBelowThreshold(pf, 1.5, 2046, KEY);
    const meanShift = shifts.length ? shifts.reduce((a, b) => a + b, 0) / shifts.length : 0;
    const disp = pf.national.dispersion_sr;
    return {
      below2009, below2046, total, karelickiSr2009,
      eligible, beyond, meanShift,
      cv2026: disp?.['2026']?.cv, cv2046: disp?.['2046']?.cv,
      sd2026: disp?.['2026']?.sd, sd2046: disp?.['2046']?.sd,
    };
  }, [pf]);

  const share2046 = ruNum((stats.below2046 / stats.total) * 100, 1);
  const beyondShare = stats.eligible ? ruNum((stats.beyond / stats.eligible) * 100, 0) : '—';
  const karelicki = ruNum(stats.karelickiSr2009, 2);
  const meanShift = ruNum(stats.meanShift, 1);

  const vars = {
    below2046: stats.below2046,
    total: stats.total,
    share2046,
    below2009: stats.below2009,
    below2009word: t(stats.below2009 === 1 ? 'район' : 'районов'),
    karelicki,
    karelickiSuffix: stats.karelickiSr2009 != null ? ` (SR = ${karelicki})` : '',
    meanShift,
    beyond: stats.beyond,
    eligible: stats.eligible,
    beyondShare,
    cv2026: ruNum(stats.cv2026, 3),
    cv2046: ruNum(stats.cv2046, 3),
    sd2026: ruNum(stats.sd2026, 3),
    sd2046: ruNum(stats.sd2046, 3),
  };

  return (
    <div className="pen-findings">
      <h2>{C.get('findings.title')}</h2>
      <Markdown text={C.get('findings.intro', vars)} />

      <section className="pen-finding">
        <h3>{fillTemplate(C.get('findings.h1-title'), vars)}</h3>
        <Markdown text={fillTemplate(C.get('findings.h1-body.p1'), vars)} />
        <Markdown text={fillTemplate(C.get('findings.h1-body.p2'), vars)} />
      </section>

      <section className="pen-finding">
        <h3>{fillTemplate(C.get('findings.h2-title'), vars)}</h3>
        <Markdown text={fillTemplate(C.get('findings.h2-body.p1'), vars)} />
        <Markdown text={fillTemplate(C.get('findings.h2-body.p2'), vars)} />
      </section>

      <section className="pen-finding">
        <h3>{fillTemplate(C.get('findings.h3-title'), vars)}</h3>
        <Markdown text={fillTemplate(C.get('findings.h3-body.p1'), vars)} />
        <Markdown text={fillTemplate(C.get('findings.h3-body.p2'), vars)} />
      </section>
    </div>
  );
}
