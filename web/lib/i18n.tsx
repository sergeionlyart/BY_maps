'use client';

import { createContext, useContext } from 'react';
import { usePathname } from 'next/navigation';
import DICT from './be-dict';

export type Lang = 'ru' | 'be';

/** Перевод строки: ключ — русский оригинал; для be берём из словаря, иначе
 *  честно откатываемся на русский (страница не ломается на пропущенном ключе). */
export function tr(lang: Lang, s: string): string {
  return lang === 'be' ? (DICT[s] ?? s) : s;
}

const LangContext = createContext<Lang>('ru');

/** Провайдер языка для клиентского поддерева: определяет язык по маршруту
 *  (/be/* → be). Оборачивает всё приложение в layout. */
export function LangProvider({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const lang: Lang = path.startsWith('/be') ? 'be' : 'ru';
  return <LangContext.Provider value={lang}>{children}</LangContext.Provider>;
}

export function useLang(): Lang {
  return useContext(LangContext);
}

/** Хук для клиентских компонентов: t('Показатель') → бел./рус. */
export function useT(): (s: string) => string {
  const lang = useLang();
  return (s: string) => tr(lang, s);
}
