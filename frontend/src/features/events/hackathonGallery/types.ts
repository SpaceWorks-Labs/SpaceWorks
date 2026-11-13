import type { Command as WireCommand, GalleryAssetRead, GalleryEntryRead, GalleryConsentRead, GalleryFieldFilter as WireFieldFilter,
  ConsentRead, SponsorOptionRead, PublicResultsRead, RoundRead } from '../../../generated/api';
export type Command = WireCommand;
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export type GalleryFieldFilter = WireFieldFilter;
export type Envelope = Pick<RoundRead, 'id' | 'event_id' | 'version' | 'state' | 'allowed_actions'>;
export type GalleryAsset = GalleryAssetRead;
export type GalleryEntry = GalleryEntryRead;
export type GalleryConsent = GalleryConsentRead;
export type SponsorConsent = ConsentRead;
export type SponsorOption = SponsorOptionRead;
export type PublicResults = PublicResultsRead;
export function command(expected_version: number): Command {
  return { operation_id: crypto.randomUUID(), expected_version };
}
