'use client';

import { useEffect, useState } from 'react';
import Markdown from './Markdown';

/** Кнопка «О данных и методике» + выдвижная панель с методблоком
 *  (web/public/content/methods/<slug>.md, шаблон Р3 из TASK_SPEC). */
export default function MethodDrawer({ slug, label = 'О данных и методике' }: { slug: string; label?: string }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState<string | null>(null);

  useEffect(() => {
    if (open && text == null) {
      fetch(`/content/methods/${slug}.md`)
        .then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
        .then(setText)
        .catch(() => setText('Не удалось загрузить методологический блок.'));
    }
  }, [open, text, slug]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <>
      <button className="btn" onClick={() => setOpen(true)}>ⓘ {label}</button>
      {open && (
        <div className="drawer-overlay" onClick={() => setOpen(false)}>
          <aside className="drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal>
            <button className="drawer-close" onClick={() => setOpen(false)} aria-label="закрыть">×</button>
            {text == null ? <p className="hint">Загрузка…</p> : <Markdown text={text} />}
          </aside>
        </div>
      )}
    </>
  );
}
