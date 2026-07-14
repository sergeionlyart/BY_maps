'use client';

/**
 * Информационная карточка события: направление, величина, сила,
 * источник аналитики и качество данных. Причины показываются ТОЛЬКО из
 * ручных аннотаций с источником; иначе — нейтральная формулировка.
 */

import { useT, useLang } from '@/lib/i18n';
import type { Annotations, NlEvent } from '@/lib/nightlightsV3';
import { fmtPct } from '@/lib/nightlightsV3';

const QUALITY_RU: Record<string, string> = {
  clean: 'высокое',
  reconstruction: 'реконструкция (ниже)',
  model: 'модель (не наблюдение)',
  methodological_boundary: 'методологическая граница',
  vnl_processing_step: 'смена обработки продукта',
};

export default function EventCard({ ev, names, annotations, onClose }: {
  ev: NlEvent;
  names: Record<string, string>;
  annotations: Annotations;
  onClose: () => void;
}) {
  const t = useT();
  const lang = useLang();
  const ann = ev.annotationKey ? annotations[ev.annotationKey] : null;
  const annForRegion = ev.regions.find((r) => r.annotationKey);
  const regionAnn = annForRegion?.annotationKey
    ? annotations[annForRegion.annotationKey] : null;
  const anyAnn = ann ?? regionAnn;

  return (
    <div className="nlv3-card" role="status">
      <button className="nlv3-card-close" onClick={onClose} aria-label={t('закрыть')}>×</button>
      {ev.kind === 'regional_change' && ev.regions[0] && (
        <>
          <div className="nlv3-card-title">
            {(names[ev.regions[0].id] ?? ev.regions[0].id)}
            {' · '}
            {ev.regions[0].direction === 'rise' ? t('рост освещения') : t('снижение освещения')}
          </div>
          <div className="nlv3-card-body">
            <div>{t('Изменение к предыдущему сопоставимому году:')} <strong className={ev.regions[0].direction === 'rise' ? 'pos' : 'neg'}>
              {fmtPct(ev.regions[0].annualizedChange, 1)}{t(' в год')}</strong></div>
            <div>{t('Изменение доли в национальном освещении:')} {fmtPct(ev.regions[0].nationalShareDelta, 2)?.replace('%', ' п.п.')}</div>
            <div>{t('Сила события:')} {ev.score != null && ev.score >= 8 ? t('высокая') : t('умеренная')}</div>
            <div>{t('Источник аналитики: гармонизированный временной ряд')}</div>
            <div>{t('Качество данных:')} {t(QUALITY_RU[ev.quality] ?? ev.quality)}</div>
            {ev.regions.length > 1 && (
              <div className="hint">{t('Также:')} {ev.regions.slice(1).map((r) =>
                `${names[r.id] ?? r.id} (${r.direction === 'rise' ? '+' : '−'})`).join(', ')}</div>
            )}
          </div>
        </>
      )}
      {ev.kind === 'national_change' && (
        <>
          <div className="nlv3-card-title">
            {ev.direction === 'rise' ? t('Общенациональный рост освещения') : t('Общенациональное снижение освещения')}
          </div>
          <div className="nlv3-card-body">
            <div>{t('Изменение к предыдущему сопоставимому году:')} <strong>{fmtPct(ev.annualizedChange ?? 0, 1)}{t(' в год')}</strong></div>
            <div>{t('Качество данных:')} {t(QUALITY_RU[ev.quality] ?? ev.quality)}</div>
          </div>
        </>
      )}
      {(ev.kind === 'source_transition' || ev.kind === 'forecast_boundary' || ev.kind === 'quality_note') && (
        <div className="nlv3-card-title">
          {ev.kind === 'source_transition' && t('Смена происхождения данных')}
          {ev.kind === 'forecast_boundary' && t('Граница наблюдений и модели')}
          {ev.kind === 'quality_note' && t('Замечание о качестве данных')}
        </div>
      )}
      {anyAnn ? (
        <p className="nlv3-card-ann">
          {lang === 'be' ? anyAnn.be : anyAnn.ru}{' '}
          <a href={anyAnn.source} target={anyAnn.source.startsWith('/') ? undefined : '_blank'}
            rel="noreferrer">{t('Источник')}</a>
        </p>
      ) : (ev.kind === 'regional_change' || ev.kind === 'national_change') && (
        <p className="nlv3-card-ann hint">
          {t('Зафиксировано выраженное изменение освещения. Причина по спутниковым данным не определяется.')}
        </p>
      )}
    </div>
  );
}
