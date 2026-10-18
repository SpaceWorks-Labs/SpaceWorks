import type * as Api from "../../generated/api";
export type PageOwner = { kind: "makerspace" | "organization"; id: number };
export type AssetId = number;
export type AccentChoice = Api.AccentChoiceEnum;
export type PageAsset = Api.Asset;
// The serializer validates this discriminator even though its generated input flattens the branches.
export type TeamEntry = Pick<Api.TeamEntry, "id" | "role"> & (
  { kind: "explicit"; display_name: string; url?: string } | { kind: "member"; profile_id: number }
);
export type SectionPayloads = {
  about: Api.About; gallery: Api.Gallery; team: { title: string; entries: TeamEntry[] };
  upcoming_events: Api.Titled; stats: Api.Stats; testimonials: Api.Testimonials; links: Api.Links;
  location: Api.Location; linked_makerspaces: Api.Titled; organization_events: Api.Titled;
  functional_content: Record<string, never>;
};
export type SectionType = keyof SectionPayloads;
export type PageSection = { [K in SectionType]: { id: string; type: K; enabled: boolean; payload: SectionPayloads[K] } }[SectionType];
export type PageDocument = Omit<Api.Document, "sections"> & { sections: PageSection[] };
// Authored documents use a discriminated local form model above; HTTP reads use generated contracts.
export type PageCapabilities = Api.EditorCapabilities;
export type EditorState = Omit<Api.EditorState, "document"> & { document: PageDocument };
export type Collection<T> = Pick<Api.OrganizationSpaceList, "count" | "next" | "previous"> & { results: T[] };
export type SpaceCard = Api.SpaceCard;
export type PublicEventCard = Api.EventCard | Api.ArchiveCard | Api.PublicOrganizationEvent | Api.OrganizationArchiveEvent;
export type PublicPageSection = Api.ProjectedPublicPageSection;
export type PublicSectionPayloads = { [K in SectionType]: Extract<PublicPageSection, { type: K }>["payload"] };
export type PublicPageProjection = Api.PublicPageProjection;
export type PreviewProjection = Api.PreviewProjection;
export type HandleResolution = Api.HandleResolution;
export type RevisionMetadata = Api.RevisionMetadata;
