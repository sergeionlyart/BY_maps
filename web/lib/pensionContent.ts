'use client';

/** INF-13 UX: два слоя текста («Просто»/«Профессионально») для /research/pension,
 *  хранятся в web/public/content/research/pension.<layer>.<lang>.md (не в коде -
 *  ТЗ handoff/10_pension_ux_copy §4 п.5). Формат файла: `## key.name` -> тело до
 *  следующего заголовка (та же idea, что headings() в lib/content.ts, только
 *  парсится на клиенте и хранит тело целиком, а не оглавление). Числа в текст
 *  подставляются через fillTemplate() из уже посчитанных в компонентах значений
 *  (Findings.tsx и т.п.) - шаблоны сами данных не считают. */

import { useEffect, useState } from 'react';

export type CopyLayer = 'simple' | 'pro';

export const DEFAULT_LAYER: CopyLayer = 'simple';

export function readLayerParam(): CopyLayer {
  if (typeof window === 'undefined') return DEFAULT_LAYER;
  return new URLSearchParams(window.location.search).get('copy') === 'pro' ? 'pro' : 'simple';
}

type ContentMap = Record<string, string>;

function parseContent(text: string): ContentMap {
  const map: ContentMap = {};
  const lines = text.split('\n');
  let key: string | null = null;
  let buf: string[] = [];
  const flush = () => {
    if (key) map[key] = buf.join('\n').trim();
    buf = [];
  };
  for (const line of lines) {
    const m = line.match(/^##\s+([a-zA-Z0-9_.-]+)\s*$/);
    if (m) {
      flush();
      key = m[1];
    } else if (key) {
      buf.push(line);
    }
  }
  flush();
  return map;
}

const cache = new Map<string, ContentMap>();
const inflight = new Map<string, Promise<ContentMap>>();

function load(path: string): Promise<ContentMap> {
  const cached = cache.get(path);
  if (cached) return Promise.resolve(cached);
  const existing = inflight.get(path);
  if (existing) return existing;
  const p = fetch(path)
    .then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
    .then((text) => {
      const parsed = parseContent(text);
      cache.set(path, parsed);
      inflight.delete(path);
      return parsed;
    });
  inflight.set(path, p);
  return p;
}

/** Загружает контент-файл для слоя/языка. Пока не загружен - map == null
 *  (вызывающий компонент показывает {{key}}-заглушки быть не должно: до
 *  первой загрузки страница ещё в состоянии "Загрузка данных..."). */
export function usePensionContent(layer: CopyLayer, lang: 'ru' | 'be'): ContentMap | null {
  const path = `/content/research/pension.${layer}.${lang}.md`;
  const [map, setMap] = useState<ContentMap | null>(() => cache.get(path) ?? null);
  useEffect(() => {
    let alive = true;
    const cached = cache.get(path);
    if (cached) { setMap(cached); return; }
    setMap(null);
    load(path).then((m) => { if (alive) setMap(m); });
    return () => { alive = false; };
  }, [path]);
  return map;
}

export function fillTemplate(tpl: string, vars: Record<string, string | number>): string {
  return tpl.replace(/\{\{(\w+)\}\}/g, (whole, k) => (k in vars ? String(vars[k]) : whole));
}

/** Русское/белорусское форматирование чисел с запятой вместо точки (проект
 *  уже так делает через toLocaleString('ru-RU') в остальных вьюхах -
 *  lib/series.ts, lib/pyramid.ts и т.д.; для be отдельной локали Intl нет,
 *  ru-RU даёт корректный десятичный разделитель и для белорусского текста). */
export function ruNum(n: number | null | undefined, digits = 2): string {
  if (n == null || !Number.isFinite(n)) return '—';
  return n.toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export interface ContentGetter {
  /** Сырой текст ключа (для Markdown) с опциональной подстановкой {{var}}. */
  get(key: string, vars?: Record<string, string | number>): string;
  /** Есть ли непустой текст под этим ключом (для условного рендера). */
  has(key: string): boolean;
}

export function makeGetter(map: ContentMap | null): ContentGetter {
  return {
    get(key, vars) {
      const raw = map?.[key];
      if (raw == null) return '';
      return vars ? fillTemplate(raw, vars) : raw;
    },
    has(key) {
      return !!map?.[key];
    },
  };
}
