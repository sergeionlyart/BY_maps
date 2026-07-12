import { describe, expect, it } from 'vitest';
import { RESEARCH } from './research';

describe('реестр исследований', () => {
  it('слаги уникальны; коды — INF-01..09 + ML', () => {
    const slugs = RESEARCH.map((r) => r.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
    expect(RESEARCH).toHaveLength(10);
    expect(RESEARCH.map((r) => r.code)).toEqual([
      ...Array.from({ length: 9 }, (_, i) => `INF-0${i + 1}`),
      'ML',
    ]);
  });

  it('каждое опубликованное исследование имеет корректно именованный пакет', () => {
    for (const r of RESEARCH.filter((x) => x.status === 'published')) {
      expect(r.artifact, r.slug).toBeDefined();
      // имя пакета образовано от slug пакета (artifactSlug, если задан) и версии
      const pkg = r.artifactSlug ?? r.slug;
      expect(r.artifact!.file).toBe(`by-maps-${pkg}-v${r.artifact!.version}.zip`);
      expect(r.artifact!.file).toMatch(/^by-maps-[a-z]+-v\d+\.\d+\.\d+\.zip$/);
    }
  });
});
