import type { PublicBookableSpace } from "./publicBookingsApi";

export const sectionKinds = ["rules", "amenity", "faq", "link", "sponsor", "gallery"] as const;
export type BookingWebsiteSection = {
  kind: typeof sectionKinds[number]; slug: string; title: string; body: string; url: string;
  visibility: "draft" | "published"; position: number; asset_id: number | null;
  image_url?: string | null; image_alt_text?: string;
};
export type BookingWebsite = {
  public_url?: string; embed_path?: string;
  revision: number; released: boolean; sections: BookingWebsiteSection[];
  assets?: { id: number; alt_text: string; size_bytes: number }[];
};
export type PublicBookingResource = PublicBookableSpace & {
  payment_amount: string; currency: string; website: BookingWebsite | null;
  rules: { minimum_minutes: number; maximum_minutes: number; lead_minutes: number;
    advance_days: number; cancellation_cutoff_hours: number };
};
export const websiteContent = (page: BookingWebsite) => ({ revision: page.revision,
  sections: page.sections.map(({ kind, slug, title, body, url, visibility, position, asset_id }) =>
    ({ kind, slug, title, body, url, visibility, position, asset_id })),
});
