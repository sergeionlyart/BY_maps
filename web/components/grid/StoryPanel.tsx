'use client';

import { interpolate } from '@/lib/gridStoryContent';
import type { Scenario, Variant } from '@/lib/grid';
import type { GridStoryData } from '@/lib/gridStory';
import { useT } from '@/lib/i18n';
import MiniChart from './MiniChart';

const SCN_RU: Record<Scenario, string> = { base: 'базовый', optimistic: 'оптимистичный', negative: 'негативный' };
const TOTAL_STEPS = 9;

/** `**жирный**` -> <strong> - лёгкая замена полноценного markdown (текст
 *  режима «История» использует только этот один приём выделения). */
function renderInline(text: string): (string | React.ReactElement)[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

function Paragraphs({ text }: { text: string }) {
  return (
    <>
      {text.split('\n\n').filter(Boolean).map((p, i) => <p key={i}>{renderInline(p)}</p>)}
    </>
  );
}

export interface StoryPanelProps {
  step: number; // 1-9
  content: Record<string, string> | null;
  values: Record<string, string | number>;
  story: GridStoryData | null;
  lang: 'ru' | 'be';
  onNext: () => void;
  onPrev: () => void;
  onShare: () => void;
  showCities: boolean;
  onToggleCities: () => void;
  scenario: Scenario;
  variant: Variant;
  onScenario: (s: Scenario) => void;
  onVariant: (v: Variant) => void;
  onFreeMode: () => void;
}

/** Панель шага режима «История» (INF-15 v2/v3) - номер, заголовок, текст,
 *  навигация. Текст читается из web/public/content/research/
 *  grid-story.{ru,be}.md через web/lib/gridStoryContent.ts, числа в нём -
 *  {{токены}} из web/lib/gridStory.ts::buildStoryValues (условие брифа:
 *  ни одно число не хардкодится в компоненте). */
export default function StoryPanel({
  step, content, values, story, lang, onNext, onPrev, onShare,
  showCities, onToggleCities, scenario, variant, onScenario, onVariant, onFreeMode,
}: StoryPanelProps) {
  const t = useT();
  const c = (key: string) => interpolate(content?.[key], values);

  const matrixGroups = story?.c006_river_road_matrix.groups;
  const matrixLabel = (id: string) => ({
    both: t('река + дорога'), river_only: t('только река'),
    road_only: t('только дорога'), neither: t('ни то, ни другое'),
  } as Record<string, string>)[id] ?? id;

  return (
    <div className="gv-story-panel">
      <div className="gv-story-step-no">
        {content ? interpolate(content['nav.step-of'], { n: step, total: TOTAL_STEPS }) : `${step} / ${TOTAL_STEPS}`}
      </div>
      <h2 className="gv-story-title">{c(`step${step}.title`)}</h2>
      <div className="gv-story-body">
        <Paragraphs text={c(`step${step}.body`)} />

        {step === 2 && (
          <>
            {content?.['step2.explain'] && (
              <p className="hint">{c('step2.explain')}</p>
            )}
            <table className="gv-story-table">
              <tbody>
                {[1, 2, 3, 4].map((i) => {
                  const [label, val] = c(`step2.table.row${i}`).split('→').map((s) => s.trim());
                  return <tr key={i}><td>{label}</td><td className="gv-story-table-val">{val}</td></tr>;
                })}
              </tbody>
            </table>
            {content?.['step2.kicker'] && <p><strong>{c('step2.kicker')}</strong></p>}
            {story && (
              <MiniChart rows={[1, 2, 3, 4].map((i) => {
                const [label] = c(`step2.table.row${i}`).split('→').map((s) => s.trim());
                const bands = story.c004_density_bands.bands;
                const idxMap = [1, 2, 4, 5]; // 5-25, 25-100, 500-2000, 2000+
                return { label, value: bands[idxMap[i - 1]]?.change_pct ?? 0 };
              })} />
            )}
          </>
        )}

        {step === 3 && (
          <>
            {content?.['step3.detail'] && <Paragraphs text={c('step3.detail')} />}
            {story && (
              <MiniChart rows={story.c007_river_distance.bands.slice(0, 2).map((b) => ({
                label: `${b.lo}–${b.hi ?? '+'} ${t('км от реки')}`, value: b.change_pct ?? 0,
              }))} />
            )}
          </>
        )}

        {step === 4 && (
          <>
            {content?.['step4.body2'] && <Paragraphs text={c('step4.body2')} />}
            {content?.['step4.kicker'] && <p><strong>{c('step4.kicker')}</strong></p>}
            <MatrixLegend t={t} />
            {matrixGroups && (
              <MiniChart rows={['river_only', 'road_only'].map((id) => {
                const g = matrixGroups.find((x) => x.id === id)!;
                return { label: matrixLabel(id), value: g.change_pct ?? 0 };
              })} />
            )}
          </>
        )}

        {step === 5 && (
          <>
            <MatrixLegend t={t} />
            <table className="gv-story-table">
              <tbody>
                {[1, 2, 3, 4].map((i) => {
                  const [label, val] = c(`step5.table.row${i}`).split('→').map((s) => s.trim());
                  return <tr key={i}><td>{label}</td><td className="gv-story-table-val">{val}</td></tr>;
                })}
              </tbody>
            </table>
            {matrixGroups && (
              <MiniChart rows={matrixGroups.map((g) => ({
                label: matrixLabel(g.id), value: g.change_pct ?? 0, highlight: g.id === 'both',
              }))} />
            )}
            <button className="btn gv-show-cities-btn" aria-pressed={showCities} onClick={onToggleCities}>
              {showCities ? t('Скрыть города') : t('Показать города')}
            </button>
            {showCities && (
              <>
                <p>{c('step5.cities')}</p>
                {story && (
                  <table className="gv-story-table gv-cities-table">
                    <thead>
                      <tr>
                        <th>{t('город')}</th>
                        <th>{t('до реки, км')}</th>
                        <th>{t('до дороги, км')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {story.c007_river_distance.cities.map((city) => (
                        <tr key={city.id} className={city.is_exception ? 'gv-city-exception' : ''}>
                          <td>{lang === 'be' ? city.name_be : city.name_ru}</td>
                          <td>{city.river_km.toFixed(1)}</td>
                          <td>{city.road_km.toFixed(1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </>
            )}
            <p className="gv-story-caveat">{c('step5.caveat')}</p>
          </>
        )}

        {step === 6 && (
          <>
            {content?.['step6.part1'] && <p>{renderInline(c('step6.part1'))}</p>}
            {content?.['step6.part2'] && <p>{renderInline(c('step6.part2'))}</p>}
            {content?.['step6.part3'] && <p>{renderInline(c('step6.part3'))}</p>}
            {content?.['step6.kicker'] && <p><strong>{c('step6.kicker')}</strong></p>}
          </>
        )}

        {step === 8 && (
          <>
            {content?.['step8.explain'] && <Paragraphs text={c('step8.explain')} />}
            {content?.['step8.numbers'] && <Paragraphs text={c('step8.numbers')} />}
          </>
        )}

        {step === 9 && (
          <>
            {content?.['step9.finding'] && <p>{c('step9.finding')}</p>}
            {content?.['step9.g3'] && <Paragraphs text={c('step9.g3')} />}
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
            {content?.['step9.conclusion'] && (
              <div className="gv-story-conclusion">
                <Paragraphs text={c('step9.conclusion')} />
              </div>
            )}
            <button className="btn primary gv-story-freemode-btn" onClick={onFreeMode}>
              {c('step9.button.free-mode')}
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
        {step < TOTAL_STEPS && (
          <button className="btn primary" onClick={onNext}>
            {content ? c('nav.next') : 'дальше →'}
          </button>
        )}
      </div>
    </div>
  );
}

/** Легенда 4 цветов маски «река x дорога» (шаги 4-5) - словами, не только
 *  цветом (раздел 8 п.3 приёмки документа v3). Цвета - те же HEX, что и
 *  MATRIX_COLORS в etl/grid_story.py (RGBA -> непрозрачный HEX). */
const MATRIX_LEGEND: { id: string; color: string; label: string }[] = [
  { id: 'both', color: '#2ea35b', label: 'река + дорога' },
  { id: 'river_only', color: '#4682dc', label: 'только река' },
  { id: 'road_only', color: '#e67828', label: 'только дорога' },
  { id: 'neither', color: '#8c8c8c', label: 'ни то, ни другое' },
];

function MatrixLegend({ t }: { t: (s: string) => string }) {
  return (
    <div className="gv-legend gv-story-matrix-legend" aria-label={t('Легенда')}>
      {MATRIX_LEGEND.map((g) => (
        <span key={g.id} className="gv-legend-row">
          <span className="gv-legend-swatch" style={{ background: g.color }} />
          {t(g.label)}
        </span>
      ))}
    </div>
  );
}
