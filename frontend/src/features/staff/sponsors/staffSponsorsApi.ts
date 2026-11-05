import { staffRequest } from "../../../lib/api";

// Hand-written mirrors of `apps/payments/donations/serializers_sponsors.py` (lane L18).
export type Sponsor = {
  id: number; name: string; organization: number | null; tier: number | null; tier_name: string; logo_url: string;
  website_url: string; blurb: string; contact_name: string; contact_email: string; contact_phone: string;
  starts_on: string | null; ends_on: string | null; show_on_wall: boolean; perks_open: number; created_at: string;
  updated_at: string; archived_at: string | null; pii_masked?: boolean;
};
export type SponsorInput = Pick<Sponsor, "name" | "tier" | "website_url" | "blurb" | "contact_name" | "contact_email"
  | "contact_phone" | "starts_on" | "ends_on" | "show_on_wall">;
export type Tier = { id: number; name: string; rank: number; amount: string | null; currency: string; description: string };
export type Perk = {
  id: number; tier: number | null; sponsor: number | null; source_perk: number | null; description: string;
  due_on: string | null; fulfilled_at: string | null; fulfilled_by: number | null; fulfilled_by_name: string; note: string;
};
export type Charge = {
  id: number; sponsor: number; amount: string; currency: string; description: string; payment_id: number | null;
  payment_status: string; created_at: string;
  /** Hack-money G8: the event this money is for, and whether it funds that event's prize pool. */
  event?: number | null; earmark?: "general" | "prize_pool";
};
export type ChargeInput = { amount: string; description: string; event_id?: number | null; earmark?: "general" | "prize_pool" };
export type EventLink = {
  id: number; sponsor: number; event_sponsor: number; event_id: number; event_title: string; label: string; created_at: string;
};

export type EventSponsorChoice = {
  id: number; label: string; event_id: number; event_title: string; active: boolean; linked_sponsor_id: number | null;
};

export const sponsorKeys = {
  list: (id: number, archived: boolean) => ["staff-sponsors", id, archived] as const,
  tiers: (id: number) => ["staff-sponsor-tiers", id] as const,
  perks: (id: number, sponsor: number | "all") => ["staff-sponsor-perks", id, sponsor] as const,
  charges: (id: number, sponsor: number) => ["staff-sponsor-charges", id, sponsor] as const,
  links: (id: number, sponsor: number) => ["staff-sponsor-links", id, sponsor] as const,
  eventSponsors: (id: number) => ["staff-sponsor-event-choices", id] as const,
};

const base = (id: number) => `/admin/makerspace/${id}/sponsors`;
const json = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) });

export const sponsorApi = {
  list: (id: number, archived: boolean) => staffRequest<Sponsor[]>(`${base(id)}${archived ? "?archived=1" : ""}`),
  create: (id: number, body: SponsorInput) => staffRequest<Sponsor>(base(id), json("POST", body)),
  update: (id: number, sponsor: number, body: Partial<SponsorInput>) =>
    staffRequest<Sponsor>(`${base(id)}/${sponsor}`, json("PATCH", body)),
  archive: (id: number, sponsor: number, archived: boolean) =>
    staffRequest<Sponsor>(`${base(id)}/${sponsor}/${archived ? "archive" : "restore"}`, json("POST")),
  logoEndpoint: (id: number, sponsor: number) => `${base(id)}/${sponsor}/logo`,
  tiers: (id: number) => staffRequest<Tier[]>(`${base(id)}/tiers`),
  createTier: (id: number, body: Pick<Tier, "name" | "rank" | "amount" | "description">) =>
    staffRequest<Tier>(`${base(id)}/tiers`, json("POST", body)),
  perks: (id: number, sponsor: number | "all") =>
    staffRequest<Perk[]>(`${base(id)}/perks${sponsor === "all" ? "" : `?sponsor=${sponsor}`}`),
  createPerk: (id: number, body: { tier?: number | null; sponsor?: number | null; description: string; due_on: string | null }) =>
    staffRequest<Perk>(`${base(id)}/perks`, json("POST", body)),
  fulfil: (id: number, perk: number, fulfilled: boolean) =>
    staffRequest<Perk>(`${base(id)}/perks/${perk}/fulfil`, json("POST", { fulfilled })),
  charges: (id: number, sponsor: number) => staffRequest<Charge[]>(`${base(id)}/${sponsor}/charges`),
  raiseCharge: (id: number, sponsor: number, body: ChargeInput) =>
    staffRequest<Charge>(`${base(id)}/${sponsor}/charges`, json("POST", body)),
  returnCharge: (id: number, charge: number) => staffRequest<Charge>(`${base(id)}/charges/${charge}/return`, json("POST", {})),
  links: (id: number, sponsor: number) => staffRequest<EventLink[]>(`${base(id)}/${sponsor}/event-links`),
  eventSponsors: (id: number) => staffRequest<EventSponsorChoice[]>(`${base(id)}/event-sponsors`),
  link: (id: number, sponsor: number, eventSponsor: number) =>
    staffRequest<EventLink>(`${base(id)}/${sponsor}/event-links`, json("POST", { event_sponsor: eventSponsor })),
  unlink: (id: number, link: number) => staffRequest<void>(`${base(id)}/event-links/${link}`, json("DELETE")),
};

export const PAYMENT_STATUS: Record<string, string> = {
  pending: "Owed", paid_online: "Paid online", paid_offline: "Paid offline", waived: "Waived", canceled: "Cancelled",
};
