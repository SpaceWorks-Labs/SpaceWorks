import { describe, expect, it } from 'vitest';
import fixtures from './domain-fixtures.test.json';
import { gallerySearchQuery } from './api';
import { galleryEntry, publicResults } from './parsers';

describe('L21b gallery search and the finalists block', () => {
  it('sends search parameters only when set', () => {
    expect(gallerySearchQuery()).toBe('');
    expect(gallerySearchQuery({ sort: 'newest' })).toBe('');
    expect(gallerySearchQuery({ q: '  rover ', sort: 'awards', awards: 'only' })).toBe('q=rover&sort=awards&awards=only');
  });
  it('reads award badges and keeps entries without them valid', () => {
    expect(galleryEntry(fixtures.gallery_entry).awards).toEqual([]);
    expect(galleryEntry({ ...fixtures.gallery_entry, awards: [{ prize: 'Gold', rank: 1 }] }).awards).toEqual([{ prize: 'Gold', rank: 1 }]);
    expect(() => galleryEntry({ ...fixtures.gallery_entry, awards: [{ prize: 'Gold', rank: 'first' }] })).toThrow();
  });
  it('reads finalists published before any results', () => {
    const value = publicResults({ event_id: 4, version: null, published_at: null, awards: [],
      finalists: [{ title: 'Rover' }], finalists_published_at: '2026-11-05T10:00:00Z' });
    expect(value.version).toBeNull();
    expect(value.finalists).toEqual([{ title: 'Rover' }]);
  });
});
