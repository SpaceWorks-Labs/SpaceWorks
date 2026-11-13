import { describe, expect, it } from 'vitest';
import fixtures from './domain-fixtures.test.json';
import frozen from '../../../../../backend/tests/events/programme/contracts/fixtures/routes-v3.json';
import { galleryEntry, galleryConsent, page, sponsorConsent } from './parsers';

describe('canonical D provider/consumer contracts', () => {
  it('reads G’s literal sponsor-consent pagination without copying the fixture', () => {
    const route = frozen.routes.find(row => row.name === 'events-programme-member-resume-consents');
    const result = page(route?.operations.GET?.response_example, sponsorConsent);
    expect(result.results[0]).toMatchObject({ sponsor_id: 6, asset_id: 301, purpose: 'recruiting', state: 'granted' });
  });
  it('keeps the public project allowlist closed', () => {
    const value = galleryEntry({ ...fixtures.gallery_entry, email: 'private@example.test', answers: { private: true } });
    expect(value).not.toHaveProperty('email'); expect(value).not.toHaveProperty('answers');
    expect(value.assets[0]).not.toHaveProperty('object_key');
  });
  it.each(['javascript:alert(1)', 'https://member:secret@example.test/private'])('refuses unsafe external links: %s', url => {
    expect(() => galleryEntry({ ...fixtures.gallery_entry, links: [{ kind: 'repo', url }] })).toThrow();
  });
  it('refuses object-store URLs and an unknown file state', () => {
    expect(() => galleryEntry({ ...fixtures.gallery_entry, assets: [{ ...fixtures.gallery_entry.assets[0], download_url: 'https://storage.test/private' }] })).toThrow();
    expect(() => galleryEntry({ ...fixtures.gallery_entry, files_state: 'hidden-ready' })).toThrow();
  });
  it('reads the frozen withdrawal response with no implicit consent', () => {
    expect(galleryConsent({ team_id: 21, version: 5, metadata_public: false, asset_ids: [], link_ids: [], state: 'withdrawn' }).metadata_public).toBe(false);
  });
});
