'use client';

/** Загрузчик текста режима «История» (INF-15 v2) —
 *  web/public/content/research/grid-story.{ru,be}.md, формат `## ключ` до
 *  следующего `## ключ` (тот же принцип, что web/lib/pensionContent.ts).
 *  Текст живёт вне компонента специально: числа в нём — {{токены}},
 *  разрешаемые из живых данных (web/lib/gridStory.ts), а не литералы -
 *  условие брифа "нельзя хардкодить числа в компоненте". */

import { useEffect, useState } from 'react';

const cache = new Map<string, Record<string, string>>();

function parseKeyValueMd(text: string): Record<string, string> {
  const lines = text.split('\n');
  const out: Record<string, string> = {};
  let key: string | null = null;
  let buf: string[] = [];
  const flush = () => { if (key) out[key] = buf.join('\n').trim(); };
  for (const line of lines) {
    const m = line.match(/^##\s+(\S+)\s*$/);
    if (m) {
      flush();
      key = m[1];
      buf = [];
    } else if (key) {
      buf.push(line);
    }
  }
  flush();
  return out;
}

export function useGridStoryContent(lang: 'ru' | 'be'): Record<string, string> | null {
  const [data, setData] = useState<Record<string, string> | null>(cache.get(lang) ?? null);
  useEffect(() => {
    let alive = true;
    const cached = cache.get(lang);
    if (cached) { setData(cached); return; }
    fetch(`/content/research/grid-story.${lang}.md`)
      .then((r) => r.text())
      .then((text) => {
        const parsed = parseKeyValueMd(text);
        cache.set(lang, parsed);
        if (alive) setData(parsed);
      })
      .catch(() => { /* сеть недоступна - шаг покажет заголовок без текста */ });
    return () => { alive = false; };
  }, [lang]);
  return data;
}

/** Подстановка {{токен}} -> значение; незакрытые токены остаются видимыми
 *  (сигнал недостающих данных при разработке, не молчаливая пустота). */
export function interpolate(template: string | undefined, values: Record<string, string | number>): string {
  if (!template) return '';
  return template.replace(/\{\{(\w+)\}\}/g, (full, k: string) =>
    k in values ? String(values[k]) : full);
}
