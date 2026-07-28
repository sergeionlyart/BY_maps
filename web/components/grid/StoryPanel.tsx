'use client';

import { interpolate } from '@/lib/gridStoryContent';
import type { Scenario, Variant } from '@/lib/grid';
import { useT } from '@/lib/i18n';

const SCN_RU: Record<Scenario, string> = { base: 'базовый', optimistic: 'оптимистичный', negative: 'негативный' };

export interface StoryPanelProps {
  step: number; // 1-7
  content: Record<string, string> | null;
  values: Record<string, string | number>;
  onNext: () => void;
  onPrev: () => void;
  onShare: () => void;
  step4Part: 'se' | 'west';
  onShowSecondPart: () => void;
  scenario: Scenario;
  variant: Variant;
  onScenario: (s: Scenario) => void;
  onVariant: (v: Variant) => void;
  onFreeMode: () => void;
}

/** Панель шага режима «История» (INF-15 v2) - номер, заголовок, текст,
 *  навигация. Текст читается из web/public/content/research/
 *  grid-story.{ru,be}.md через web/lib/gridStoryContent.ts, числа в нём -
 *  {{токены}} из web/lib/gridStory.ts::buildStoryValues (условие брифа:
 *  ни одно число не хардкодится в компоненте). */
export default function StoryPanel({
  step, content, values, onNext, onPrev, onShare,
  step4Part, onShowSecondPart, scenario, variant, onScenario, onVariant, onFreeMode,
}: StoryPanelProps) {
  const t = useT();
  const c = (key: string) => interpolate(content?.[key], values);

  return (
    <div className="gv-story-panel">
      <div className="gv-story-step-no">
        {content ? interpolate(content['nav.step-of'], { n: step, total: 7 }) : `${step} / 7`}
      </div>
      <h2 className="gv-story-title">{c(`step${step}.title`)}</h2>
      <div className="gv-story-body">
        {c(`step${step}.body`).split('\n\n').filter(Boolean).map((p, i) => <p key={i}>{p}</p>)}

        {step === 2 && (
          <table className="gv-story-table">
            <tbody>
              {[1, 2, 3, 4].map((i) => {
                const [label, val] = c(`step2.table.row${i}`).split('→').map((s) => s.trim());
                return <tr key={i}><td>{label}</td><td className="gv-story-table-val">{val}</td></tr>;
              })}
            </tbody>
          </table>
        )}

        {step === 3 && <p className="gv-story-caveat">{c('step3.caveat')}</p>}

        {step === 4 && (
          <>
            <p>{c(step4Part === 'se' ? 'step4.part1' : 'step4.part2')}</p>
            {step4Part === 'se' && (
              <button className="btn" onClick={onShowSecondPart}>{c('step4.button.show-second')}</button>
            )}
          </>
        )}

        {step === 7 && (
          <>
            {content?.['step7.body2'] && c('step7.body2').split('\n\n').filter(Boolean).map((p, i) => <p key={`b2-${i}`}>{p}</p>)}
            <div className="gv-story-step7-controls">
              <div role="group" aria-label={t('Сценарий')}>
                {(['base', 'optimistic', 'negative'] as const).map((s) => (
                  <button key={s} className={`btn${scenario === s ? ' active' : ''}`}
                    aria-pressed={scenario === s} onClick={() => onScenario(s)}>
                    {t(SCN_RU[s])}
                  </button>
                ))}
              </div>
              <div role="group" aria-label={t('Вариант прогноза')}>
                {(['A', 'B'] as const).map((v) => (
                  <button key={v} className={`btn${variant === v ? ' active' : ''}`}
                    aria-pressed={variant === v} onClick={() => onVariant(v)}>
                    {v === 'A' ? t('A — инерция') : t('Б — пригороды/периферия')}
                  </button>
                ))}
              </div>
            </div>
            <button className="btn primary gv-story-freemode-btn" onClick={onFreeMode}>
              {c('step7.button.free-mode')}
            </button>
          </>
        )}
      </div>

      <div className="gv-story-nav">
        <button className="btn" onClick={onPrev} disabled={step === 1}>
          {content ? c('nav.prev') : '← назад'}
        </button>
        <button className="btn" onClick={onShare} aria-label={content ? c('nav.share') : 'поделиться шагом'}>
          🔗
        </button>
        {step < 7 && (
          <button className="btn primary" onClick={onNext}>
            {content ? c('nav.next') : 'дальше →'}
          </button>
        )}
      </div>
    </div>
  );
}
