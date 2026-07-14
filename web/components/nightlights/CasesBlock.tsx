'use client';

/**
 * Блок «Что здесь не сходится»: карточки исследовательских кандидатов
 * H1–H3. Каждый кейс — гипотеза с уровнем доказательности, а не вывод:
 * наблюдаемое расхождение, период, качество, конкурирующие объяснения,
 * данные для проверки, ссылка на воспроизводимый артефакт.
 */

import { useT, useLang } from '@/lib/i18n';
import type { ResearchCandidate, ExternalCase } from '@/lib/nightlightsV3';
import { fmtPct } from '@/lib/nightlightsV3';

const STATUS_RU: Record<string, string> = {
  candidate: 'кандидат',
  investigating: 'исследуется',
  partially_confirmed: 'подтверждено частично',
  unexplained: 'объяснение не установлено',
};

const CHECK_RU: Record<string, string> = {
  industrial_production_index: 'промпроизводство',
  employment: 'занятость',
  relative_wage: 'зарплата к средней',
  net_migration: 'миграция',
  electricity_production_oblast: 'электроэнергия (область)',
};

const VERDICT_RU: Record<string, string> = {
  consistent: 'согласуется',
  inconsistent: 'расходится',
  context: 'контекст',
};

const HYP_RU: Record<string, string> = {
  commuting_mobility: 'маятниковая мобильность',
  services_logistics: 'услуги и логистика',
  suburbanization_undercount: 'недоучтённая субурбанизация',
  higher_lighting_per_capita: 'выше освещённость на жителя',
  built_area_expansion: 'расширение застройки',
  industrial_load_change: 'изменение промышленной нагрузки',
  lighting_efficiency: 'энергоэффективность/LED',
  population_measurement_lag: 'запаздывание учёта населения',
  industrial_site_lighting_change: 'освещение промплощадки',
  commuting_without_residence: 'занятость без проживания',
  large_infrastructure: 'крупная инфраструктура',
  construction_lighting: 'освещение стройки',
  roads_engineering: 'дороги и инженерные сети',
  services_housing_growth: 'рост услуг и жилья',
  lit_area_expansion_without_population: 'рост следа без роста населения',
};

export default function CasesBlock({ candidates, externalChecks, onOpen }: {
  candidates: ResearchCandidate[];
  externalChecks: Record<string, ExternalCase>;
  onOpen: (c: ResearchCandidate) => void;
}) {
  const t = useT();
  const lang = useLang();
  if (!candidates.length) return null;
  return (
    <div className="chart-block nlv3-cases" id="cases">
      <div className="chart-title">
        <span className="chip chip-interp">{t('Гипотезы')}</span>{' '}
        {t('Что здесь не сходится: кандидаты для следующего исследования')}
      </div>
      <div className="nlv3-cases-grid">
        {candidates.map((c) => (
          <div key={c.id} className="nlv3-case-card">
            <div className="nlv3-case-head">
              <strong>{lang === 'be' ? c.titleBe : c.titleRu}</strong>
              <span className="nlv3-case-status">{t(STATUS_RU[c.status] ?? c.status)}</span>
            </div>
            <p className="nlv3-case-line">
              {c.direction === 'light_above_statistics'
                ? t('свет растёт сильнее статистики населения')
                : t('свет отстаёт от статистики населения')}
              {' · '}{c.period[0]}–{c.period[1]}
            </p>
            {c.releaseApproved && (
              <p className="nlv3-case-metric">
                {t('резидуал')} <strong className={c.metrics.lightResidualPct < 0 ? 'neg' : 'pos'}>
                  {fmtPct(c.metrics.lightResidualPct / 100, 1)}</strong>
                {' '}({c.metrics.metric === 'share' ? t('доли в нац. свете') : t('уровни света')}
                {'; '}{t('альтернативная метрика')}: {fmtPct(c.metrics.altResidualPct / 100, 1)})
              </p>
            )}
            <p className="hint nlv3-case-hyp">
              {t('Гипотезы:')} {c.hypotheses.slice(0, 3).map((h) => t(HYP_RU[h] ?? h)).join(', ')}
            </p>
            <p className="hint nlv3-case-check">{t('Проверить:')} {t(c.checkRu)}</p>
            {externalChecks[c.id] && externalChecks[c.id].checks.length > 0 && (
              <div className="nlv3-case-ext">
                <p className="hint nlv3-case-ext-title">{t('Внешняя проверка (открытая статистика):')}</p>
                <ul className="nlv3-case-ext-list">
                  {externalChecks[c.id].checks.map((ch, i) => (
                    <li key={i} className={`nlv3-ext-${ch.verdict}`}>
                      <span className="nlv3-ext-verdict">{t(VERDICT_RU[ch.verdict])}</span>{' '}
                      {t(CHECK_RU[ch.metric] ?? ch.metric)}
                      {ch.zone && !ch.zone.includes('+') ? ` (${ch.zone})` : ''}:{' '}
                      {ch.value !== null ? `${ch.value > 0 && ch.metric !== 'industrial_production_index' ? '+' : ''}${ch.value}` : t('н/д')}{' '}
                      <span className="nlv3-ext-unit">{t(ch.unit)}</span>
                    </li>
                  ))}
                </ul>
                <p className="hint nlv3-case-ext-note">
                  {t('«Согласуется» — ряд движется в сторону резидуала; это повышает доверие к кейсу, но не устанавливает причину.')}
                </p>
              </div>
            )}
            <div className="nlv3-case-actions">
              <button className="btn" onClick={() => onOpen(c)}>{t('Показать на карте')}</button>
              <a className="btn" href="/artifacts/nightlights" >{t('Артефакт')}</a>
            </div>
          </div>
        ))}
      </div>
      <p className="hint">
        {t('Расхождение — сигнал для проверки, а не причинный вывод: источники могут описывать разные процессы, привычного объяснения может быть недостаточно, возможна и проблема данных. Причина по спутниковым данным не определяется.')}
      </p>
    </div>
  );
}
