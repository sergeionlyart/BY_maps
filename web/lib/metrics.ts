import type { DataFile, Territory } from './types';
import { valueAt } from './series';

export interface RaionBreakdown {
  /** Население всего района (полигон: район + города на его территории). */
  whole: number | null;
  /** Городские центры района (райцентр + города областного подчинения). */
  centers: { id: string; ru: string; pop: number | null; area: number | null }[];
  centersPop: number | null;
  /** Население без городских центров. */
  noCenter: number | null;
  areaTotal: number;
  /** Площадь без известных площадей центров (где площади нет - без вычета). */
  areaNoCenter: number;
  densityWhole: number | null;
  densityNoCenter: number | null;
  /** Плотность в центрах - только если площади всех центров известны. */
  densityCenters: number | null;
  /** Доля населения района, живущая в центрах. */
  centersShare: number | null;
}

/** Декомпозиция района: весь район / городские центры / сельская часть.
 *  Смысл: средняя плотность района маскирует рост центра при пустеющей
 *  периферии (пример - Гродненский район и Гродно). */
export function raionBreakdown(data: DataFile, t: Territory, year: number): RaionBreakdown | null {
  if (t.level !== 'raion' || !t.area) return null;

  const centers = (t.center ?? [])
    .map((cid) => data.territories[cid])
    .filter(Boolean)
    .map((c) => ({
      id: c.id,
      ru: c.ru,
      pop: valueAt(c.pop, year)?.value ?? null,
      area: c.area ?? null,
    }));

  const whole = valueAt(t.pop, year)?.value ?? null;
  const noCenter = valueAt(t.popNoCenter, year)?.value ?? null;

  const centersPop = centers.length && centers.every((c) => c.pop != null)
    ? centers.reduce((s, c) => s + (c.pop ?? 0), 0)
    : null;

  const knownCenterArea = centers.reduce((s, c) => s + (c.area ?? 0), 0);
  const areaNoCenter = Math.max(t.area - knownCenterArea, 1);
  const centersAreaKnown = centers.length > 0 && centers.every((c) => c.area != null);

  return {
    whole,
    centers,
    centersPop,
    noCenter,
    areaTotal: t.area,
    areaNoCenter,
    densityWhole: whole != null ? whole / t.area : null,
    densityNoCenter: noCenter != null ? noCenter / areaNoCenter : null,
    densityCenters: centersAreaKnown && centersPop != null ? centersPop / knownCenterArea : null,
    centersShare: whole && centersPop != null ? centersPop / whole : null,
  };
}

/** Плотность города (чел./км²), если известна его площадь (Wikidata P2046). */
export function cityDensity(t: Territory, year: number): number | null {
  if (t.level !== 'city' || !t.area) return null;
  const pop = valueAt(t.pop, year)?.value;
  return pop != null ? pop / t.area : null;
}
