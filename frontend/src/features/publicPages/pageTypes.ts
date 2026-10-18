import type { Asset, EditorCapabilities, PageLimits, EventCard, ArchiveCard, PublicGallery, RevisionMetadata as ApiRevisionMetadata, ResolvedTheme } from "../../generated/api";
export type PageOwner = { kind: "makerspace" | "organization"; id: number };
export type AssetId = number;
export type AccentChoice = "inherit" | "maker_teal" | "workshop_orange" | "citron" | "sky_blue" | "warm_yellow";
export type PageAsset = Asset;
export type TeamEntry = { id: string; role: string } & (
  { kind: "explicit"; display_name: string; url: string } | { kind: "member"; profile_id: number }
);
export type SectionPayloads = {
  about: { title: string; markdown: string };
  gallery: { title: string; items: { asset_id: AssetId; caption: string }[] };
  team: { title: string; entries: TeamEntry[] };
  upcoming_events: { title: string };
  stats: { title: string; show_public_inventory_units: boolean; show_published_event_count: boolean; publish_public_member_count: boolean };
  testimonials: { title: string; entries: { id: string; quote: string; attribution: string }[] };
  links: { title: string; entries: { id: string; label: string; platform: "website" | "github" | "linkedin" | "instagram" | "youtube" | "x" | "other"; url: string }[] };
  location: { title: string; enabled_publicly: boolean; source: "makerspace_public" | "entered"; address?: string; map_url?: string; latitude?: number | null; longitude?: number | null; directions?: string };
  linked_makerspaces: { title: string };
  organization_events: { title: string };
  functional_content: Record<string, never>;
};
export type SectionType = keyof SectionPayloads;
export type PageSection = { [K in SectionType]: { id: string; type: K; enabled: boolean; payload: SectionPayloads[K] } }[SectionType];
export type PageDocument = {
  schema_version: 1; cover_mode: "inherit" | "asset" | "none"; cover_asset_id: AssetId | null;
  accent_choice: AccentChoice | null; sections: PageSection[];
};
export type PageCapabilities = EditorCapabilities;
export type EditorState = {
  kind: PageOwner["kind"]; owner_id: number; version: number; handle: string | null;
  draft_revision_id: string | null; published_revision_id: string | null;
  document: PageDocument; assets: PageAsset[]; capabilities: PageCapabilities;
  limits: PageLimits;
};
export type Collection<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export type SpaceCard = { name: string; slug: string; logo_url: string | null; canonical_url: string };
export type PublicEventCard = Omit<EventCard, "event_url"> & {
  description?: string; timezone?: string;
  event_url: string | null; host?: ArchiveCard["host"];
  payment_amount?: string; currency?: string; availability?: string;
};
export type PublicSectionPayloads = {
  about: SectionPayloads["about"] & { rendering_policy?: "restricted" | "legacy_literal" };
  gallery: PublicGallery;
  team: { title: string; entries: { id?: string; display_name: string; role: string; url?: string; avatar_url?: string | null; handle?: string }[] };
  testimonials: SectionPayloads["testimonials"];
  links: SectionPayloads["links"];
  location: SectionPayloads["location"];
  stats: { title: string; metrics: Partial<Record<"public_exact_count_subset_units" | "published_event_count" | "public_member_count", number>> };
  upcoming_events: { title: string; collection_url: string; results: PublicEventCard[]; count: number };
  linked_makerspaces: { title: string; collection_url: string; results: SpaceCard[]; count: number };
  organization_events: { title: string; upcoming: Collection<PublicEventCard>; past: Collection<PublicEventCard>; collection_url: string };
  functional_content: { links: { label: string; url: string }[] };
};
export type PublicPageSection = { [K in SectionType]: { id: string; type: K; enabled?: boolean; payload: PublicSectionPayloads[K] } }[SectionType];
export type PublicPageProjection = {
  schema_version: 1; kind: PageOwner["kind"]; canonical_url: string; title: string; description: string;
  publication_token: string; cover: { url: string; alt: string } | null;
  presentation: { accent_choice: AccentChoice | null; resolved_theme: ResolvedTheme };
  sections: PublicPageSection[];
};
export type HandleResolution = {
  kind: "member" | PageOwner["kind"]; handle: string; canonical_url: string; redirected: boolean; content_url: string;
};
export type RevisionMetadata = ApiRevisionMetadata;
