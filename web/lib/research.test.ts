import { describe, expect, it } from 'vitest';
import { RESEARCH } from './research';

describe('реестр исследований', () => {
  it('слаги уникальны и соответствуют кодам INF-01..09', () => {
    const slugs = RESEARCH.map((r) => r.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
    expect(RESEARCH).toHaveLength(9);
    expect(RESEARCH.map((r) => r.code)).toEqual(
      Array.from({ length: 9 }, (_, i) => `INF-0${i + 1}`),
    );
  });

  it('каждое опубликованное исследование имеет пакет артефактов', () => {
    for (const r of RESEARCH.filter((x) => x.status === 'published')) {
      expect(r.artifact, r.slug).toBeDefined();
      expect(r.artifact!.file).toMatch(new RegExp(`^by-maps-${r.slug}-v\\d+\\.\\d+\\.\\d+\\.zip$`));
    }
  });
});
