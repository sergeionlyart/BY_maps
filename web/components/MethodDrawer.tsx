'use client';

import { useEffect, useState } from 'react';
import { useT, useLang } from '@/lib/i18n';
import Markdown from './Markdown';

/** Кнопка «О данных и методике» + выдвижная панель с методблоком
 *  (web/public/content/methods/[be/]<slug>.md, шаблон Р3 из TASK_SPEC). */
export default function MethodDrawer({ slug, label = 'О данных и методике' }: { slug: string; label?: string }) {
  const t = useT();
  const lang = useLang();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState<string | null>(null);

  useEffect(() => {
    if (open && text == null) {
      const dir = lang === 'be' ? 'methods/be' : 'methods';
      fetch(`/content/${dir}/${slug}.md`)
        .then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
        .then(setText)
        .catch(() => setText(t('Не удалось загрузить методологический блок.')));
    }
  }, [open, text, slug, lang]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <>
      <button className="btn" onClick={() => setOpen(true)}>ⓘ {t(label)}</button>
      {open && (
        <div className="drawer-overlay" onClick={() => setOpen(false)}>
          <aside className="drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal>
            <button className="drawer-close" onClick={() => setOpen(false)} aria-label={t('закрыть')}>×</button>
            {text == null ? <p className="hint">{t('Загрузка…')}</p> : <Markdown text={text} />}
          </aside>
        </div>
      )}
    </>
  );
}
