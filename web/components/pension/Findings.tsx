'use client';

/** Три пререгистрированные гипотезы (docs/preregistration/pension-v0.1.md,
 *  docs/decisions/INF-13.md). Числа считаются здесь же из pension.json (не
 *  вписаны вручную), чтобы не разойтись с данными — база: сценарий
 *  base:official, как заморожено в пререгистрации. Формулировки — по
 *  редакторскому решению в журнале решений (H1: назван Кореличский район,
 *  НЕ «ни одного»; H2: показаны и CV, и SD/размах; H3: названа доля 27/93,
 *  НЕ «ни в одном районе»). */

import { useMemo } from 'react';
import { useT } from '@/lib/i18n';
import type { PensionFile } from '@/lib/pension';

const KEY = 'base:official' as const;

export default function Findings({ pf }: { pf: PensionFile }) {
  const t = useT();

  const stats = useMemo(() => {
    const years = pf.years.territory;
    const i2009 = years.indexOf(2009);
    const i2046 = years.indexOf(2046);
    let below2009 = 0, below2046 = 0;
    let karelickiSr2009: number | null = null;
    let eligible = 0, beyond = 0;
    const shifts: number[] = [];
    for (const [tid, terr] of Object.entries(pf.territories)) {
      const arr = terr.sr.as_is?.[KEY];
      const v2009 = arr?.[i2009] ?? null;
      const v2046 = arr?.[i2046] ?? null;
      if (v2009 != null && v2009 < 1.5) below2009++;
      if (v2046 != null && v2046 < 1.5) below2046++;
      if (tid === 'r-karelicki') karelickiSr2009 = v2009;

      const cAsIs = terr.crossing.as_is?.[KEY]?.['1.5'] ?? null;
      if (cAsIs != null && cAsIs <= 2056) {
        eligible++;
        const cAlt = terr.crossing['65_60']?.[KEY]?.['1.5'] ?? null;
        if (cAlt == null) beyond++;
        else shifts.push(cAlt - cAsIs);
      }
    }
    const meanShift = shifts.length ? shifts.reduce((a, b) => a + b, 0) / shifts.length : 0;
    const disp = pf.national.dispersion_sr;
    return {
      below2009, below2046, karelickiSr2009,
      eligible, beyond, meanShift,
      cv2026: disp?.['2026']?.cv, cv2046: disp?.['2046']?.cv,
      sd2026: disp?.['2026']?.sd, sd2046: disp?.['2046']?.sd,
    };
  }, [pf]);

  return (
    <div className="pen-findings">
      <h2>{t('Три проверенные гипотезы')}</h2>
      <p className="hint">
        {t('Зафиксированы до расчёта (пререгистрация, base:official). Отрицательный результат публикуется так же полно, как подтверждение — раздел 5 ТЗ.')}
      </p>

      <p>
        <span className="chip-tag chip-calc">{t('расчёт')}</span>{' '}
        <strong>{t('H1.')}</strong>{' '}
        {t('К 2046 году порог 1,5 работающих на пожилого проходят')} <strong>{stats.below2046} {t('из 118 районов')}</strong> ({(stats.below2046 / 118 * 100).toFixed(1)}%).
        {' '}{t('В 2009 году порог уже прошёл')} <strong>{stats.below2009} {stats.below2009 === 1 ? t('район') : t('районов')}</strong> —{' '}
        <strong>{t('Кореличский')}</strong>{stats.karelickiSr2009 != null ? ` (SR = ${stats.karelickiSr2009.toFixed(2)})` : ''}, {t('а не ноль, как буквально формулировала гипотеза; это не аномалия расчёта — устойчиво «старый» район по независимым источникам (подробнее — журнал решений).')}
      </p>

      <p>
        <span className="chip-tag chip-calc">{t('расчёт')}</span>{' '}
        <strong>{t('H2.')}</strong>{' '}
        {t('Межрайонный коэффициент вариации SR немного растёт:')} {stats.cv2026?.toFixed(3)} → {stats.cv2046?.toFixed(3)} (2026→2046).{' '}
        {t('Но абсолютный разброс между районами при этом сужается: стандартное отклонение')} {stats.sd2026?.toFixed(3)} → {stats.sd2046?.toFixed(3)}.{' '}
        {t('Страна не столько расслаивается, сколько сходится к более низкому общему уровню поддержки быстрее, чем сжимается разброс вокруг него — обе картины важны, ни одна отдельно не даёт полного вывода.')}
      </p>

      <p>
        <span className="chip-tag chip-calc">{t('расчёт')}</span>{' '}
        <strong>{t('H3.')}</strong>{' '}
        {t('Повышение пенсионного возраста до 65/60 сдвигает год перехода порога 1,5 в среднем на')} {stats.meanShift.toFixed(1)} {t('года — близко к ожидавшимся 8–12 годам для большинства из')} {stats.eligible} {t('районов, где переход наступает при действующем графике до 2056 года.')}{' '}
        {t('Но у')} <strong>{stats.beyond} {t('из')} {stats.eligible} {t('районов')}</strong> ({(stats.beyond / stats.eligible * 100).toFixed(0)}%) {t('переход при графике 65/60 не наступает в пределах горизонта модели (до 2056 года) — то есть для этой части гипотеза «не отменяет переход ни в одном районе» опровергнута собственным критерием пререгистрации. Направление вывода не меняется: настройка сдвигает дату, для части районов — далеко за горизонт расчёта, но это не «навсегда» и не факт вне модели.')}
      </p>
    </div>
  );
}
