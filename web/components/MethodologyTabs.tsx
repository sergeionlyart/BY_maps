'use client';

import { useState } from 'react';
import Markdown from '@/components/Markdown';
import { useT } from '@/lib/i18n';

/** Подразделы методологии: «Методика обработки» и «Источники». Тексты
 *  передаются пропсами (прочитаны на сборке) — SSR помещает активную вкладку
 *  в статический HTML (в отличие от прежнего клиентского fetch, T-08). */
export default function MethodologyTabs({ method, sources }: { method: string; sources: string }) {
  const t = useT();
  const [tab, setTab] = useState<'method' | 'sources'>('method');
  return (
    <section id="podrobno" className="method-tabs">
      <div className="seg" style={{ margin: '8px 0 14px' }}>
        <button className={tab === 'method' ? 'on' : ''} onClick={() => setTab('method')}>
          {t('Методика обработки')}
        </button>
        <button className={tab === 'sources' ? 'on' : ''} onClick={() => setTab('sources')}>
          {t('Источники данных')}
        </button>
      </div>
      <article className="content">
        <Markdown text={tab === 'method' ? method : sources} />
      </article>
    </section>
  );
}
