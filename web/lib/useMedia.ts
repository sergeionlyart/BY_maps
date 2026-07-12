'use client';

import { useEffect, useState } from 'react';

/** SSR-безопасный matchMedia-хук. `initial` - значение до монтирования
 *  (на сервере/первом рендере), чтобы не мигало. */
export function useMedia(query: string, initial = false): boolean {
  const [matches, setMatches] = useState(initial);
  useEffect(() => {
    const mq = window.matchMedia(query);
    setMatches(mq.matches);
    const fn = (e: MediaQueryListEvent) => setMatches(e.matches);
    mq.addEventListener('change', fn);
    return () => mq.removeEventListener('change', fn);
  }, [query]);
  return matches;
}
