export type Command = { operation_id: string; expected_version: number };
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export type Envelope = { id: number; event_id: number; version: number; state?: string; allowed_actions: string[] };
export type GalleryAsset = { public_id: string; mime: string; bytes: number; sha256: string; kind: string; download_url: string };
export type GalleryEntry = {
  public_id: string; title: string; description: string; consent_version: number;
  files_state: 'available' | 'expired' | 'withdrawn'; content_sha256: string;
  assets: GalleryAsset[]; links: { kind: string; url: string }[];
  members: { display_name: string; profile_url: string; photo_url?: string | null }[];
};
export type GalleryConsent = {
  team_id: number; version: number; metadata_public: boolean; asset_ids: number[]; link_ids: number[];
  publication_state?: 'published' | 'unpublished' | 'amendment_required'; state?: string;
};
export type SponsorConsent = {
  id: number; sponsor_id: number; sponsor_name: string; asset_id: number; purpose: 'recruiting';
  state: 'granted' | 'revoked'; version: number; consented_at: string; expires_at: string | null;
};
export type SponsorOption = { id: number; name: string; disclosure_revision: number };
export type PublicResults = { event_id: number; version: number; published_at: string;
  awards: { prize: string; rank: number; title: string }[] };
export function command(expected_version: number): Command {
  return { operation_id: crypto.randomUUID(), expected_version };
}
