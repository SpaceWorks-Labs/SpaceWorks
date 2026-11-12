import { useQuery } from "@tanstack/react-query";
import { API_V1_URL, staffRequest, tenantPublicRequest } from "../../lib/api";

// Hand-typed from the SPACE-DISPLAY contract (decision 307); `generated/api.ts` is regenerated at staging.
export type PersonCard = {
  handle: string | null; display_name: string; avatar_url: string | null; headline: string;
  status: { preset: string; note: string } | null; skills: string[]; presence_status: string; since: string;
};
export type HereNow = { audience: "public" | "member"; people: PersonCard[]; others_count: number; total: number };
export type MachineNowStatus = "in_use" | "free" | "out_of_service";
export type MachinesNow = { in_use: number; free: number; out_of_service: number;
  items: { name: string; type: string; status: MachineNowStatus }[] };
export type DisplayEvent = { token: string; title: string; starts_at: string; ends_at: string; location: string;
  delivery_mode: string; live: boolean };
export type DisplayCalendar = { month: string; events: DisplayEvent[]; live: DisplayEvent[] };
export type DisplayPanel = "here_now" | "calendar" | "machines" | "announcement" | "public_stats" | "opening_hours"
  | "inventory_highlights" | "sponsors";
export const DISPLAY_PANELS: DisplayPanel[] = ["here_now", "calendar", "machines", "announcement", "public_stats", "opening_hours",
  "inventory_highlights", "sponsors"];
export type DisplayLayout = "single" | "grid" | "playlist";
export type DisplayTheme = "dark" | "light" | "black" | "brand" | "space";
/** `profiles` is how Here now behaved before settings existed; the other two only show less. */
export type DisplayPrivacy = "profiles" | "first_names" | "counts";
export type DisplayConfig = { name: string; panels: DisplayPanel[]; rotation_seconds: number; version: number;
  layout: DisplayLayout; theme: DisplayTheme; privacy: DisplayPrivacy; refresh_seconds: number; slide_seconds: Partial<Record<DisplayPanel, number>> };
export type StatsMetric = { key: string; label: string; value: number | null; kind: string; suppressed: boolean };
export type StatsPanelData = { period: string; metrics: StatsMetric[] };
/** The public catalogue's own availability object: an exact count only when the item allows it. */
export type PublicAvailability = { mode: "exact_count" | "status_only"; label: string; count?: number } | null;
export type InventoryHighlightsData = { items: { name: string; category: string; image_url: string | null; availability: PublicAvailability }[] };
export type SponsorsWallData = { sponsors: { name: string; tier: string; logo_url: string | null }[] };
export type OpeningInterval = { start: string; end: string };
export type OpeningHoursData = { weekly?: Record<string, OpeningInterval[]>; exceptions?: Record<string, OpeningInterval[]> };
export type DisplayState =
  | { state: "unclaimed"; code: string; code_expires_at: string }
  | { state: "paired"; generated_at: string; space: { name: string; slug: string; timezone: string; theme?: unknown }; config: DisplayConfig;
      here_now: HereNow | null; calendar: DisplayCalendar | null; machines: MachinesNow | null; announcement: string | null;
      public_stats: StatsPanelData | null; opening_hours: OpeningHoursData | null;
      inventory_highlights?: InventoryHighlightsData | null; sponsors?: SponsorsWallData | null };
export type DisplayRegistration = { token: string; code: string; code_expires_at: string };
export type AdminDisplay = { id: number; name: string; panels: DisplayPanel[]; rotation_seconds: number;
  announcement: string; claimed_at: string; last_seen_at: string | null; online: boolean;
  layout: DisplayLayout; theme: DisplayTheme; privacy: DisplayPrivacy; refresh_seconds: number;
  slide_seconds: Partial<Record<DisplayPanel, number>>; player_ids: number[];
  /** A staff-issued link screen (Anthias). */ has_link: boolean;
  /** The secret-bearing address: only in the provision and New address responses, "" in lists (L-D3). */ url: string };
export type AdminDisplayList = { enabled: boolean; displays: AdminDisplay[] };
export type DisplayConfigInput = Partial<{ name: string; panels: DisplayPanel[]; rotation_seconds: number; announcement: string;
  layout: DisplayLayout; theme: DisplayTheme; privacy: DisplayPrivacy; refresh_seconds: number; slide_seconds: Partial<Record<DisplayPanel, number>> }>;

export class DisplayHttpError extends Error {
  constructor(public status: number) { super(`display request failed (${status})`); }
}

/**
 * The screen has no account: no session, no cookies, no publishable key. Its secret travels only in the
 * `Authorization: Display <secret>` header to a fixed path (decision 335d), never in a URL a log records.
 */
async function screenRequest<T>(path: string, method: "GET" | "POST", token?: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_V1_URL}${path}`, { method, cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer",
    headers: { Authorization: token ? `Display ${token}` : "" }, signal });
  if (!response.ok) throw new DisplayHttpError(response.status);
  return (await response.json()) as T;
}

export const displayScreenApi = {
  register: () => screenRequest<DisplayRegistration>("/space-displays/register/", "POST"),
  state: (token: string, signal?: AbortSignal) => screenRequest<DisplayState>("/space-displays/state/", "GET", token, signal),
};

export const spaceNowKeys = {
  config: (slug: string) => ["space-now", slug, "config"] as const,
  hereNow: (slug: string) => ["space-now", slug, "here-now"] as const,
  machines: (slug: string) => ["space-now", slug, "machines"] as const,
  admin: (makerspaceId: number) => ["presence", "staff", makerspaceId, "displays"] as const,
};

const publicBase = (slug: string) => `/public/makerspaces/${encodeURIComponent(slug)}`;

/** The refresh interval of the public page sections; the server never caches a viewer-shaped body. */
export const NOW_REFRESH_MS = 30_000;

/** Optional session: the same URL answers a signed-in viewer with more cards than a visitor. */
export function useHereNow(slug: string, enabled: boolean) {
  return useQuery({ queryKey: spaceNowKeys.hereNow(slug), enabled: enabled && Boolean(slug),
    queryFn: () => tenantPublicRequest<HereNow>(slug, `${publicBase(slug)}/presence/here-now/`),
    refetchInterval: NOW_REFRESH_MS, refetchIntervalInBackground: false, retry: 1 });
}

export function useMachinesNow(slug: string, enabled: boolean) {
  return useQuery({ queryKey: spaceNowKeys.machines(slug), enabled: enabled && Boolean(slug),
    queryFn: () => tenantPublicRequest<MachinesNow>(slug, `${publicBase(slug)}/machines/now/`),
    refetchInterval: NOW_REFRESH_MS, refetchIntervalInBackground: false, retry: 1 });
}

const adminBase = (id: number) => `/admin/makerspace/${id}/presence-displays`;
export const adminDisplayApi = {
  list: (id: number) => staffRequest<AdminDisplayList>(adminBase(id)),
  claim: (id: number, input: DisplayConfigInput & { code: string }) =>
    staffRequest<AdminDisplay>(adminBase(id), { method: "POST", body: JSON.stringify(input) }),
  update: (id: number, displayId: number, input: DisplayConfigInput) =>
    staffRequest<AdminDisplay>(`${adminBase(id)}/${displayId}`, { method: "PATCH", body: JSON.stringify(input) }),
  provision: (id: number, input: DisplayConfigInput) =>
    staffRequest<AdminDisplay>(`${adminBase(id)}/link`, { method: "POST", body: JSON.stringify(input) }),
  rotateLink: (id: number, displayId: number) => staffRequest<AdminDisplay>(`${adminBase(id)}/${displayId}/link`, { method: "POST" }),
  unpair: (id: number, displayId: number) => staffRequest<void>(`${adminBase(id)}/${displayId}`, { method: "DELETE" }),
};
