import type { GalleryConsent, GalleryEntry, GalleryFieldFilter, Page, PublicResults, SponsorConsent } from './types';

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid event response. Reload to try again.');
  return value as Record<string, unknown>;
}
function integer(value: unknown): asserts value is number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) throw new Error('Invalid event number.');
}
function text(value: unknown): asserts value is string {
  if (typeof value !== 'string') throw new Error('Invalid event text.');
}
function array(value: unknown): asserts value is unknown[] {
  if (!Array.isArray(value)) throw new Error('Invalid event list.');
}
export function page<T>(value: unknown, parse: (row: unknown) => T): Page<T> {
  const row = object(value); integer(row.count); array(row.results);
  for (const key of ['next', 'previous']) if (row[key] !== null) text(row[key]);
  return { count: row.count, next: row.next as string | null, previous: row.previous as string | null, results: row.results.map(parse) };
}
/** S7: the public choice fields the gallery may filter by; absent (an older server) reads as none. */
export function galleryFilters(value: unknown): GalleryFieldFilter[] {
  const row = object(value);
  if (row.filters === undefined) return [];
  array(row.filters);
  return row.filters.map(item => {
    const filter = object(item); text(filter.key); text(filter.label); array(filter.choices); filter.choices.forEach(text);
    return { key: filter.key, label: filter.label, choices: filter.choices as string[] };
  });
}
export function galleryEntry(value: unknown): GalleryEntry {
  const row = object(value);
  for (const key of ['public_id', 'title', 'description', 'content_sha256']) text(row[key]);
  integer(row.consent_version);
  if (!['available', 'expired', 'withdrawn'].includes(String(row.files_state))) throw new Error('Invalid project file state.');
  array(row.assets); array(row.links); array(row.members);
  const assets = row.assets.map(value => {
    const asset = object(value);
    for (const key of ['public_id', 'mime', 'sha256', 'kind', 'download_url']) text(asset[key]);
    integer(asset.bytes);
    if (!/^\/api\/v1\/public\/event-programmes\/[a-f0-9-]+\/gallery\/assets\/[a-f0-9-]+\/$/i.test(String(asset.download_url))) {
      throw new Error('Invalid project download route.');
    }
    return { public_id: String(asset.public_id), mime: String(asset.mime), bytes: Number(asset.bytes),
      sha256: String(asset.sha256), kind: String(asset.kind), download_url: String(asset.download_url) };
  });
  const links = row.links.map(value => {
    const link = object(value); text(link.kind); text(link.url);
    const url = new URL(link.url);
    if (url.protocol !== 'https:' || url.username || url.password) throw new Error('Invalid project link.');
    return { kind: link.kind, url: link.url };
  });
  const members = row.members.map(value => {
    const card = object(value); text(card.display_name); text(card.profile_url);
    if (!/^\/[a-z0-9][a-z0-9._-]{1,28}[a-z0-9]$/.test(card.profile_url)) throw new Error('Invalid public profile.');
    const photo = typeof card.photo_url === 'string' && /^\/api\/v1\/public\/event-programmes\/[a-f0-9-]{36}\/member-cards\/[a-f0-9-]{36}\/photo\/$/.test(card.photo_url)
      ? card.photo_url : undefined;
    return { display_name: card.display_name, profile_url: card.profile_url, ...(photo ? { photo_url: photo } : {}) };
  });
  // L21b: award badges arrive only after results are published (and only with gallery search on).
  const awards = Array.isArray(row.awards) ? row.awards.map(value => { const award = object(value); text(award.prize); integer(award.rank);
    return { prize: award.prize, rank: award.rank }; }) : [];
  return { public_id: String(row.public_id), title: String(row.title), description: String(row.description),
    content_sha256: String(row.content_sha256), consent_version: row.consent_version,
    files_state: row.files_state as GalleryEntry['files_state'], assets, links, members, awards,
    // #181: present (true) only on a published People's choice winner.
    ...(row.peoples_choice === true ? { peoples_choice: true } : {}) };
}
export function galleryConsent(value: unknown): GalleryConsent {
  const row = object(value); integer(row.team_id); integer(row.version);
  if (typeof row.metadata_public !== 'boolean') throw new Error('Invalid publication choice.');
  array(row.asset_ids); array(row.link_ids); row.asset_ids.forEach(integer); row.link_ids.forEach(integer);
  if (row.publication_state && !['published', 'unpublished', 'amendment_required'].includes(String(row.publication_state))) throw new Error('Invalid publication state.');
  return { team_id: row.team_id, version: row.version, metadata_public: row.metadata_public,
    asset_ids: row.asset_ids as number[], link_ids: row.link_ids as number[],
    publication_state: row.publication_state as GalleryConsent['publication_state'], state: row.state as string | undefined };
}
export function sponsorConsent(value: unknown): SponsorConsent {
  const row = object(value);
  for (const key of ['id', 'sponsor_id', 'asset_id', 'version']) integer(row[key]);
  text(row.sponsor_name); text(row.consented_at);
  if (row.purpose !== 'recruiting' || !['granted', 'revoked'].includes(String(row.state))) throw new Error('Invalid résumé consent.');
  if (row.expires_at !== null) text(row.expires_at);
  return { id: Number(row.id), sponsor_id: Number(row.sponsor_id), asset_id: Number(row.asset_id), version: Number(row.version),
    sponsor_name: row.sponsor_name, purpose: 'recruiting', state: row.state as SponsorConsent['state'],
    consented_at: row.consented_at, expires_at: row.expires_at as string | null };
}
export function publicResults(value: unknown): PublicResults {
  const row = object(value); integer(row.event_id); array(row.awards);
  // L21b: published finalists may come before results, so version and published_at may be null.
  if (row.version !== null) integer(row.version);
  if (row.published_at !== null) text(row.published_at);
  const finalists = Array.isArray(row.finalists) ? row.finalists.map(value => { const item = object(value); text(item.title); return { title: item.title }; }) : [];
  return { event_id: row.event_id, version: row.version as number | null, published_at: row.published_at as string | null,
    awards: row.awards.map(value => { const award = object(value); text(award.prize); text(award.title); integer(award.rank);
      return { prize: award.prize, title: award.title, rank: award.rank }; }),
    finalists, finalists_published_at: typeof row.finalists_published_at === 'string' ? row.finalists_published_at : null };
}
