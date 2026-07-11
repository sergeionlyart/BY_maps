'use client';

import { useEffect, useState } from 'react';
import Markdown from '@/components/Markdown';

export default function MethodologyPage() {
  const [method, setMethod] = useState<string | null>(null);
  const [sources, setSources] = useState<string | null>(null);
  const [tab, setTab] = useState<'method' | 'sources'>('method');

  useEffect(() => {
    fetch('/content/methodology.md').then((r) => r.text()).then(setMethod);
    fetch('/content/sources.md').then((r) => r.text()).then(setSources);
  }, []);

  const text = tab === 'method' ? method : sources;
  return (
    <div className="page">
      <h1>Методика и источники</h1>
      <div className="seg" style={{ marginBottom: 14 }}>
        <button className={tab === 'method' ? 'on' : ''} onClick={() => setTab('method')}>
          Методика обработки
        </button>
        <button className={tab === 'sources' ? 'on' : ''} onClick={() => setTab('sources')}>
          Источники данных
        </button>
      </div>
      {text == null ? <p className="hint">Загрузка…</p> : <Markdown text={text} />}
    </div>
  );
}
