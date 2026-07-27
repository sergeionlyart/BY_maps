'use client';

/** INF-13 «Кто кого содержит»: видеоверсия исследования (рилс R-P1, 1080x1920,
 *  53 с, RU/BE). Ролик собирается тем же конвейером, что и остальные материалы
 *  исследования - tools/render_reel_pension.py + tools/reel_pension_scene.json,
 *  все числа в кадрах считаются из web/public/data/pension.json в момент
 *  рендера, поэтому разойтись с опубликованными на этой странице числами он
 *  не может (то же правило, что у Findings.tsx).
 *
 *  Файлы: web/public/video/reel_pension_<lang>.mp4 (перекодировка CRF 18,
 *  ~3,2 МБ - каноническая CBR-версия 79 МБ не версионируется и выкладывается
 *  ассетом GitHub-релиза artifact-pension-reel-v1.4.0).
 *
 *  preload="none" - ролик не тянется, пока пользователь не нажал play:
 *  страница исследования и без него тяжёлая (карта + geojson + pension.json). */

import { useLang } from '@/lib/i18n';

export default function ReelBlock({ title, caption }: { title: string; caption?: string }) {
  const lang = useLang();
  const base = lang === 'be' ? '/video/reel_pension_be' : '/video/reel_pension_ru';
  return (
    <div className="chart-block pen-reel-block">
      <div className="chart-title">{title}</div>
      <video
        className="pen-reel"
        src={`${base}.mp4`}
        poster={`${base}.webp`}
        controls
        playsInline
        preload="none"
        width={1080}
        height={1920}
      />
      {caption ? <p className="hint pen-reel-caption">{caption}</p> : null}
    </div>
  );
}
